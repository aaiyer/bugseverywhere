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
"""List bugs"""
from libbe import cmdutil, names
from libbe.bug import cmp_severity, cmp_time
import os
def execute(args):
    options, args = get_parser().parse_args(args)
    if len(args) > 0:
        raise cmdutil.UsageError
    active = True
    severity = ("minor", "serious", "critical", "fatal")
    if options.wishlist:
        severity = ("wishlist",)
    if options.closed:
        active = False
    tree = cmdutil.bug_tree()
    current_id = names.creator()
    def filter(bug):
        if options.mine and bug.assigned != current_id:
            return False
        if options.cur_target:
            if tree.target is None or bug.target != tree.target:
                return False
        if active is not None:
            if bug.active != active:
                return False
        if bug.severity not in severity:
            return False
        return True

    all_bugs = list(tree.list())
    bugs = [b for b in all_bugs if filter(b) ]
    if len(bugs) == 0:
        print "No matching bugs found"
    
    my_target_bugs = []
    other_target_bugs = []
    unassigned_target_bugs = []
    my_bugs = []
    other_bugs = []
    unassigned_bugs = []
    if tree.target is not None:
        for bug in bugs:
            if bug.target != tree.target:
                continue
            if bug.assigned == current_id:
                my_target_bugs.append(bug)
            elif bug.assigned is None:
                unassigned_target_bugs.append(bug)
            else:
                other_target_bugs.append(bug)

    for bug in bugs:
        if tree.target is not None and bug.target == tree.target:
            continue
        if bug.assigned == current_id:
            my_bugs.append(bug)
        elif bug.assigned is None:
            unassigned_bugs.append(bug)
        else:
            other_bugs.append(bug)

    def list_bugs(cur_bugs, title, no_target=False):
        cur_bugs.sort(cmp_time)
        cur_bugs.sort(cmp_severity)
        if len(cur_bugs) > 0:
            print cmdutil.underlined(title)
            for bug in cur_bugs:
                print cmdutil.bug_summary(bug, all_bugs, no_target=no_target,
                                          shortlist=True),
    
    list_bugs(my_target_bugs, 
              "Bugs assigned to you for target %s" % tree.target, 
              no_target=True)
    list_bugs(unassigned_target_bugs, 
              "Unassigned bugs for target %s" % tree.target, no_target=True)
    list_bugs(other_target_bugs, 
              "Bugs assigned to others for target %s" % tree.target, 
              no_target=True)
    list_bugs(my_bugs, "Bugs assigned to you")
    list_bugs(unassigned_bugs, "Unassigned bugs")
    list_bugs(other_bugs, "Bugs assigned to others")


def get_parser():
    parser = cmdutil.CmdOptionParser("be list [options]")
    parser.add_option("-w", "--wishlist", action="store_true", dest="wishlist",
                      help="List bugs with 'wishlist' severity")
    parser.add_option("-c", "--closed", action="store_true", dest="closed",
                      help="List closed bugs")
    parser.add_option("-m", "--mine", action="store_true", dest="mine",
                      help="List only bugs assigned to you")
    parser.add_option("-t", "--cur-target", action="store_true", 
                      dest="cur_target",
                      help="List only bugs for the current target")
    return parser

longhelp="""
This command lists bugs.  Options are cumulative, so that -mc will list only
closed bugs assigned to you.
"""

def help():
    return get_parser().help_str() + longhelp
