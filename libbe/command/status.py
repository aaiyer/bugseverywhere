# Copyright (C) 2008-2009 Gianluca Montecchi <gian@grys.it>
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

import libbe
import libbe.bug
import libbe.command
import libbe.command.util


class Status (libbe.command.Command):
    """Change a bug's status level

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Status()
    >>> cmd._storage = bd.storage
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> bd.bug_from_uuid('a').status
    'open'
    >>> ret = cmd.run(args=['closed', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').status
    'closed'
    >>> ret = cmd.run(args=['none', '/a'])
    Traceback (most recent call last):
    UserError: Invalid status level: none
    >>> bd.cleanup()
    """
    name = 'status'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.args.extend([
                libbe.command.Argument(
                    name='status', metavar='STATUS', default=None,
                    completion_callback=libbe.command.util.complete_status),
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID', default=None,
                    repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                ])
    
    def _run(self, **params):
        bugdir = self._get_bugdir()
        for bug_id in params['bug-id']:
            bug,dummy_comment = \
                libbe.command.util.bug_comment_from_user_id(bugdir, bug_id)
            if bug.status != params['status']:
                try:
                    bug.status = params['status']
                except ValueError, e:
                    if e.name != 'status':
                        raise e
                    raise libbe.command.UserError(
                        'Invalid status level: %s' % e.value)
        return 0

    def _long_help(self):
        longest_status_len = max([len(s) for s in libbe.bug.status_values])
        active_statuses = []
        for status in libbe.bug.active_status_values :
            description = libbe.bug.status_description[status]
            s = "%*s : %s" % (longest_status_len, status, description)
            active_statuses.append(s)
        inactive_statuses = []
        for status in libbe.bug.inactive_status_values :
            description = libbe.bug.status_description[status]
            s = "%*s : %s" % (longest_status_len, status, description)
            inactive_statuses.append(s)
        ret = """
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
        return ret
