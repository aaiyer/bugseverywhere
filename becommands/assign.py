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
"""Assign an individual or group to fix a bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> bd.bug_from_shortname("a").assigned is None
    True

    >>> execute(["a"])
    >>> bd.load()
    >>> bd.bug_from_shortname("a").assigned == bd.rcs.get_user_id()
    True

    >>> execute(["a", "someone"])
    >>> bd.load()
    >>> print bd.bug_from_shortname("a").assigned
    someone

    >>> execute(["a","none"])
    >>> bd.load()
    >>> bd.bug_from_shortname("a").assigned is None
    True
    """
    options, args = get_parser().parse_args(args)
    assert(len(args) in (0, 1, 2))
    if len(args) == 0:
        raise cmdutil.UserError("Please specify a bug id.")
    if len(args) > 2:
        help()
        raise cmdutil.UserError("Too many arguments.")
    bd = bugdir.BugDir(loadNow=True)
    bug = bd.bug_from_shortname(args[0])
    if len(args) == 1:
        bug.assigned = bug.rcs.get_user_id()
    elif len(args) == 2:
        if args[1] == "none":
            bug.assigned = None
        else:
            bug.assigned = args[1]
    bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be assign bug-id [assignee]")
    return parser

longhelp = """
Assign a person to fix a bug.

By default, the bug is self-assigned.  If an assignee is specified, the bug
will be assigned to that person.

Assignees should be the person's Bugs Everywhere identity, the string that
appears in Creator fields.

To un-assign a bug, specify "none" for the assignee.
"""

def help():
    return get_parser().help_str() + longhelp
