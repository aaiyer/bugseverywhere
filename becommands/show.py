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
from libbe import bugdir, cmdutil, utility
import os

def execute(args):
    options, args = get_parser().parse_args(args)
    if len(args) !=1:
        raise cmdutil.UserError("Please specify a bug id.")
    bug_dir = cmdutil.bug_tree()
    bug = cmdutil.get_bug(args[0], bug_dir)
    print cmdutil.bug_summary(bug, list(bug_dir.list())).rstrip("\n")
    if bug.time is None:
        time_str = "(Unknown time)"
    else:
        time_str = "%s (%s)" % (utility.handy_time(bug.time), 
                                utility.time_to_str(bug.time))
    print "Created: %s" % time_str
    for comment in bug.list_comments():
        print "--------- Comment ---------"
        print "From: %s" % comment.From
        print "Date: %s\n" % utility.time_to_str(comment.date)
        print comment.body.rstrip('\n')

def get_parser():
    parser = cmdutil.CmdOptionParser("be show bug-id")
    return parser

longhelp="""
Show all information about a bug.
"""

def help():
    return get_parser().help_str() + longhelp

