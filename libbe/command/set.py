# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
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


import textwrap

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.util
from libbe.storage.util.settings_object import EMPTY


class Set (libbe.command.Command):
    """Change bug directory settings

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Set(ui=ui)

    >>> ret = ui.run(cmd, args=['target'])
    None
    >>> ret = ui.run(cmd, args=['target', 'abcdefg'])
    >>> ret = ui.run(cmd, args=['target'])
    abcdefg
    >>> ret = ui.run(cmd, args=['target', 'none'])
    >>> ret = ui.run(cmd, args=['target'])
    None
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'set'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.args.extend([
                libbe.command.Argument(
                    name='setting', metavar='SETTING', optional=True,
                    completion_callback=complete_bugdir_settings),
                libbe.command.Argument(
                    name='value', metavar='VALUE', optional=True)
                ])

    def _run(self, **params):
        bugdir = self._get_bugdir()
        if params['setting'] == None:
            keys = bugdir.settings_properties
            keys.sort()
            for key in keys:
                print >> self.stdout, \
                    '%16s: %s' % (key, _value_string(bugdir, key))
            return 0
        if params['setting'] not in bugdir.settings_properties:
            msg = 'Invalid setting %s\n' % params['setting']
            msg += 'Allowed settings:\n  '
            msg += '\n  '.join(bugdir.settings_properties)
            raise libbe.command.UserError(msg)
        if params['value'] == None:
            print _value_string(bugdir, params['setting'])
        else:
            if params['value'] == 'none':
                params['value'] = EMPTY
            old_setting = bugdir.settings.get(params['setting'])
            attr = bugdir._setting_name_to_attr_name(params['setting'])
            setattr(bugdir, attr, params['value'])
        return 0

    def _long_help(self):
        return """
Show or change per-tree settings.

If name and value are supplied, the name is set to a new value.
If no value is specified, the current value is printed.
If no arguments are provided, all names and values are listed.

To unset a setting, set it to "none".

Allowed settings are:

%s

Note that this command does not provide a good interface for some of
these settings (yet!).  You may need to edit the bugdir settings file
(`.be/<bugdir>/settings`) manually.  Examples for each troublesome
setting are given below.

Add the following lines to override the default severities and use
your own:

  severities:
    - - target
      - The issue is a target or milestone, not a bug.
    - - wishlist
      - A feature that could improve usefulness, but not a bug.

You may add as many name/description pairs as you wish to have; they
are sorted in order from least important at the top, to most important
at the bottom.  The target severity gets special handling by `be
target`.

Note that the values here _override_ the defaults. That means that if
you like the defaults, and wish to keep them, you will have to copy
them here before adding any of your own.  See `be severity --help` for
the current list.

Add the following lines to override the default statuses and use your
own:

  active_status:
    - - unconfirmed
      - A possible bug which lacks independent existance confirmation.
    - - open
      - A working bug that has not been assigned to a developer.

  inactive_status:
    - - closed
      - The bug is no longer relevant.
    - - fixed
      - The bug should no longer occur.

You may add as many name/description pairs as you wish to have; they
are sorted in order from most important at the top, to least important
at the bottom.

Note that the values here _override_ the defaults. That means that if
you like the defaults, and wish to keep them, you will have to copy
them here before adding any of your own.  See `be status --help` for
the current list.
""" % ('\n'.join(get_bugdir_settings()),)

def get_bugdir_settings():
    settings = []
    for s in libbe.bugdir.BugDir.settings_properties:
        settings.append(s)
    settings.sort()
    documented_settings = []
    for s in settings:
        set = getattr(libbe.bugdir.BugDir, s)
        dstr = set.__doc__.strip()
        # per-setting comment adjustments
        if s == 'vcs_name':
            lines = dstr.split('\n')
            while lines[0].startswith('This property defaults to') == False:
                lines.pop(0)
            assert len(lines) != None, \
                'Unexpected vcs_name docstring:\n  "%s"' % dstr
            lines.insert(
                0, 'The name of the revision control system to use.\n')
            dstr = '\n'.join(lines)
        doc = textwrap.wrap(dstr, width=70, initial_indent='  ',
                            subsequent_indent='  ')
        documented_settings.append('%s\n%s' % (s, '\n'.join(doc)))
    return documented_settings

def _value_string(bugdir, setting):
    val = bugdir.settings.get(setting, EMPTY)
    if val == EMPTY:
        default = getattr(bugdir, bugdir._setting_name_to_attr_name(setting))
        if default not in [None, EMPTY]:
            val = 'None (%s)' % default
        else:
            val = None
    return str(val)

def complete_bugdir_settings(command, argument, fragment=None):
    """
    List possible command completions for fragment.

    Neither the command nor argument arguments are used.
    """
    return libbe.bugdir.BugDir.settings_properties
