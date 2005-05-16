#!/usr/bin/env python
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


from libbe.cmdutil import *
from libbe.bugdir import tree_root, create_bug_dir
from libbe import names, plugin, cmdutil
import sys
import os
import becommands.severity
import becommands.list
import becommands.show
import becommands.set_root
import becommands.new
import becommands.close
import becommands.open
import becommands.inprogress
__doc__ = """Bugs Everywhere - Distributed bug tracking

Supported becommands
 set-root: assign the root directory for bug tracking
      new: Create a new bug
     list: list bugs
     show: show a particular bug
    close: close a bug
     open: re-open a bug
 severity: %s

Unimplemented becommands
  comment: append a comment to a bug
""" % becommands.severity.__desc__



if len(sys.argv) == 1:
    cmdlist = []
    print """Bugs Everywhere - Distributed bug tracking
    
Supported commands"""
    for name, module in cmdutil.iter_commands():
        cmdlist.append((name, module.__doc__))
    for name, desc in cmdlist:
        print "be %s\n    %s" % (name, desc)
else:
    try:
        try:
            sys.exit(execute(sys.argv[1], sys.argv[2:]))
        except KeyError, e:
            raise UserError("Unknown command \"%s\"" % e.args[0])
        except cmdutil.GetHelp:
            print cmdutil.help(sys.argv[1])
            sys.exit(0)
        except cmdutil.UsageError:
            print cmdutil.help(sys.argv[1])
            sys.exit(1)
    except UserError, e:
        print e
        sys.exit(1)
