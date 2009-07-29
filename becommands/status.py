# Copyright (C) 2008-2009 W. Trevor King <wking@drexel.edu>
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
"""Show or change a bug's status"""
from libbe import cmdutil, bugdir, bug
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute(["a"], manipulate_encodings=False)
    open
    >>> execute(["a", "closed"], manipulate_encodings=False)
    >>> execute(["a"], manipulate_encodings=False)
    closed
    >>> execute(["a", "none"], manipulate_encodings=False)
    Traceback (most recent call last):
    UserError: Invalid status: none
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) not in (1,2):
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bug = cmdutil.bug_from_shortname(bd, args[0])
    if len(args) == 1:
        print bug.status
    else:
        try:
            bug.status = args[1]
        except ValueError, e:
            if e.name != "status":
                raise
            raise cmdutil.UserError ("Invalid status: %s" % e.value)

def get_parser():
    parser = cmdutil.CmdOptionParser("be status BUG-ID [STATUS]")
    return parser


def help():
    try: # See if there are any per-tree status configurations
        bd = bugdir.BugDir(from_disk=True,
                           manipulate_encodings=False)
    except bugdir.NoBugDir, e:
        pass # No tree, just show the defaults
    longest_status_len = max([len(s) for s in bug.status_values])
    active_statuses = []
    for status in bug.active_status_values :
        description = bug.status_description[status]
        s = "%*s : %s" % (longest_status_len, status, description)
        active_statuses.append(s)
    inactive_statuses = []
    for status in bug.inactive_status_values :
        description = bug.status_description[status]
        s = "%*s : %s" % (longest_status_len, status, description)
        inactive_statuses.append(s)
    longhelp="""
Show or change a bug's status.

If no status is specified, the current value is printed.  If a status
is specified, it will be assigned to the bug.

There are two classes of statuses, active and inactive, which are only
important for commands like "be list" that show only active bugs by
default.

Active status levels are:
  %s
Inactive status levels are:
  %s

You can overide the list of allowed statuses on a per-repository basis.
See "be set --help" for more details.
""" % ('\n  '.join(active_statuses), '\n  '.join(inactive_statuses))
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option,value in cmdutil.option_value_pairs(options, parser):
        if value == "--complete":
            # no argument-options at the moment, so this is future-proofing
            raise cmdutil.GetCompletions()
    for pos,value in enumerate(args):
        if value == "--complete":
            try: # See if there are any per-tree status configurations
                bd = bugdir.BugDir(from_disk=True,
                                   manipulate_encodings=False)
            except bugdir.NoBugDir:
                bd = None
            if pos == 0: # fist positional argument is a bug id 
                ids = []
                if bd != None:
                    bd.load_all_bugs()
                    ids = [bd.bug_shortname(bg) for bg in bd]
                raise cmdutil.GetCompletions(ids)
            elif pos == 1: # second positional argument is a status
                raise cmdutil.GetCompletions(bug.status_values)
            raise cmdutil.GetCompletions()
