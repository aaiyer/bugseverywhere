# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Change tree settings"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute(["target"])
    None
    >>> execute(["target", "tomorrow"])
    >>> execute(["target"])
    tomorrow
    >>> execute(["target", "none"])
    >>> execute(["target"])
    None
    """
    options, args = get_parser().parse_args(args)
    if len(args) > 2:
        help()
        raise cmdutil.UserError("Too many arguments.")
    bd = bugdir.BugDir(loadNow=True)
    if len(args) == 0:
        keys = bd.settings.keys()
        keys.sort()
        for key in keys:
            print "%16s: %s" % (key, bd.settings[key])
    elif len(args) == 1:
        print bd.settings.get(args[0])
    else:
        if args[1] != "none":
            bd.settings[args[0]] = args[1]
        else:
            del bd.settings[args[0]]
        bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be set [name] [value]")
    return parser

longhelp="""
Show or change per-tree settings. 

If name and value are supplied, the name is set to a new value.
If no value is specified, the current value is printed.
If no arguments are provided, all names and values are listed. 

Interesting settings are:
rcs_name
  The name of the revision control system.  "Arch" and "None" are supported.
target
  The current development goal 

To unset a setting, set it to "none".
"""

def help():
    return get_parser().help_str() + longhelp
