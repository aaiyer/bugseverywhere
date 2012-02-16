# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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

import sys

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.util
import libbe.storage
import libbe.ui.util.editor


class Commit (libbe.command.Command):
    """Commit the currently pending changes to the repository

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False, versioned=True)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Commit(ui=ui)

    >>> bd.extra_strings = ['hi there']
    >>> bd.flush_reload()
    >>> ui.run(cmd, args=['Making a commit']) # doctest: +ELLIPSIS
    Committed ...
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'commit'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='body', short_name='b',
                    help='Provide the detailed body for the commit message.  In the special case that FILE == "EDITOR", spawn an editor to enter the body text (in which case you cannot use stdin for the summary)',
                    arg=libbe.command.Argument(name='body', metavar='FILE',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='allow-empty', short_name='a',
                                     help='Allow empty commits'),
                 ])
        self.args.extend([
                libbe.command.Argument(
                    name='summary', metavar='SUMMARY', default=None,
                    optional=True),
                ])

    def _run(self, **params):
        if params['summary'] == '-': # read summary from stdin
            assert params['body'] != 'EDITOR', \
                'Cannot spawn and editor when the summary is using stdin.'
            summary = sys.stdin.readline()
        else:
            summary = params['summary']
            if summary == None and params['body'] == None:
                params['body'] = 'EDITOR'
        storage = self._get_storage()
        if params['body'] == None:
            body = None
        elif params['body'] == 'EDITOR':
            body = libbe.ui.util.editor.editor_string(
                'Please enter your commit message above')
        else:
            self._check_restricted_access(storage, params['body'])
            body = libbe.util.encoding.get_file_contents(
                params['body'], decode=True)
        if summary == None:  # use the first body line as the summary
            if body == None:
                raise libbe.command.UserError(
                    'cannot commit without a summary')
            lines = body.splitlines()
            summary = lines[0]
            body = '\n'.join(lines[1:]).strip() + '\n'
        try:
            revision = storage.commit(summary, body=body,
                                      allow_empty=params['allow-empty'])
            print >> self.stdout, 'Committed %s' % revision
        except libbe.storage.EmptyCommit, e:
            print >> self.stdout, e
            return 1

    def _long_help(self):
        return """
Commit the current repository status.

The summary specified on the commandline is a string (only one line)
that describes the commit briefly or "-", in which case the string
will be read from stdin.  If no summary is given, the first line from
the body message is used instead.  If no summary or body is given, we
spawn an editor without needing the special "EDITOR" value for the
"--body" option.
"""
