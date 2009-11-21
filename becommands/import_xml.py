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
import os
import sys
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
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
    else:
        croot_bug,croot_comment = (None, None)

    if filename == '-':
        xml = sys.stdin.read()
    else:
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
            new.from_xml(unicode(ElementTree.tostring(child)).decode('unicode_escape'))
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
    croot_cids = []
    for c in croot_bug.comment_root.traverse():
        croot_cids.append(c.uuid)
        if c.alt_id != None:
            croot_cids.append(c.alt_id)
    for new in root_comments:
        if new.alt_id in croot_cids:
            raise cmdutil.UserError(
                'clashing comment alt_id: %s' % new.alt_id)
        croot_cids.append(new.uuid)
        if new.alt_id != None:
            croot_cids.append(new.alt_id)
        if new.in_reply_to == None:
            new.in_reply_to = croot_comment.uuid
    try:
        # link new comments
        comment.list_to_root(root_comments,croot_bug,root=croot_comment,
                             ignore_missing_references= \
                                 options.ignore_missing_references)
    except comment.MissingReference, e:
        raise cmdutil.UserError(e)

    # merge the new croot_bugs
    for new in root_bugs:
        bd.append(new)

    # protect against programmer error causing data loss:
    comms = [c.uuid for c in croot_comment.traverse()]
    for new in root_comments:
        assert new.uuid in comms, \
            "comment %s wasn't added to %s" % (new.uuid, croot_comment.uuid)
    for new in root_bugs:
        assert bd.has_bug(new.uuid), \
            "bug %s wasn't added" % (new.uuid)

    # save new information
    for new in root_comments:
        new.save()
    for new in root_bugs:
        new.save()

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
      <nick>be</nick>
      <revision>446</revision>
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
Comment.xml().  Take a look at the output of `be show --xml --version`
for some explicit examples.  Unrecognized tags are ignored.  Missing
tags are left at the default value.  The version tag is not required,
but is strongly recommended.

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
   bug (uuid=B, author=John, status=open)
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
   bug (uuid=B, author=John, status=fixed)
     estr (don't forget your towel)
     estr (helps with space travel)
     estr (watch out for flying dolphins)
     com (uuid=C1, author=Jane, body=So long)
     com (uuid=C2, author=Jess, body=World)
     com (uuid=C4, alt-id=C3, author=Jed, body=And thanks)
  Result, with --add-only
   bug (uuid=B, author=John, status=open)
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
  user$ be show --xml --version 48f > 48f.xml
  user$ cat 48f.xml | mail -s "Demuxulizer bug xml" devs@b.com
Devs recieve email, and save it's contents as demux-bug.xml
  dev$ cat demux-bug.xml | be import-xml -
"""

def help():
    return get_parser().help_str() + longhelp
