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

"""Compare bug reports with older tree"""
from libbe import cmdutil, bugdir, diff
import os
__desc__ = __doc__

def execute(args):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> original = bd.rcs.commit("Original status")
    >>> bug = bd.bug_from_uuid("a")
    >>> bug.status = "closed"
    >>> bd.save()
    >>> changed = bd.rcs.commit("Closed bug a")
    >>> os.chdir(bd.root)
    >>> if bd.rcs.versioned == True:
    ...     execute([original])
    ... else:
    ...     print "a:cm: Bug A\\nstatus: open -> closed\\n"
    Modified bug reports:
    a:cm: Bug A
      status: open -> closed
    <BLANKLINE>
    """
    options, args = get_parser().parse_args(args)
    if len(args) == 0:
        revision = None
    if len(args) == 1:
        revision = args[0]
    if len(args) > 1:
        help()
        raise cmdutil.UserError("Too many arguments.")
    bd = bugdir.BugDir(from_disk=True)
    if bd.rcs.versioned == False:
        print "This directory is not revision-controlled."
    else:
        old_bd = bd.duplicate_bugdir(revision)
        r,m,a = diff.diff(old_bd, bd)
        diff.diff_report((r,m,a), bd)
        bd.remove_duplicate_bugdir()

def get_parser():
    parser = cmdutil.CmdOptionParser("be diff [specifier]")
    return parser

longhelp="""
Uses the RCS to compare the current tree with a previous tree, and prints
a pretty report.  If specifier is given, it is a specifier for the particular
previous tree to use.  Specifiers are specific to their RCS.  

For Arch: a fully-qualified revision name
"""

def help():
    return get_parser().help_str() + longhelp
