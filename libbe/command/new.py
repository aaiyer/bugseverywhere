# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
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


class New (libbe.command.Command):
    """Create a new bug

    >>> import os
    >>> import sys
    >>> import time
    >>> import libbe.bugdir
    >>> import libbe.util.id
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = New()
    >>> cmd._storage = bd.storage
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> uuid_gen = libbe.util.id.uuid_gen
    >>> libbe.util.id.uuid_gen = lambda: 'X'
    >>> ret = cmd.run(args=['this is a test',])
    Created bug with ID abc/X
    >>> libbe.util.id.uuid_gen = uuid_gen
    >>> bd.flush_reload()
    >>> bug = bd.bug_from_uuid('X')
    >>> print bug.summary
    this is a test
    >>> bug.time <= int(time.time())
    True
    >>> print bug.severity
    minor
    >>> print bug.status
    open
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
                libbe.command.Option(name='assigned', short_name='a',
                    help='The developer in charge of the bug',
                    arg=libbe.command.Argument(
                        name='assigned', metavar='NAME',
                        completion_callback=libbe.command.util.complete_assigned)),
                ])
        self.args.extend([
                libbe.command.Argument(name='summary', metavar='SUMMARY')
                ])

    def _run(self, **params):
        if params['summary'] == '-': # read summary from stdin
            summary = self.stdin.readline()
        else:
            summary = params['summary']
        bugdir = self._get_bugdir()
        bug = bugdir.new_bug(summary=summary.strip())
        if params['reporter'] != None:
            bug.reporter = params['reporter']
        else:
            bug.reporter = bug.creator
        if params['assigned'] != None:
            bug.assigned = params['assigned']
        print >> self.stdout, 'Created bug with ID %s' % bug.id.user()
        return 0

    def _long_help(self):
        return """
Create a new bug, with a new ID.  The summary specified on the
commandline is a string (only one line) that describes the bug briefly
or "-", in which case the string will be read from stdin.
"""
