# Copyright (C) 2008-2009 W. Trevor King <wking@drexel.edu>
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
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> from libbe import mapfile
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> print bd.bug_from_shortname("b").status
    closed
    >>> execute (["b"], test=True)
    Removed bug b
    >>> bd._clear_bugs()
    >>> try:
    ...     bd.bug_from_shortname("b")
    ... except KeyError:
    ...     print "Bug not found"
    Bug not found
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
    if len(args) != 1:
        raise cmdutil.UsageError, "Please specify a bug id."
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    bug = bd.bug_from_shortname(args[0])
    bd.remove_bug(bug)
    bd.save()
    print "Removed bug %s" % bug.uuid

def get_parser():
    parser = cmdutil.CmdOptionParser("be remove BUG-ID")
    return parser

longhelp="""
Remove (delete) an existing bug.  Use with caution: if you're not using a
revision control system, there may be no way to recover the lost information.
You should use this command, for example, to get rid of blank or otherwise 
mangled bugs.
"""

def help():
    return get_parser().help_str() + longhelp
