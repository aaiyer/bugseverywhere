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
import becommands

__doc__ == cmdutil.help()

if len(sys.argv) == 1 or sys.argv[1] in ('--help', '-h'):
    print cmdutil.help()
else:
    try:
        try:
            sys.exit(cmdutil.execute(sys.argv[1], sys.argv[2:]))
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
