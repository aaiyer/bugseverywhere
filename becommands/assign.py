# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
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
"""Assign an individual or group to fix a bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> bd.bug_from_shortname("a").assigned is None
    True

    >>> execute(["a"], manipulate_encodings=False)
    >>> bd._clear_bugs()
    >>> bd.bug_from_shortname("a").assigned == bd.user_id
    True

    >>> execute(["a", "someone"], manipulate_encodings=False)
    >>> bd._clear_bugs()
    >>> print bd.bug_from_shortname("a").assigned
    someone

    >>> execute(["a","none"], manipulate_encodings=False)
    >>> bd._clear_bugs()
    >>> bd.bug_from_shortname("a").assigned is None
    True
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
    assert(len(args) in (0, 1, 2))
    if len(args) == 0:
        raise cmdutil.UsageError("Please specify a bug id.")
    if len(args) > 2:
        help()
        raise cmdutil.UsageError("Too many arguments.")
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bug = cmdutil.bug_from_id(bd, args[0])
    bug = bd.bug_from_shortname(args[0])
    if len(args) == 1:
        bug.assigned = bd.user_id
    elif len(args) == 2:
        if args[1] == "none":
            bug.assigned = None
        else:
            bug.assigned = args[1]
    bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be assign BUG-ID [ASSIGNEE]")
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
