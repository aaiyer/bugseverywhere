# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Chris Ball <cjb@laptop.org>
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
"""Change tree settings"""
import textwrap
from libbe import cmdutil, bugdir, rcs, settings_object
__desc__ = __doc__

def _value_string(bd, setting):
    val = bd.settings.get(setting, settings_object.EMPTY)
    if val == settings_object.EMPTY:
        default = getattr(bd, bd._setting_name_to_attr_name(setting))
        if default not in [None, settings_object.EMPTY]:
            val = "None (%s)" % default
        else:
            val = None
    return str(val)

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> execute(["target"], manipulate_encodings=False)
    None
    >>> execute(["target", "tomorrow"], manipulate_encodings=False)
    >>> execute(["target"], manipulate_encodings=False)
    tomorrow
    >>> execute(["target", "none"], manipulate_encodings=False)
    >>> execute(["target"], manipulate_encodings=False)
    None
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) > 2:
        raise cmdutil.UsageError, "Too many arguments"
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    if len(args) == 0:
        keys = bd.settings_properties
        keys.sort()
        for key in keys:
            print "%16s: %s" % (key, _value_string(bd, key))
    elif len(args) == 1:
        print _value_string(bd, args[0])
    else:
        if args[1] == "none":
            setattr(bd, args[0], settings_object.EMPTY)
        else:
            if args[0] not in bd.settings_properties:
                msg = "Invalid setting %s\n" % args[0]
                msg += 'Allowed settings:\n  '
                msg += '\n  '.join(bd.settings_properties)
                raise cmdutil.UserError(msg)
            old_setting = bd.settings.get(args[0])
            setattr(bd, args[0], args[1])

def get_parser():
    parser = cmdutil.CmdOptionParser("be set [NAME] [VALUE]")
    return parser

def get_bugdir_settings():
    settings = []
    for s in bugdir.BugDir.settings_properties:
        settings.append(s)
    settings.sort()
    documented_settings = []
    for s in settings:
        set = getattr(bugdir.BugDir, s)
        dstr = set.__doc__.strip()
        # per-setting comment adjustments
        if s == "rcs_name":
            lines = dstr.split('\n')
            while lines[0].startswith("This property defaults to") == False:
                lines.pop(0)
            assert len(lines) != None, \
                "Unexpected rcs_name docstring:\n  '%s'" % dstr
            lines.insert(
                0, "The name of the revision control system to use.\n")
            dstr = '\n'.join(lines)
        doc = textwrap.wrap(dstr, width=70, initial_indent='  ',
                            subsequent_indent='  ')
        documented_settings.append("%s\n%s" % (s, '\n'.join(doc)))
    return documented_settings

longhelp="""
Show or change per-tree settings. 

If name and value are supplied, the name is set to a new value.
If no value is specified, the current value is printed.
If no arguments are provided, all names and values are listed. 

To unset a setting, set it to "none".

Allowed settings are:

%s""" % ('\n'.join(get_bugdir_settings()),)

def help():
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option, value in cmdutil.option_value_pairs(options, parser):
        if value == "--complete":
            # no argument-options at the moment, so this is future-proofing
            raise cmdutil.GetCompletions()
    for pos,value in enumerate(args):
        if value == "--complete":
            if pos == 0: # first positional argument is a setting name
                props = bugdir.BugDir.settings_properties
                raise cmdutil.GetCompletions(props)
            raise cmdutil.GetCompletions() # no positional arguments for list
