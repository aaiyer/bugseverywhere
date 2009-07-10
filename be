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


import sys
from libbe import cmdutil, _version

__doc__ == cmdutil.help()

if len(sys.argv) == 1 or sys.argv[1] in ('--help', '-h'):
    print cmdutil.help()
elif sys.argv[1] == '--complete':
    for command, module in cmdutil.iter_commands():
        print command
    print '\n'.join(["--help","--complete","--options","--version"])
elif sys.argv[1] == '--version':
    print _version.version_info["revision_id"]
else:
    try:
        sys.exit(cmdutil.execute(sys.argv[1], sys.argv[2:]))
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
        print "\nArgs:", sys.argv[1:]
        print cmdutil.help(sys.argv[1])
        sys.exit(1)
    except cmdutil.UserError, e:
        print "ERROR:"
        print e
        sys.exit(1)
