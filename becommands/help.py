# Copyright (C) 2006-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
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
"""Print help for given subcommand"""
from libbe import cmdutil, utility
__desc__ = __doc__

def execute(args, manipulate_encodings=False):
    """
    Print help of specified command (the manipulate_encodings argument
    is ignored).

    >>> execute(["help"])
    Usage: be help [COMMAND]
    <BLANKLINE>
    Options:
      -h, --help  Print a help message
      --complete  Print a list of available completions
    <BLANKLINE>
    Print help for specified command or list of all commands.
    <BLANKLINE>
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) > 1:
        raise cmdutil.UsageError("Too many arguments.")
    if len(args) == 0:
        print cmdutil.help()
    else:
        try:
            print cmdutil.help(args[0])
        except AttributeError:
            print "No help available"    

def get_parser():
    parser = cmdutil.CmdOptionParser("be help [COMMAND]")
    return parser

longhelp="""
Print help for specified command or list of all commands.
"""

def help():
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option, value in cmdutil.option_value_pairs(options, parser):
        if value == "--complete":
            # no argument-options at the moment, so this is future-proofing
            raise cmdutil.GetCompletions()
    if "--complete" in args:
        cmds = [command for command,module in cmdutil.iter_commands()]
        raise cmdutil.GetCompletions(cmds)
