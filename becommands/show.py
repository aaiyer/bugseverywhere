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
"""Show a particular bug"""
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute (["a",], test=True)
              ID : a
      Short name : a
        Severity : minor
          Status : open
        Assigned : 
          Target : 
         Creator : John Doe <jdoe@example.com>
         Created : Wed, 31 Dec 1969 19:00 (Thu, 01 Jan 1970 00:00:00 +0000)
    Bug A
    <BLANKLINE>
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
    if len(args) == 0:
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    for bugid in args:
        bug = bd.bug_from_shortname(bugid)
        print bug.string(show_comments=True)
        if bugid != args[-1]:
            print "" # add a blank line between bugs

def get_parser():
    parser = cmdutil.CmdOptionParser("be show BUG-ID [BUG-ID ...]")
    return parser

longhelp="""
Show all information about a bug.
"""

def help():
    return get_parser().help_str() + longhelp
