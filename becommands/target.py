# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
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
    >>> execute(["a", "none"], test=True)
    >>> execute(["a"], test=True)
    No target assigned.
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) not in (1, 2):
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    bug = bd.bug_from_shortname(args[0])
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
        bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be target BUG-ID [TARGET]")
    return parser

longhelp="""
Show or change a bug's target for fixing.  

If no target is specified, the current value is printed.  If a target
is specified, it will be assigned to the bug.

Targets are freeform; any text may be specified.  They will generally be
milestone names or release numbers.

The value "none" can be used to unset the target.
"""

def help():
    return get_parser().help_str() + longhelp
