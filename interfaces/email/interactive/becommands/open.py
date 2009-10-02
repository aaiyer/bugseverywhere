# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Marien Zwart <marienz@gentoo.org>
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
"""Re-open a bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> print bd.bug_from_shortname("b").status
    closed
    >>> execute(["b"], manipulate_encodings=False)
    >>> bd._clear_bugs()
    >>> print bd.bug_from_shortname("b").status
    open
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==False})
    if len(args) == 0:
        raise cmdutil.UsageError, "Please specify a bug id."
    if len(args) > 1:
        raise cmdutil.UsageError, "Too many arguments."
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bug = cmdutil.bug_from_shortname(bd, args[0])
    bug.status = "open"

def get_parser():
    parser = cmdutil.CmdOptionParser("be open BUG-ID")
    return parser

longhelp="""
Mark a bug as 'open'.
"""

def help():
    return get_parser().help_str() + longhelp
