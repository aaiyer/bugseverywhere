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
"""Create a new bug"""
from libbe import cmdutil, names, utility
from libbe.bug import new_bug

def execute(args):
    """
    >>> import os, time
    >>> from libbe import tests
    >>> dir = tests.bug_arch_dir()
    >>> os.chdir(dir.dir)
    >>> names.uuid = lambda: "a"
    >>> execute (["this is a test",])
    Created bug with ID a
    >>> bug = list(dir.list())[0]
    >>> bug.summary
    u'this is a test'
    >>> bug.creator = os.environ["LOGNAME"]
    >>> bug.time <= int(time.time())
    True
    >>> bug.severity
    u'minor'
    >>> bug.target == None
    True
    >>> tests.clean_up()
    """
    options, args = get_parser().parse_args(args)
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a summary message")
    dir = cmdutil.bug_tree()
    bug = new_bug(dir)
    bug.summary = args[0]
    bug.save()
    bugs = (dir.list())
    print "Created bug with ID %s" % cmdutil.unique_name(bug, bugs)

def get_parser():
    parser = cmdutil.CmdOptionParser("be new SUMMARY")
    return parser

longhelp="""
Create a new bug, with a new ID.  The summary specified on the commandline
is a string that describes the bug briefly.
"""

def help():
    return get_parser().help_str() + longhelp
