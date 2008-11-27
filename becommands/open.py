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
"""Re-open a bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> print bd.bug_from_shortname("b").status
    closed
    >>> execute(["b"], test=True)
    >>> bd._clear_bugs()
    >>> print bd.bug_from_shortname("b").status
    open
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) == 0:
        raise cmdutil.UsageError, "Please specify a bug id."
    if len(args) > 1:
        raise cmdutil.UsageError, "Too many arguments."
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    bug = bd.bug_from_shortname(args[0])
    bug.status = "open"
    bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be open BUG-ID")
    return parser

longhelp="""
Mark a bug as 'open'.
"""

def help():
    return get_parser().help_str() + longhelp
