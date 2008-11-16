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
from libbe import bugdir, diff, cmdutil
import os
__desc__ = __doc__

def execute(args):
    options, args = get_parser().parse_args(args)
    if len(args) == 0:
        spec = None
    elif len(args) == 1:
        spec = args[0]
    else:
        raise cmdutil.UsageError
    tree = bugdir.tree_root(".")
    if tree.rcs_name == "None":
        print "This directory is not revision-controlled."
    else:
        diff.diff_report(diff.reference_diff(tree, spec), tree)


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
