# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         Tim Guirgies <lt.infiltrator@gmail.com>
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
import libbe.bug
import libbe.command
import libbe.command.util


class Severity (libbe.command.Command):
    """Change a bug's severity level

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Severity(ui=ui)

    >>> bd.bug_from_uuid('a').severity
    'minor'
    >>> ret = ui.run(cmd, args=['wishlist', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').severity
    u'wishlist'
    >>> ret = ui.run(cmd, args=['none', '/a'])
    Traceback (most recent call last):
    UserError: Invalid severity level: none
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'severity'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.args.extend([
                libbe.command.Argument(
                    name='severity', metavar='SEVERITY', default=None,
                    completion_callback=libbe.command.util.complete_severity),
                libbe.command.Argument(
                    name='bug-id', metavar='BUG-ID', default=None,
                    repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                ])

    def _run(self, **params):
        bugdirs = self._get_bugdirs()
        for bug_id in params['bug-id']:
            bugdir,bug,comment = (
                libbe.command.util.bugdir_bug_comment_from_user_id(
                    bugdirs, bug_id))
            if bug.severity != params['severity']:
                try:
                    bug.severity = params['severity']
                except ValueError, e:
                    if e.name != 'severity':
                        raise e
                    raise libbe.command.UserError(
                        'Invalid severity level: %s' % e.value)
        return 0

    def _long_help(self):
        try: # See if there are any per-tree severity configurations
            bugdirs = self._get_bugdirs()
        except NotImplementedError:
            pass # No tree, just show the defaults
        longest_severity_len = max([len(s) for s in libbe.bug.severity_values])
        severity_levels = []
        for severity in libbe.bug.severity_values :
            description = libbe.bug.severity_description[severity]
            s = '%*s : %s' % (longest_severity_len, severity, description)
            severity_levels.append(s)
        ret = """
Show or change a bug's severity level.

If no severity is specified, the current value is printed.  If a severity level
is specified, it will be assigned to the bug.

Severity levels are:
  %s

You can overide the list of allowed severities on a per-repository
basis.  See `be set --help` for details.
""" % ('\n  '.join(severity_levels))
        return ret
