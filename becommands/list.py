"""List bugs"""
from libbe import bugdir, cmdutil, names
from libbe.mapfile import FileString
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
        cur_bugs.sort(bugdir.cmp_severity)
        if len(cur_bugs) > 0:
            print cmdutil.underlined(title)
            for bug in cur_bugs:
                print cmdutil.bug_summary(bug, all_bugs, no_target=no_target)
    
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
    fs = FileString()
    get_parser().print_help(fs)
    return fs.str + longhelp
