# Copyright (C) 2006 Thomas Gerigk
# <tgerigk@gmx.de>
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
"""Print help for given subcommand"""
from libbe import bugdir, cmdutil, names, utility

def execute(args):
    """
    Print help of specified command.
    """
    options, args = get_parser().parse_args(args)
    if len(args) > 1:
        raise cmdutil.UserError("Too many arguments.")
    if len(args) == 0:
        cmdutil.print_command_list()
    else:
        try:
            print cmdutil.help(args[0])
        except AttributeError:
            print "No help available"
    
    return


def get_parser():
    parser = cmdutil.CmdOptionParser("be help [COMMAND]")
    return parser

longhelp="""
Print help for specified command or list of all commands.
"""

def help():
    return get_parser().help_str() + longhelp
