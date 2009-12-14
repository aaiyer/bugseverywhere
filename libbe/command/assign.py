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

    >>> import os, sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Assign()
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> cmd.run(bd, {'user-id':u'Fran\xe7ois'}, ['-', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    u'Fran\\xe7ois'

    >>> cmd.run(bd, args=['someone', '/a', '/b'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned
    'someone'
    >>> bd.bug_from_uuid('b').assigned
    'someone'

    >>> cmd.run(bd, args=['none', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').assigned is None
    True
    >>> bd.cleanup()
    """
    
    name = 'assign'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.requires_bugdir = True
        self.args.extend([
                libbe.command.Argument(
                    name='assignee', metavar='ASSIGNEE', default=None,
                    completion_callback=libbe.command.util.complete_assigned),
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID', default=None,
                    repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                ])

    def _run(self, bugdir, **params):
        assignee = params['assignee']
        if assignee == 'none':
            assignee = None
        elif assignee == '-':
            assignee = params['user-id']
        for bug_id in params['bug-id']:
            p = libbe.util.id.parse_user(bugdir, bug_id)
            if p['type'] != 'bug':
                raise libbe.command.UserError(
                    '%s is a %s id, not a bug id' % (bug_id, p['type']))
            if p['bugdir'] != bugdir.uuid:
                raise libbe.command.UserError(
                    "%s doesn't belong to this bugdir (%s)"
                    % (bug_id, bugdir.uuid))
            bug = bugdir.bug_from_uuid(p['bug'])
            if bug.assigned != assignee:
                bug.assigned = assignee

    def _long_help(self):
        return """
Assign a person to fix a bug.

Assignees should be the person's Bugs Everywhere identity, the same
string that appears in Creator fields.

Special assignee strings:
  "-"      assign the bug to yourself
  "none"   un-assigns the bug
"""
