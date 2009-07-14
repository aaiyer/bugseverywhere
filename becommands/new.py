# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
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
"""Create a new bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import os, time
    >>> from libbe import bug
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> bug.uuid_gen = lambda: "X"
    >>> execute (["this is a test",], test=True)
    Created bug with ID X
    >>> bd.load()
    >>> bug = bd.bug_from_uuid("X")
    >>> print bug.summary
    this is a test
    >>> bug.time <= int(time.time())
    True
    >>> print bug.severity
    minor
    >>> bug.target == None
    True
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) != 1:
        raise cmdutil.UsageError("Please supply a summary message")
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    if args[0] == '-': # read summary from stdin
        summary = sys.stdin.readline()
    else:
        summary = args[0]
    bug = bd.new_bug(summary=summary.strip())
    if options.reporter != None:
        bug.reporter = options.reporter
    else:
        bug.reporter = bug.creator
    if options.assigned != None:
        bug.assigned = options.assigned
    elif bd.default_assignee != None:
        bug.assigned = bd.default_assignee
    bd.save()
    print "Created bug with ID %s" % bd.bug_shortname(bug)

def get_parser():
    parser = cmdutil.CmdOptionParser("be new SUMMARY")
    parser.add_option("-r", "--reporter", metavar="REPORTER", dest="reporter",
                      help="The user who reported the bug", default=None)
    parser.add_option("-a", "--assigned", metavar="ASSIGNED", dest="assigned",
                      help="The developer in charge of the bug", default=None)
    return parser

longhelp="""
Create a new bug, with a new ID.  The summary specified on the
commandline is a string (only one line) that describes the bug briefly
or "-", in which case the string will be read from stdin.
"""

def help():
    return get_parser().help_str() + longhelp
