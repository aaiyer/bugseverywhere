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
"""Remove (delete) a bug and its comments"""
from libbe import cmdutil
__desc__ = __doc__

def execute(args):
    """
    >>> import os
    >>> from libbe import bugdir, mapfile
    >>> dir = bugdir.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> dir.get_bug("b").status
    u'closed'
    >>> execute (["b"])
    Removed bug b
    >>> try:
    ...     dir.get_bug("b")
    ... except mapfile.NoSuchFile:
    ...     print "Bug not found"
    Bug not found
    """
    options, args = get_parser().parse_args(args)
    if len(args) != 1:
        raise cmdutil.UserError("Please specify a bug id.")
    bug = cmdutil.get_bug(args[0])
    bug.remove()
    print "Removed bug %s" % bug.uuid

def get_parser():
    parser = cmdutil.CmdOptionParser("be remove bug-id")
    return parser

longhelp="""
Remove (delete) an existing bug.  Use with caution: if you're not using a
revision control system, there may be no way to recover the lost information.
You should use this command, for example, to get rid of blank or otherwise 
mangled bugs.
"""

def help():
    return get_parser().help_str() + longhelp
