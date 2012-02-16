# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Valtteri Kokkoniemi <rvk@iki.fi>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

import copy
import os
import sys
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree

import libbe
import libbe.bug
import libbe.command
import libbe.command.util
import libbe.comment
import libbe.util.encoding
import libbe.util.utility

if libbe.TESTING == True:
    import doctest
    import StringIO
    import unittest

    import libbe.bugdir

class Import_XML (libbe.command.Command):
    """Import comments and bugs from XML

    >>> import time
    >>> import StringIO
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Import_XML(ui=ui)

    >>> ui.io.set_stdin('<be-xml><comment><uuid>c</uuid><body>This is a comment about a</body></comment></be-xml>')
    >>> ret = ui.run(cmd, {'comment-root':'/a'}, ['-'])
    >>> bd.flush_reload()
    >>> bug = bd.bug_from_uuid('a')
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    This is a comment about a
    <BLANKLINE>
    >>> comment.time <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'import-xml'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='ignore-missing-references', short_name='i',
                    help="If any comment's <in-reply-to> refers to a non-existent comment, ignore it (instead of raising an exception)."),
                libbe.command.Option(name='add-only', short_name='a',
                    help='If any bug or comment listed in the XML file already exists in the bug repository, do not alter the repository version.'),
                libbe.command.Option(name='preserve-uuids', short_name='p',
                    help='Preserve UUIDs for trusted input (potential name collisions).'),
                libbe.command.Option(name='comment-root', short_name='c',
                    help='Supply a bug or comment ID as the root of any <comment> elements that are direct children of the <be-xml> element.  If any such <comment> elements exist, you are required to set this option.',
                    arg=libbe.command.Argument(
                        name='comment-root', metavar='ID',
                        completion_callback=libbe.command.util.complete_bug_comment_id)),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='xml-file', metavar='XML-FILE'),
                ])

    def _run(self, **params):
        bugdir = self._get_bugdir()
        writeable = bugdir.storage.writeable
        bugdir.storage.writeable = False
        if params['comment-root'] != None:
            croot_bug,croot_comment = \
                libbe.command.util.bug_comment_from_user_id(
                    bugdir, params['comment-root'])
            croot_bug.load_comments(load_full=True)
            if croot_comment.uuid == libbe.comment.INVALID_UUID:
                croot_comment = croot_bug.comment_root
            else:
                croot_comment = croot_bug.comment_from_uuid(croot_comment.uuid)
            new_croot_bug = libbe.bug.Bug(bugdir=bugdir, uuid=croot_bug.uuid)
            new_croot_bug.explicit_attrs = []
            new_croot_bug.comment_root = copy.deepcopy(croot_bug.comment_root)
            if croot_comment.uuid == libbe.comment.INVALID_UUID:
                new_croot_comment = new_croot_bug.comment_root
            else:
                new_croot_comment = \
                    new_croot_bug.comment_from_uuid(croot_comment.uuid)
            for new in new_croot_bug.comments():
                new.explicit_attrs = []
        else:
            croot_bug,croot_comment = (None, None)

        if params['xml-file'] == '-':
            xml = self.stdin.read().encode(self.stdin.encoding)
        else:
            self._check_restricted_access(bugdir.storage, params['xml-file'])
            xml = libbe.util.encoding.get_file_contents(
                params['xml-file'])

        # parse the xml
        root_bugs = []
        root_comments = []
        version = {}
        be_xml = ElementTree.XML(xml)
        if be_xml.tag != 'be-xml':
            raise libbe.util.utility.InvalidXML(
                'import-xml', be_xml, 'root element must be <be-xml>')
        for child in be_xml.getchildren():
            if child.tag == 'bug':
                new = libbe.bug.Bug(bugdir=bugdir)
                new.from_xml(child, preserve_uuids=params['preserve-uuids'])
                root_bugs.append(new)
            elif child.tag == 'comment':
                new = libbe.comment.Comment(croot_bug)
                new.from_xml(child, preserve_uuids=params['preserve-uuids'])
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
        if params['add-only'] == True:
            accept_changes = False
            accept_extra_strings = False
        else:
            accept_changes = True
            accept_extra_strings = True
        accept_comments = True
        if len(root_comments) > 0:
            if croot_bug == None:
                raise libbe.command.UserError(
                    '--comment-root option is required for your root comments:\n%s'
                    % '\n\n'.join([c.string() for c in root_comments]))
            try:
                # link new comments
                new_croot_bug.add_comments(root_comments,
                                           default_parent=new_croot_comment,
                                           ignore_missing_references= \
                                               params['ignore-missing-references'])
            except libbe.comment.MissingReference, e:
                raise libbe.command.UserError(e)
            croot_bug.merge(new_croot_bug, accept_changes=accept_changes,
                            accept_extra_strings=accept_extra_strings,
                            accept_comments=accept_comments)

        # merge the new croot_bugs
        merged_bugs = []
        old_bugs = []
        for new in root_bugs:
            try:
                old = bugdir.bug_from_uuid(new.alt_id)
            except KeyError:
                old = None
            if old == None:
                bugdir.append(new)
            else:
                old.load_comments(load_full=True)
                old.merge(new, accept_changes=accept_changes,
                          accept_extra_strings=accept_extra_strings,
                          accept_comments=accept_comments)
                merged_bugs.append(new)
                old_bugs.append(old)

        # protect against programmer error causing data loss:
        if croot_bug != None:
            comms = []
            for c in croot_comment.traverse():
                comms.append(c.uuid)
                if c.alt_id != None:
                    comms.append(c.alt_id)
            if croot_comment.uuid == libbe.comment.INVALID_UUID:
                root_text = croot_bug.id.user()
            else:
                root_text = croot_comment.id.user()
            for new in root_comments:
                assert new.uuid in comms or new.alt_id in comms, \
                    "comment %s (alt: %s) wasn't added to %s" \
                    % (new.uuid, new.alt_id, root_text)
        for new in root_bugs:
            if not new in merged_bugs:
                assert bugdir.has_bug(new.uuid), \
                    "bug %s wasn't added" % (new.uuid)

        # save new information
        bugdir.storage.writeable = writeable
        if croot_bug != None:
            croot_bug.save()
        for new in root_bugs:
            if not new in merged_bugs:
                new.save()
        for old in old_bugs:
            old.save()

    def _long_help(self):
        return """
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


