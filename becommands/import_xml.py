# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Import comments and bugs from XML"""
from libbe import cmdutil, bugdir, bug, comment, utility
from becommands.comment import complete
import copy
import os
import sys
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
import doctest
import unittest
__desc__ = __doc__

def execute(args, manipulate_encodings=True, restrict_file_access=False):
    """
    >>> import time
    >>> import StringIO
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> orig_stdin = sys.stdin
    >>> sys.stdin = StringIO.StringIO("<be-xml><comment><uuid>c</uuid><body>This is a comment about a</body></comment></be-xml>")
    >>> execute(["-c", "a", "-"], manipulate_encodings=False)
    >>> sys.stdin = orig_stdin
    >>> bd._clear_bugs()
    >>> bug = cmdutil.bug_from_id(bd, "a")
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    This is a comment about a
    <BLANKLINE>
    >>> comment.author == bd.user_id
    True
    >>> comment.time <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) < 1:
        raise cmdutil.UsageError("Please specify an XML file.")
    if len(args) > 1:
        raise cmdutil.UsageError("Too many arguments.")
    filename = args[0]

    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    if options.comment_root != None:
        croot_bug,croot_comment = \
            cmdutil.bug_comment_from_id(bd, options.comment_root)
        croot_bug.load_comments(load_full=True)
        croot_bug.set_sync_with_disk(False)
        if croot_comment.uuid == comment.INVALID_UUID:
            croot_comment = croot_bug.comment_root
        else:
            croot_comment = croot_bug.comment_from_uuid(croot_comment.uuid)
        new_croot_bug = bug.Bug(bugdir=bd, uuid=croot_bug.uuid)
        new_croot_bug.explicit_attrs = []
        new_croot_bug.comment_root = copy.deepcopy(croot_bug.comment_root)
        if croot_comment.uuid == comment.INVALID_UUID:
            new_croot_comment = new_croot_bug.comment_root
        else:
            new_croot_comment = \
                new_croot_bug.comment_from_uuid(croot_comment.uuid)
        for new in new_croot_bug.comments():
            new.explicit_attrs = []
    else:
        croot_bug,croot_comment = (None, None)

    if filename == '-':
        xml = sys.stdin.read()
    else:
        if restrict_file_access == True:
            cmdutil.restrict_file_access(bd, options.body)
        xml = bd.vcs.get_file_contents(filename, allow_no_vcs=True)
    str_xml = xml.encode('unicode_escape').replace(r'\n', '\n')
    # unicode read + encode to string so we know the encoding,
    # which might not be given (?) in a binary string read?

    # parse the xml
    root_bugs = []
    root_comments = []
    version = {}
    be_xml = ElementTree.XML(str_xml)
    if be_xml.tag != 'be-xml':
        raise utility.InvalidXML(
            'import-xml', be_xml, 'root element must be <be-xml>')
    for child in be_xml.getchildren():
        if child.tag == 'bug':
            new = bug.Bug(bugdir=bd)
            new.from_xml(unicode(ElementTree.tostring(child)).decode("unicode_escape"))
            root_bugs.append(new)
        elif child.tag == 'comment':
            new = comment.Comment(croot_bug)
            new.from_xml(unicode(ElementTree.tostring(child)).decode("unicode_escape"))
            root_comments.append(new)
        elif child.tag == 'version':
            for gchild in child.getchildren():
                if child.tag in ['tag', 'nick', 'revision', 'revision-id']:
                    text = xml.sax.saxutils.unescape(child.text)
                    text = text.decode('unicode_escape').strip()
                    version[child.tag] = text
                else:
                    print >> sys.stderr, 'ignoring unknown tag %s in %s' \
                        % (gchild.tag, child.tag)
        else:
            print >> sys.stderr, 'ignoring unknown tag %s in %s' \
                % (child.tag, comment_list.tag)

    # merge the new root_comments
    if options.add_only == True:
        accept_changes = False
        accept_extra_strings = False
    else:
        accept_changes = True
        accept_extra_strings = True
    accept_comments = True
    if len(root_comments) > 0:
        if croot_bug == None:
            raise UserError(
                '--comment-root option is required for your root comments:\n%s'
                % '\n\n'.join([c.string() for c in root_comments]))
        try:
            # link new comments
            new_croot_bug.add_comments(root_comments,
                                       default_parent=new_croot_comment,
                                       ignore_missing_references= \
                                           options.ignore_missing_references)
        except comment.MissingReference, e:
            raise cmdutil.UserError(e)
        croot_bug.merge(new_croot_bug, accept_changes=accept_changes,
                        accept_extra_strings=accept_extra_strings,
                        accept_comments=accept_comments)

    # merge the new croot_bugs
    merged_bugs = []
    old_bugs = []
    for new in root_bugs:
        try:
            old = bd.bug_from_uuid(new.alt_id)
        except KeyError:
            old = None
        if old == None:
            bd.append(new)
        else:
            old.load_comments(load_full=True)
            old.merge(new, accept_changes=accept_changes,
                      accept_extra_strings=accept_extra_strings,
                      accept_comments=accept_comments)
            merged_bugs.append(new)
            old_bugs.append(old)

    # protect against programmer error causing data loss:
    if croot_bug != None:
        comms = [c.uuid for c in croot_comment.traverse()]
        for new in root_comments:
            assert new.uuid in comms, \
                "comment %s wasn't added to %s" % (new.uuid, croot_comment.uuid)
    for new in root_bugs:
        if not new in merged_bugs:
            assert bd.has_bug(new.uuid), \
                "bug %s wasn't added" % (new.uuid)

    # save new information
    if croot_bug != None:
        croot_bug.save()
    for new in root_bugs:
        if not new in merged_bugs:
            new.save()
    for old in old_bugs:
        old.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be import-xml XMLFILE")
    parser.add_option("-i", "--ignore-missing-references", action="store_true",
                      dest="ignore_missing_references", default=False,
                      help="If any comment's <in-reply-to> refers to a non-existent comment, ignore it (instead of raising an exception).")
    parser.add_option("-a", "--add-only", action='store_true',
                      dest="add_only", default=False,
                      help="If any bug or comment listed in the XML file already exists in the bug repository, do not alter the repository version.")
    parser.add_option("-c", "--comment-root", dest="comment_root",
                      help="Supply a bug or comment ID as the root of any <comment> elements that are direct children of the <be-xml> element.  If any such <comment> elements exist, you are required to set this option.")
    return parser

longhelp="""
Import comments and bugs from XMLFILE.  If XMLFILE is '-', the file is
read from stdin.

