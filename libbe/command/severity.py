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
import libbe.bug
import libbe.command
import libbe.command.util

class Severity (libbe.command.Command):
    """Change a bug's severity level

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Severity()
    >>> cmd._storage = bd.storage
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> bd.bug_from_uuid('a').severity
    'minor'
    >>> ret = cmd.run(args=['wishlist', '/a'])
    >>> bd.flush_reload()
    >>> bd.bug_from_uuid('a').severity
    'wishlist'
    >>> ret = cmd.run(args=['none', '/a'])
    Traceback (most recent call last):
    UserError: Invalid severity level: none
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
        bugdir = self._get_bugdir()
        for bug_id in params['bug-id']:
            bug,dummy_comment = \
                libbe.command.util.bug_comment_from_user_id(bugdir, bug_id)
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
        ret = ["""
Show or change a bug's severity level.

If no severity is specified, the current value is printed.  If a severity level
is specified, it will be assigned to the bug.

Severity levels are:
"""]
        try: # See if there are any per-tree severity configurations
            bd = self._get_bugdir()
        except NotImplementedError:
            pass # No tree, just show the defaults
        longest_severity_len = max([len(s) for s in libbe.bug.severity_values])
        for severity in bug.severity_values :
            description = bug.severity_description[severity]
            ret.append('%*s : %s\n' \
                % (longest_severity_len, severity, description))
        return ''.join(ret)
