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
"""Close a bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> from libbe import bugdir
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> print bd.bug_from_shortname("a").status
    open
    >>> execute(["a"], test=True)
    >>> bd._clear_bugs()
    >>> print bd.bug_from_shortname("a").status
    closed
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
    if len(args) == 0:
        raise cmdutil.UsageError("Please specify a bug id.")
    if len(args) > 1:
        raise cmdutil.UsageError("Too many arguments.")
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    bug = bd.bug_from_shortname(args[0])
    bug.status = "closed"
    bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be close BUG-ID")
    return parser

longhelp="""
Close the bug identified by BUG-ID.
"""

def help():
    return get_parser().help_str() + longhelp
