#!/usr/bin/env python
# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Chris Ball <cjb@laptop.org>
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
#                         W. Trevor King <wking@drexel.edu>
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

import os
import sys

from libbe import cmdutil, _version

__doc__ = cmdutil.help()

usage = "be [options] [command] [command_options ...] [command_args ...]"

parser = cmdutil.CmdOptionParser(usage)
parser.command = "be"
parser.add_option("--version", action="store_true", dest="version",
                  help="Print version string and exit.")
parser.add_option("-d", "--dir", dest="dir", metavar="DIR",
                  help="Run this command from DIR instead of the current directory.")

try:
    options,args = parser.parse_args()
    for option,value in cmdutil.option_value_pairs(options, parser):
        if value == "--complete":
            if option == "dir":
                if len(args) == 0:
                    args = ["."]
                paths = cmdutil.complete_path(args[0])
                raise cmdutil.GetCompletions(paths)
except cmdutil.GetHelp:
    print cmdutil.help(parser=parser)
    sys.exit(0)
except cmdutil.GetCompletions, e:
    print '\n'.join(e.completions)
    sys.exit(0)

if options.version == True:
    print _version.version_info["revision_id"]
    sys.exit(0)
if options.dir != None:
    os.chdir(options.dir)

try:
    if len(args) == 0:
        raise cmdutil.UsageError, "must supply a command"
    sys.exit(cmdutil.execute(args[0], args[1:]))
except cmdutil.GetHelp:
    print cmdutil.help(sys.argv[1])
    sys.exit(0)
except cmdutil.GetCompletions, e:
    print '\n'.join(e.completions)
    sys.exit(0)
except cmdutil.UnknownCommand, e:
    print e
    sys.exit(1)
except cmdutil.UsageError, e:
    print "Invalid usage:", e
    if len(args) == 0:
        print cmdutil.help(parser=parser)
    else:
        print "\nArgs:", args
        print cmdutil.help(sys.argv[1])
    sys.exit(1)
except cmdutil.UserError, e:
    print "ERROR:"
    print e
    sys.exit(1)
