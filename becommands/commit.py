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
"""Commit the currently pending changes to the repository"""
from libbe import cmdutil, bugdir, editor, vcs
import sys
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> from libbe import bug
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> full_path = "testfile"
    >>> test_contents = "A test file"
    >>> bd.vcs.set_file_contents(full_path, test_contents)
    >>> execute(["Added %s." % (full_path)], manipulate_encodings=False) # doctest: +ELLIPSIS
    Committed ...
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) != 1:
        raise cmdutil.UsageError("Please supply a commit message")
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    if args[0] == '-': # read summary from stdin
        assert options.body != "EDITOR", \
          "Cannot spawn and editor when the summary is using stdin."
        summary = sys.stdin.readline()
    else:
        summary = args[0]
    if options.body == None:
        body = None
    elif options.body == "EDITOR":
        body = editor.editor_string("Please enter your commit message above")
    else:
        body = bd.vcs.get_file_contents(options.body, allow_no_vcs=True)
    try:
        revision = bd.vcs.commit(summary, body=body,
                                 allow_empty=options.allow_empty)
    except vcs.EmptyCommit, e:
        print e
        return 1
    else:
        print "Committed %s" % revision

def get_parser():
    parser = cmdutil.CmdOptionParser("be commit COMMENT")
    parser.add_option("-b", "--body", metavar="FILE", dest="body",
                      help='Provide a detailed body for the commit message.  In the special case that FILE == "EDITOR", spawn an editor to enter the body text (in which case you cannot use stdin for the summary)', default=None)
    parser.add_option("-a", "--allow-empty", dest="allow_empty",
                      help="Allow empty commits",
                      default=False, action="store_true")
    return parser

longhelp="""
Commit the current repository status.  The summary specified on the
commandline is a string (only one line) that describes the commit
briefly or "-", in which case the string will be read from stdin.
"""

def help():
    return get_parser().help_str() + longhelp