This command provides a fallback mechanism for passing bugs between
repositories, in case the repositories VCSs are incompatible.  If the
VCSs are compatible, it's better to use their builtin merge/push/pull
to share this information, as that will preserve a more detailed
history.

The XML file should be formatted similarly to
  <be-xml>
    <version>
      <tag>1.0.0</tag>
      <branch-nick>be</branch-nick>
      <revno>446</revno>
      <revision-id>a@b.com-20091119214553-iqyw2cpqluww3zna</revision-id>
    <version>
    <bug>
      ...
      <comment>...</comment>
      <comment>...</comment>
    </bug>
    <bug>...</bug>
    <comment>...</comment>
    <comment>...</comment>
  </be-xml>
where the ellipses mark output commpatible with Bug.xml() and
Comment.xml().  Take a look at the output of `be show --xml` for some
explicit examples.  Unrecognized tags are ignored.  Missing tags are
left at the default value.  The version tag is not required, but is
strongly recommended.

The bug and comment UUIDs are always auto-generated, so if you set a
<uuid> field, but no <alt-id> field, your <uuid> will be used as the
comment's <alt-id>.  An exception is raised if <alt-id> conflicts with
an existing comment.  Bugs do not have a permantent alt-id, so they
the <uuid>s you specify are not saved.  The <uuid>s _are_ used to
match agains prexisting bug and comment uuids, and comment alt-ids,
and fields explicitly given in the XML file will replace old versions
unless the --add-only flag.

