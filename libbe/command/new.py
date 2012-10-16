# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Andrew Cooper <andrew.cooper@hkcreations.org>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Niall Douglas (s_sourceforge@nedprod.com) <spam@spamtrap.com>
#                         W. Trevor King <wking@tremily.us>
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

from .assign import parse_assigned as _parse_assigned


class New (libbe.command.Command):
    """Create a new bug

    >>> import os
    >>> import sys
    >>> import time
    >>> import libbe.bugdir
    >>> import libbe.util.id
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = New()

    >>> uuid_gen = libbe.util.id.uuid_gen
    >>> libbe.util.id.uuid_gen = lambda: 'X'
    >>> ui._user_id = u'Fran\\xe7ois'
    >>> options = {'assigned': 'none'}
    >>> ret = ui.run(cmd, options=options, args=['this is a test',])
    Created bug with ID abc/X
    >>> libbe.util.id.uuid_gen = uuid_gen
    >>> bd.flush_reload()
    >>> bug = bd.bug_from_uuid('X')
    >>> print bug.summary
    this is a test
    >>> bug.creator
    u'Fran\\xe7ois'
    >>> bug.reporter
    u'Fran\\xe7ois'
    >>> bug.time <= int(time.time())
    True
    >>> print bug.severity
    minor
    >>> print bug.status
    open
    >>> print bug.assigned
    None
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'new'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='reporter', short_name='r',
                    help='The user who reported the bug',
                    arg=libbe.command.Argument(
                        name='reporter', metavar='NAME')),
                libbe.command.Option(name='creator', short_name='c',
                    help='The user who created the bug',
                    arg=libbe.command.Argument(
                        name='creator', metavar='NAME')),
                libbe.command.Option(name='assigned', short_name='a',
                    help='The developer in charge of the bug',
                    arg=libbe.command.Argument(
                        name='assigned', metavar='NAME',
                        completion_callback=libbe.command.util.complete_assigned)),
                libbe.command.Option(name='status', short_name='t',
                    help='The bug\'s status level',
                    arg=libbe.command.Argument(
                        name='status', metavar='STATUS',
                        completion_callback=libbe.command.util.complete_status)),
                libbe.command.Option(name='severity', short_name='s',
                    help='The bug\'s severity',
                    arg=libbe.command.Argument(
                        name='severity', metavar='SEVERITY',
                        completion_callback=libbe.command.util.complete_severity)),
                libbe.command.Option(name='bugdir', short_name='b',
                    help='Short bugdir UUID for the new bug.  You '
                    'only need to set this if you have multiple bugdirs in '
                    'your repository.',
                    arg=libbe.command.Argument(
                        name='bugdir', metavar='ID', default=None,
                        completion_callback=libbe.command.util.complete_bugdir_id)),
                libbe.command.Option(name='full-uuid', short_name='f',
                    help='Print the full UUID for the new bug')
                ])
        self.args.extend([
                libbe.command.Argument(name='summary', metavar='SUMMARY')
                ])

    def _run(self, **params):
        if params['summary'] == '-': # read summary from stdin
            summary = self.stdin.readline()
        else:
            summary = params['summary']
        storage = self._get_storage()
        bugdirs = self._get_bugdirs()
        if params['bugdir']:
            bugdir = bugdirs[bugdir]
        elif len(bugdirs) == 1:
            bugdir = bugdirs.values()[0]
        else:
            raise libbe.command.UserError(
                'Ambiguous bugdir {}'.format(sorted(bugdirs.values())))
        storage.writeable = False
        bug = bugdir.new_bug(summary=summary.strip())
        if params['creator'] != None:
            bug.creator = params['creator']
        else:
            bug.creator = self._get_user_id()
        if params['reporter'] != None:
            bug.reporter = params['reporter']
        else:
            bug.reporter = bug.creator
        if params['assigned'] != None:
            bug.assigned = _parse_assigned(self, params['assigned'])
        if params['status'] != None:
            bug.status = params['status']
        if params['severity'] != None:
            bug.severity = params['severity']
        storage.writeable = True
        bug.save()
        if params['full-uuid']:
            bug_id = bug.id.long_user()
        else:
            bug_id = bug.id.user()
        self.stdout.write('Created bug with ID %s\n' % (bug_id))
        return 0

    def _long_help(self):
        return """
Create a new bug, with a new ID.  The summary specified on the
commandline is a string (only one line) that describes the bug briefly
or "-", in which case the string will be read from stdin.
"""
