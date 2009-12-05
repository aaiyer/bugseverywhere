# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         Thomas Habets <thomas@habets.pp.se>
#                         W. Trevor King <wking@drexel.edu>
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
"""Show a particular bug, comment, or combination of both."""
import sys
from libbe import cmdutil, bugdir, comment, version, _version
__desc__ = __doc__

def execute(args, manipulate_encodings=True, restrict_file_access=False):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> execute (["a",], manipulate_encodings=False) # doctest: +ELLIPSIS
              ID : a
      Short name : a
        Severity : minor
          Status : open
        Assigned : 
          Target : 
        Reporter : 
         Creator : John Doe <jdoe@example.com>
         Created : ...
    Bug A
    <BLANKLINE>
    >>> execute (["--xml", "a"], manipulate_encodings=False) # doctest: +ELLIPSIS
    <?xml version="1.0" encoding="..." ?>
    <be-xml>
      <version>
        <tag>...</tag>
        <branch-nick>...</branch-nick>
        <revno>...</revno>
        <revision-id>...</revision-id>
      </version>
      <bug>
        <uuid>a</uuid>
        <short-name>a</short-name>
        <severity>minor</severity>
        <status>open</status>
        <creator>John Doe &lt;jdoe@example.com&gt;</creator>
        <created>Thu, 01 Jan 1970 00:00:00 +0000</created>
        <summary>Bug A</summary>
      </bug>
    </be-xml>
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={-1: lambda bug : bug.active==True})
    if len(args) == 0:
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)

    if options.only_raw_body == True:
        if len(args) != 1:
            raise cmdutil.UsageError(
                'only one ID accepted with --only-raw-body')
        bug,comment = cmdutil.bug_comment_from_id(bd, args[0])
        if comment == bug.comment_root:
            raise cmdutil.UsageError(
                "--only-raw-body requires a comment ID, not '%s'" % args[0])
        sys.__stdout__.write(comment.body)
        sys.exit(0)
    print output(args, bd, as_xml=options.XML, with_comments=options.comments)

def get_parser():
    parser = cmdutil.CmdOptionParser("be show [options] ID [ID ...]")
    parser.add_option("-x", "--xml", action="store_true", default=False,
                      dest='XML', help="Dump as XML")
    parser.add_option("--only-raw-body", action="store_true",
                      dest='only_raw_body',
                      help="When printing only a single comment, just print it's body.  This allows extraction of non-text content types.")
    parser.add_option("-c", "--no-comments", dest="comments",
                      action="store_false", default=True,
                      help="Disable comment output.  This is useful if you just want more details on a bug's current status.")
    return parser

longhelp="""
Show all information about the bugs or comments whose IDs are given.

Without the --xml flag set, it's probably not a good idea to mix bug
and comment IDs in a single call, but you're free to do so if you
like.  With the --xml flag set, there will never be any root comments,
so mix and match away (the bug listings for directly requested
comments will be restricted to the bug uuid and the requested
comment(s)).

Directly requested comments will be grouped by their parent bug and
placed at the end of the output, so the ordering may not match the
order of the listed IDs.
"""

def help():
    return get_parser().help_str() + longhelp

def _sort_ids(ids, with_comments=True):
    bugs = []
    root_comments = {}
    for id in ids:
        bugname,commname = cmdutil.parse_id(id)
        if commname == None:
            bugs.append(bugname)
        elif with_comments == True:
            if bugname not in root_comments:
                root_comments[bugname] = [commname]
            else:
                root_comments[bugname].append(commname)
    for bugname in root_comments.keys():
        assert bugname not in bugs, \
            "specifically requested both '%s%s' and '%s'" \
            % (bugname, root_comments[bugname][0], bugname)
    return (bugs, root_comments)

def _xml_header(encoding):
    lines = ['<?xml version="1.0" encoding="%s" ?>' % encoding,
             '<be-xml>',
             '  <version>',
             '    <tag>%s</tag>' % version.version()]
    for tag in ['branch-nick', 'revno', 'revision-id']:
        value = _version.version_info[tag.replace('-', '_')]
        lines.append('    <%s>%s</%s>' % (tag, value, tag))
    lines.append('  </version>')
    return lines

def _xml_footer():
    return ['</be-xml>']

def output(ids, bd, as_xml=True, with_comments=True):
    bugs,root_comments = _sort_ids(ids, with_comments)
    lines = []
    if as_xml:
        lines.extend(_xml_header(bd.encoding))
    else:
        spaces_left = len(ids) - 1
    for bugname in bugs:
        bug = cmdutil.bug_from_id(bd, bugname)
        if as_xml:
            lines.append(bug.xml(indent=2, show_comments=with_comments))
        else:
            lines.append(bug.string(show_comments=with_comments))
            if spaces_left > 0:
                spaces_left -= 1
                lines.append('') # add a blank line between bugs/comments
    for bugname,comments in root_comments.items():
        bug = cmdutil.bug_from_id(bd, bugname)
        if as_xml:
            lines.extend(['  <bug>', '    <uuid>%s</uuid>' % bug.uuid])
        for commname in comments:
            try:
                comment = bug.comment_root.comment_from_shortname(commname)
            except comment.InvalidShortname, e:
                raise UserError(e.message)
            if as_xml:
                lines.append(comment.xml(indent=4, shortname=bugname))
            else:
                lines.append(comment.string(shortname=bugname))
                if spaces_left > 0:
                    spaces_left -= 1
                    lines.append('') # add a blank line between bugs/comments
        if as_xml:
            lines.append('</bug>')
    if as_xml:
        lines.extend(_xml_footer())
    return '\n'.join(lines)