Import_xml = Import_XML # alias for libbe.command.base.get_command_class()

if libbe.TESTING == True:
    class LonghelpTestCase (unittest.TestCase):
        """
        Test import scenarios given in longhelp.
        """
        def setUp(self):
            self.bugdir = libbe.bugdir.SimpleBugDir(memory=False)
            io = libbe.command.StringInputOutput()
            self.ui = libbe.command.UserInterface(io=io)
            self.ui.storage_callbacks.set_storage(self.bugdir.storage)
            self.cmd = Import_XML(ui=self.ui)
            self.cmd._storage = self.bugdir.storage
            self.cmd._setup_io = lambda i_enc,o_enc : None
            bugA = self.bugdir.bug_from_uuid('a')
            self.bugdir.remove_bug(bugA)
            self.bugdir.storage.writeable = False
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
            self.bugdir.storage.writeable = True
            bugB.save()
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
            self.root_comment_xml = """
            <be-xml>
              <comment>
                <uuid>c1</uuid>
                <body>So long</body>
              </comment>
              <comment>
                <uuid>c3</uuid>
                <author>Jed</author>
                <body>And thanks</body>
              </comment>
            </be-xml>
            """
        def tearDown(self):
            self.bugdir.cleanup()
            self.ui.cleanup()
        def _execute(self, xml, params={}, args=[]):
            self.ui.io.set_stdin(xml)
            self.ui.run(self.cmd, params, args)
            self.bugdir.flush_reload()
        def testCleanBugdir(self):
            uuids = list(self.bugdir.uuids())
            self.failUnless(uuids == ['b'], uuids)
        def testNotAddOnly(self):
            bugB = self.bugdir.bug_from_uuid('b')
            self._execute(self.xml, {}, ['-'])
            uuids = list(self.bugdir.uuids())
            self.failUnless(uuids == ['b'], uuids)
            bugB = self.bugdir.bug_from_uuid('b')
            self.failUnless(bugB.uuid == 'b', bugB.uuid)
            self.failUnless(bugB.creator == 'John', bugB.creator)
            self.failUnless(bugB.status == 'fixed', bugB.status)
            self.failUnless(bugB.summary == 'a test bug', bugB.summary)
            estrs = ["don't forget your towel",
                     'helps with space travel',
                     'watch out for flying dolphins']
            self.failUnless(bugB.extra_strings == estrs, bugB.extra_strings)
            comments = list(bugB.comments())
            self.failUnless(len(comments) == 3,
                            ['%s (%s, %s)' % (c.uuid, c.alt_id, c.body)
                             for c in comments])
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
            bugB = self.bugdir.bug_from_uuid('b')
            initial_bugB_summary = bugB.summary
            self._execute(self.xml, {'add-only':True}, ['-'])
            uuids = list(self.bugdir.uuids())
            self.failUnless(uuids == ['b'], uuids)
            bugB = self.bugdir.bug_from_uuid('b')
            self.failUnless(bugB.uuid == 'b', bugB.uuid)
            self.failUnless(bugB.creator == 'John', bugB.creator)
            self.failUnless(bugB.status == 'open', bugB.status)
            self.failUnless(bugB.summary == initial_bugB_summary, bugB.summary)
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
        def testRootCommentsNotAddOnly(self):
            bugB = self.bugdir.bug_from_uuid('b')
            initial_bugB_summary = bugB.summary
            self._execute(self.root_comment_xml, {'comment-root':'/b'}, ['-'])
            uuids = list(self.bugdir.uuids())
            uuids = list(self.bugdir.uuids())
            self.failUnless(uuids == ['b'], uuids)
            bugB = self.bugdir.bug_from_uuid('b')
            self.failUnless(bugB.uuid == 'b', bugB.uuid)
            self.failUnless(bugB.creator == 'John', bugB.creator)
            self.failUnless(bugB.status == 'open', bugB.status)
            self.failUnless(bugB.summary == initial_bugB_summary, bugB.summary)
            estrs = ["don't forget your towel",
                     'helps with space travel']
            self.failUnless(bugB.extra_strings == estrs, bugB.extra_strings)
            comments = list(bugB.comments())
            self.failUnless(len(comments) == 3,
                            ['%s (%s, %s)' % (c.uuid, c.alt_id, c.body)
                             for c in comments])
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
        def testRootCommentsAddOnly(self):
            bugB = self.bugdir.bug_from_uuid('b')
            initial_bugB_summary = bugB.summary
            self._execute(self.root_comment_xml,
                          {'comment-root':'/b', 'add-only':True}, ['-'])
            uuids = list(self.bugdir.uuids())
            self.failUnless(uuids == ['b'], uuids)
            bugB = self.bugdir.bug_from_uuid('b')
            self.failUnless(bugB.uuid == 'b', bugB.uuid)
            self.failUnless(bugB.creator == 'John', bugB.creator)
            self.failUnless(bugB.status == 'open', bugB.status)
            self.failUnless(bugB.summary == initial_bugB_summary, bugB.summary)
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

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
