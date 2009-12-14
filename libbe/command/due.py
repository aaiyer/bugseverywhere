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

import libbe
import libbe.command
import libbe.command.util
import libbe.util.utility

DUE_TAG = 'DUE:'

class Due (libbe.command.Command):
    """Set bug due dates

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Due()
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> ret = cmd.run(bd.storage, bd, {}, ['/a'])
    No due date assigned.
    >>> ret = cmd.run(bd.storage, bd, {}, ['/a', 'Thu, 01 Jan 1970 00:00:00 +0000'])
    >>> ret = cmd.run(bd.storage, bd, {}, ['/a'])
    Thu, 01 Jan 1970 00:00:00 +0000
    >>> ret = cmd.run(bd.storage, bd, {}, ['/a', 'none'])
    >>> ret = cmd.run(bd.storage, bd, {}, ['/a'])
    No due date assigned.
    >>> bd.cleanup()
    """
    name = 'due'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.requires_bugdir = True
        self.args.extend([
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID',
                    completion_callback=libbe.command.util.complete_bug_id),
                libbe.command.Argument(
                    name='due', metavar='DUE', optional=True),
                ])

    def _run(self, storage, bugdir, **params):
        bug,dummy_comment = libbe.command.util.bug_comment_from_user_id(
            bugdir, params['bug-id'])
        if params['due'] == None:
            due_time = get_due(bug)
            if due_time is None:
                print >> self.stdout, 'No due date assigned.'
            else:
                print >> self.stdout, libbe.util.utility.time_to_str(due_time)
        else:
            if params['due'] == 'none':
                remove_due(bug)
            else:
                due_time = libbe.util.utility.str_to_time(params['due'])
                set_due(bug, due_time)

    def _long_help(self):
        return """
If no DATE is specified, the bug's current due date is printed.  If
DATE is specified, it will be assigned to the bug.
"""

# internal helper functions

def _generate_due_string(time):
    return "%s%s" % (DUE_TAG, libbe.util.utility.time_to_str(time))

def _parse_due_string(string):
    assert string.startswith(DUE_TAG)
    return libbe.util.utility.str_to_time(string[len(DUE_TAG):])

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
