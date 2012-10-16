# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Thomas Gerigk <tgerigk@gmx.de>
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


class Remove (libbe.command.Command):
    """Remove (delete) a bug and its comments

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Remove(ui=ui)

    >>> print bd.bug_from_uuid('b').status
    closed
    >>> ret = ui.run(cmd, args=['/b'])
    Removed bug abc/b
    >>> bd.flush_reload()
    >>> try:
    ...     bd.bug_from_uuid('b')
    ... except libbe.bugdir.NoBugMatches:
    ...     print 'Bug not found'
    Bug not found
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'remove'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.args.extend([
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID', default=None,
                    repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                ])

    def _run(self, **params):
        bugdirs = self._get_bugdirs()
        user_ids = []
        for bug_id in params['bug-id']:
            bugdir,bug,comment = (
                libbe.command.util.bugdir_bug_comment_from_user_id(
                    bugdirs, bug_id))
            user_ids.append(bug.id.user())
            bugdir.remove_bug(bug)
        if len(user_ids) == 1:
            print >> self.stdout, 'Removed bug %s' % user_ids[0]
        else:
            print >> self.stdout, 'Removed bugs %s' % ', '.join(user_ids)
        return 0

    def _long_help(self):
        return """
Remove (delete) existing bugs.  Use with caution: if you're not using
a revision control system, there may be no way to recover the lost
information.  You should use this command, for example, to get rid of
blank or otherwise mangled bugs.
"""
