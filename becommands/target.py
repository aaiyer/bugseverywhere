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
"""Show or change a bug's target for fixing"""
from libbe import bugdir
from libbe import cmdutil 
__desc__ = __doc__

def execute(args):
    """
    >>> from libbe import tests
    >>> import os
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> execute(("a",))
    No target assigned.
    >>> execute(("a", "tomorrow"))
    >>> execute(("a",))
    tomorrow
    >>> execute(("a", "none"))
    >>> execute(("a",))
    No target assigned.
    >>> tests.clean_up()
    """
    assert(len(args) in (0, 1, 2))
    if len(args) == 0:
        print help()
        return
    bug = cmdutil.get_bug(args[0])
    if len(args) == 1:
        if bug.target is None:
            print "No target assigned."
        else:
            print bug.target
    elif len(args) == 2:
        if args[1] == "none":
            bug.target = None
        else:
            bug.target = args[1]
        bug.save()


def help():
    return """be target bug-id [target]

Show or change a bug's target for fixing.  

If no target is specified, the current value is printed.  If a target 
is specified, it will be assigned to the bug.

Targets are freeform; any text may be specified.  They will generally be
milestone names or release numbers.

The value "none" can be used to unset the target.
"""