*.extra_strings recieves special treatment, and if --add-only is not
set, the resulting list concatenates both source lists and removes
repeats.

Here's an example of import activity:
  Repository
   bug (uuid=B, creator=John, status=open)
     estr (don't forget your towel)
     estr (helps with space travel)
     com (uuid=C1, author=Jane, body=Hello)
     com (uuid=C2, author=Jess, body=World)
  XML
   bug (uuid=B, status=fixed)
     estr (don't forget your towel)
     estr (watch out for flying dolphins)
     com (uuid=C1, body=So long)
     com (uuid=C3, author=Jed, body=And thanks)
  Result
   bug (uuid=B, creator=John, status=fixed)
     estr (don't forget your towel)
     estr (helps with space travel)
     estr (watch out for flying dolphins)
     com (uuid=C1, author=Jane, body=So long)
     com (uuid=C2, author=Jess, body=World)
     com (uuid=C4, alt-id=C3, author=Jed, body=And thanks)
  Result, with --add-only
   bug (uuid=B, creator=John, status=open)
     estr (don't forget your towel)
     estr (helps with space travel)
     com (uuid=C1, author=Jane, body=Hello)
     com (uuid=C2, author=Jess, body=World)
     com (uuid=C4, alt-id=C3, author=Jed, body=And thanks)

Examples:

Import comments (e.g. emails from an mbox) and append to bug XYZ
  $ be-mbox-to-xml mail.mbox | be import-xml --c XYZ -
Or you can append those emails underneath the prexisting comment XYZ-3
  $ be-mbox-to-xml mail.mbox | be import-xml --c XYZ-3 -

User creates a new bug
  user$ be new "The demuxulizer is broken"
  Created bug with ID 48f
  user$ be comment 48f
  <Describe bug>
  ...
User exports bug as xml and emails it to the developers
  user$ be show --xml 48f > 48f.xml
  user$ cat 48f.xml | mail -s "Demuxulizer bug xml" devs@b.com
or equivalently (with a slightly fancier be-handle-mail compatible
email):
  user$ be email-bugs 48f
Devs recieve email, and save it's contents as demux-bug.xml
  dev$ cat demux-bug.xml | be import-xml -
"""

def help():
    return get_parser().help_str() + longhelp


class LonghelpTestCase (unittest.TestCase):
    """
    Test import scenarios given in longhelp.
    """
    def setUp(self):
        self.bugdir = bugdir.SimpleBugDir()
        self.original_working_dir = os.getcwd()
        os.chdir(self.bugdir.root)
        bugA = self.bugdir.bug_from_uuid('a')
        self.bugdir.remove_bug(bugA)
        self.bugdir.set_sync_with_disk(False)
        bugB = self.bugdir.bug_from_uuid('b')
        bugB.creator = 'John'
        bugB.status = 'open'
        bugB.extra_strings += ["don't forget your towel"]
        bugB.extra_strings += ['helps with space travel']
        comm1 = bugB.comment_root.new_reply(body='Hello\n')
        comm1.uuid = 'c1'
        comm1.author = 'Jane'
        comm2 = bugB.comment_root.new_reply(body='World\n')
        comm2.uuid = 'c2'
        comm2.author = 'Jess'
        bugB.save()
        self.bugdir.set_sync_with_disk(True)
        self.xml = """
        <be-xml>
          <bug>
            <uuid>b</uuid>
            <status>fixed</status>
            <summary>a test bug</summary>
            <extra-string>don't forget your towel</extra-string>
            <extra-string>watch out for flying dolphins</extra-string>
            <comment>
              <uuid>c1</uuid>
              <body>So long</body>
            </comment>
            <comment>
              <uuid>c3</uuid>
              <author>Jed</author>
              <body>And thanks</body>
            </comment>
          </bug>
        </be-xml>
        """
    def tearDown(self):
        os.chdir(self.original_working_dir)
        self.bugdir.cleanup()
    def _execute(self, *args):
        import StringIO
        orig_stdin = sys.stdin
        sys.stdin = StringIO.StringIO(self.xml)
        execute(list(args)+["-"], manipulate_encodings=False,
                restrict_file_access=True)
        sys.stdin = orig_stdin
        self.bugdir._clear_bugs()
    def testCleanBugdir(self):
        uuids = list(self.bugdir.uuids())
        self.failUnless(uuids == ['b'], uuids)
    def testNotAddOnly(self):
        self._execute()
        uuids = list(self.bugdir.uuids())
        self.failUnless(uuids == ['b'], uuids)
        bugB = self.bugdir.bug_from_uuid('b')
        self.failUnless(bugB.uuid == 'b', bugB.uuid)
        self.failUnless(bugB.creator == 'John', bugB.creator)
        self.failUnless(bugB.status == 'fixed', bugB.status)
        estrs = ["don't forget your towel",
                 'helps with space travel',
                 'watch out for flying dolphins']
        self.failUnless(bugB.extra_strings == estrs, bugB.extra_strings)
        comments = list(bugB.comments())
        self.failUnless(len(comments) == 3,
                        ['%s (%s, %s)' % (c.uuid, c.alt_id, c.body) for c in comments])
        c1 = bugB.comment_from_uuid('c1')
        comments.remove(c1)
        self.failUnless(c1.uuid == 'c1', c1.uuid)
        self.failUnless(c1.alt_id == None, c1.alt_id)
        self.failUnless(c1.author == 'Jane', c1.author)
        self.failUnless(c1.body == 'So long\n', c1.body)
        c2 = bugB.comment_from_uuid('c2')
        comments.remove(c2)
        self.failUnless(c2.uuid == 'c2', c2.uuid)
        self.failUnless(c2.alt_id == None, c2.alt_id)
        self.failUnless(c2.author == 'Jess', c2.author)
        self.failUnless(c2.body == 'World\n', c2.body)
        c4 = comments[0]
        self.failUnless(len(c4.uuid) == 36, c4.uuid)
        self.failUnless(c4.alt_id == 'c3', c4.alt_id)
        self.failUnless(c4.author == 'Jed', c4.author)
        self.failUnless(c4.body == 'And thanks\n', c4.body)
    def testAddOnly(self): 
        self._execute('--add-only')
        uuids = list(self.bugdir.uuids())
        self.failUnless(uuids == ['b'], uuids)
        bugB = self.bugdir.bug_from_uuid('b')
        self.failUnless(bugB.uuid == 'b', bugB.uuid)
        self.failUnless(bugB.creator == 'John', bugB.creator)
        self.failUnless(bugB.status == 'open', bugB.status)
        estrs = ["don't forget your towel",
                 'helps with space travel']
        self.failUnless(bugB.extra_strings == estrs, bugB.extra_strings)
        comments = list(bugB.comments())
        self.failUnless(len(comments) == 3,
                        ['%s (%s)' % (c.uuid, c.alt_id) for c in comments])
        c1 = bugB.comment_from_uuid('c1')
        comments.remove(c1)
        self.failUnless(c1.uuid == 'c1', c1.uuid)
        self.failUnless(c1.alt_id == None, c1.alt_id)
        self.failUnless(c1.author == 'Jane', c1.author)
        self.failUnless(c1.body == 'Hello\n', c1.body)
        c2 = bugB.comment_from_uuid('c2')
        comments.remove(c2)
        self.failUnless(c2.uuid == 'c2', c2.uuid)
        self.failUnless(c2.alt_id == None, c2.alt_id)
        self.failUnless(c2.author == 'Jess', c2.author)
        self.failUnless(c2.body == 'World\n', c2.body)
        c4 = comments[0]
        self.failUnless(len(c4.uuid) == 36, c4.uuid)
        self.failUnless(c4.alt_id == 'c3', c4.alt_id)
        self.failUnless(c4.author == 'Jed', c4.author)
        self.failUnless(c4.body == 'And thanks\n', c4.body)

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
