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
"""Set bug due dates"""
from libbe import cmdutil, bugdir, utility
__desc__ = __doc__

DUE_TAG="DUE:"

def execute(args, manipulate_encodings=True, restrict_file_access=False):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> bd.save()
    >>> os.chdir(bd.root)
    >>> execute(["a"], manipulate_encodings=False)
    No due date assigned.
    >>> execute(["a", "Thu, 01 Jan 1970 00:00:00 +0000"], manipulate_encodings=False)
    >>> execute(["a"], manipulate_encodings=False)
    Thu, 01 Jan 1970 00:00:00 +0000
    >>> execute(["a", "none"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    >>> execute(["a"], manipulate_encodings=False)
    No due date assigned.
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
                             
    if len(args) not in (1, 2):
        raise cmdutil.UsageError('Incorrect number of arguments.')
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bug = cmdutil.bug_from_id(bd, args[0])
    if len(args) == 1:
        due_time = get_due(bug)
        if due_time is None:
            print "No due date assigned."
        else:
            print utility.time_to_str(due_time)
    else:
        if args[1] == "none":
            remove_due(bug)
        else:
            due_time = utility.str_to_time(args[1])
            set_due(bug, due_time)

def get_parser():
    parser = cmdutil.CmdOptionParser("be due BUG-ID [DATE]")
    return parser

longhelp="""
If no DATE is specified, the bug's current due date is printed.  If
DATE is specified, it will be assigned to the bug.
"""

def help():
    return get_parser().help_str() + longhelp

# internal helper functions

def _generate_due_string(time):
    return "%s%s" % (DUE_TAG, utility.time_to_str(time))

def _parse_due_string(string):
    assert string.startswith(DUE_TAG)
    return utility.str_to_time(string[len(DUE_TAG):])

# functions exposed to other modules

def get_due(bug):
    matched = []
    for line in bug.extra_strings:
        if line.startswith(DUE_TAG):
            matched.append(_parse_due_string(line))
    if len(matched) == 0:
        return None
    if len(matched) > 1:
        raise Exception('Several due dates for %s?:\n  %s'
                        % (bug.uuid, '\n  '.join(matched)))
    return matched[0]

def remove_due(bug):
    estrs = bug.extra_strings
    for due_str in [s for s in estrs if s.startswith(DUE_TAG)]:
        estrs.remove(due_str)
    bug.extra_strings = estrs # reassign to notice change

def set_due(bug, time):
    remove_due(bug)
    estrs = bug.extra_strings
    estrs.append(_generate_due_string(time))
    bug.extra_strings = estrs # reassign to notice change
