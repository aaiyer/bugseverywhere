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

import libbe
import libbe.command
import libbe.command.util


class Assign (libbe.command.Command):
    """Assign an individual or group to fix a bug

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Assign()
    >>> cmd._storage = bd.storage
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> ret = cmd.run({'user-id':u'Fran\xe7ois'}, ['-', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    u'Fran\\xe7ois'

    >>> ret = cmd.run(args=['someone', '/a', '/b'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    'someone'
    >>> bd.bug_from_uuid('b').assigned
    'someone'

    >>> ret = cmd.run(args=['none', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned is None
    True
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
        assigned = params['assigned']
        if assigned == 'none':
            assigned = None
        elif assigned == '-':
            assigned = self._get_user_id()
        bugdir = self._get_bugdir()
        for bug_id in params['bug-id']:
            bug,dummy_comment = \
                libbe.command.util.bug_comment_from_user_id(bugdir, bug_id)
            if bug.assigned != assigned:
                bug.assigned = assigned
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
