# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marienz@gentoo.org>
#                         Thomas Gerigk <tgerigk@gmx.de>
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
"""Show or change a bug's target for fixing"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute(["a"], test=True)
    No target assigned.
    >>> execute(["a", "tomorrow"], test=True)
    >>> execute(["a"], test=True)
    tomorrow
    >>> execute(["--list"], test=True)
    tomorrow
    >>> execute(["a", "none"], test=True)
    >>> execute(["a"], test=True)
    No target assigned.
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
                             
    if len(args) not in (1, 2):
        if not (options.list == True and len(args) == 0):
            raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    if options.list:
        ts = set([bd.bug_from_uuid(bug).target for bug in bd.list_uuids()])
        for target in sorted(ts):
            if target and isinstance(target,str):
                print target
        return
    bug = cmdutil.bug_from_shortname(bd, args[0])
    if len(args) == 1:
        if bug.target is None:
            print "No target assigned."
        else:
            print bug.target
    else:
        assert len(args) == 2
        if args[1] == "none":
            bug.target = None
        else:
            bug.target = args[1]

def get_parser():
    parser = cmdutil.CmdOptionParser("be target BUG-ID [TARGET]\nor:    be target --list")
    parser.add_option("-l", "--list", action="store_true", dest="list",
                      help="List all available targets and exit")
    return parser

longhelp="""
Show or change a bug's target for fixing.  

If no target is specified, the current value is printed.  If a target
is specified, it will be assigned to the bug.

Targets are freeform; any text may be specified.  They will generally be
milestone names or release numbers.

The value "none" can be used to unset the target.

In the alternative `be target --list` form print a list of all
currently specified targets.  Note that bug status
(i.e. opened/closed) is ignored.  If you want to list all bugs
matching a current target, see `be list --target TARGET'.
"""

def help():
    return get_parser().help_str() + longhelp
