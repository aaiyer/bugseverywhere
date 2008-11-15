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
from libbe.bug import cmp_full, severity_values, status_values, \
    active_status_values, inactive_status_values
import os
def execute(args):
    options, args = get_parser().parse_args(args)
    if len(args) > 0:
        raise cmdutil.UsageError
    tree = cmdutil.bug_tree()
    # select status
    if options.status != None:
        if options.status == "all":
            status = status_values
        else:
            status = options.status.split(',')
    else:
        status = []
        if options.active == True:
            status.extend(list(active_status_values))
        if options.unconfirmed == True:
            status.append("unconfirmed")
        if options.open == True:
            status.append("opened")
        if options.test == True:
            status.append("test")
        if status == []: # set the default value
            status = active_status_values
    # select severity
    if options.severity != None:
        if options.severity == "all":
            severity = severity_values
        else:
            severity = options.severity.split(',')
    else:
        severity = []
        if options.wishlist == True:
            severity.extend("wishlist")
        if options.important == True:
            serious = severity_values.index("serious")
            severity.append(list(severity_values[serious:]))
        if severity == []: # set the default value
            severity = severity_values
    # select assigned
    if options.assigned != None:
        if options.assigned == "all":
            assigned = "all"
        else:
            assigned = options.assigned.split(',')
    else:
        assigned = []
        if options.mine == True:
            assigned.extend('-')
        if assigned == []: # set the default value
            assigned = "all"
    for i in range(len(assigned)):
        if assigned[i] == '-':
            assigned[i] == names.creator()
    # select target
    if options.target != None:
        if options.target == "all":
            target = "all"
        else:
            target = options.target.split(',')
    else:
        target = []
        if options.cur_target == True:
            target.append(tree.target)
        if target == []: # set the default value
            target = "all"
    
    def filter(bug):
        if status != "all" and not bug.status in status:
            return False
        if severity != "all" and not bug.severity in severity:
            return False
        if assigned != "all" and not bug.assigned in assigned:
            return False
        if target != "all" and not bug.target in target:
            return False
        return True

    all_bugs = list(tree.list())
    bugs = [b for b in all_bugs if filter(b) ]
    if len(bugs) == 0:
        print "No matching bugs found"
    
    def list_bugs(cur_bugs, title=None, no_target=False):
        cur_bugs.sort(cmp_full)
        if len(cur_bugs) > 0:
            if title != None:
                print cmdutil.underlined(title)
            for bug in cur_bugs:
                print bug.string(all_bugs, shortlist=True),
    
    list_bugs(bugs, no_target=False)

def get_parser():
    parser = cmdutil.CmdOptionParser("be list [options]")
    parser.add_option("-s", "--status", metavar="STATUS", dest="status",
                      help="List options matching STATUS", default=None)
    parser.add_option("-v", "--severity", metavar="SEVERITY", dest="severity",
                      help="List options matching SEVERITY", default=None)
    parser.add_option("-a", "--assigned", metavar="ASSIGNED", dest="assigned",
                      help="List options matching ASSIGNED", default=None)
    parser.add_option("-t", "--target", metavar="TARGET", dest="target",
                      help="List options matching TARGET", default=None)
    # boolean shortucts.  All of these are special cases of long forms
    bools = (("w", "wishlist", "List bugs with 'wishlist' severity"),
             ("i", "important", "List bugs with >= 'serious' severity"),
             ("A", "active", "List all active bugs"),
             ("u", "unconfirmed", "List unconfirmed bugs"),
             ("o", "open", "List open bugs"),
             ("T", "test", "List bugs in testing"),
             ("m", "mine", "List bugs assigned to you"),
             ("c", "cur-target", "List bugs for the current target"))
    for s in bools:
        attr = s[1].replace('-','_')
        short = "-%c" % s[0]
        long = "--%s" % s[1]
        help = s[2]
        parser.add_option(short, long, action="store_true", dest=attr, help=help)
    return parser

longhelp="""
This command lists bugs.  There are several criteria that you can
search by:
  * status
  * severity
  * assigned (who the bug is assigned to)
  * target   (bugfix deadline)
Allowed values for each criterion may be given in a comma seperated
list.  The special string "all" may be used with any of these options
to match all values of the criterion.

status
  %s
severity
  %s
assigned
  free form, with the string '-' being a shortcut for yourself.
target
  free form

In addition, there are some shortcut options that set boolean flags.
The boolean options are ignored if the matching string option is used.
""" % (','.join(status_values),
       ','.join(severity_values))

def help():
    return get_parser().help_str() + longhelp
