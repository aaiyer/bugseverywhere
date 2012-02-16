# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Robert Lehmann <mail@robertlehmann.de>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

import libbe
import libbe.command
import libbe.command.util


class Assign (libbe.command.Command):
    u"""Assign an individual or group to fix a bug

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Assign(ui=ui)

    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> ui._user_id = u'Fran\xe7ois'
    >>> ret = ui.run(cmd, args=['-', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    u'Fran\\xe7ois'

    >>> ret = ui.run(cmd, args=['someone', '/a', '/b'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    'someone'
    >>> bd.bug_from_uuid('b').assigned
    'someone'

    >>> ret = ui.run(cmd, args=['none', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'assign'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.args.extend([
                libbe.command.Argument(
                    name='assigned', metavar='ASSIGNED', default=None,
                    completion_callback=libbe.command.util.complete_assigned),
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID', default=None,
                    repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                ])

    def _run(self, **params):
        assigned = parse_assigned(self, params['assigned'])
        bugdir = self._get_bugdir()
        for bug_id in params['bug-id']:
            bug,dummy_comment = \
                libbe.command.util.bug_comment_from_user_id(bugdir, bug_id)
            if bug.assigned != assigned:
                bug.assigned = assigned
                if bug.status == 'open':
                    bug.status = 'assigned'
        return 0

    def _long_help(self):
        return """
Assign a person to fix a bug.

Assigneds should be the person's Bugs Everywhere identity, the same
string that appears in Creator fields.

Special assigned strings:
  "-"      assign the bug to yourself
  "none"   un-assigns the bug
"""

def parse_assigned(command, assigned):
    """Standard processing for the 'assigned' Argument.
    """
    if assigned == 'none':
        assigned = None
    elif assigned == '-':
        assigned = command._get_user_id()
    return assigned
