"""List bugs"""
from libbe import bugdir, cmdutil, names
import os
def execute(args):
    active = True
    severity = ("minor", "serious", "critical", "fatal")
    tree = cmdutil.bug_tree()
    def filter(bug):
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
    current_id = names.creator()
    
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

    def list_bugs(cur_bugs, title):
        cur_bugs.sort(bugdir.cmp_severity)
        if len(cur_bugs) > 0:
            print cmdutil.underlined(title)
            for bug in cur_bugs:
                print cmdutil.bug_summary(bug, all_bugs)
    
    list_bugs(my_target_bugs, 
              "Bugs assigned to you for target %s" % tree.target)
    list_bugs(unassigned_target_bugs, 
              "Unassigned bugs for target %s" % tree.target)
    list_bugs(other_target_bugs, 
              "Bugs assigned to others for target %s" % tree.target)
    list_bugs(my_bugs, "Bugs assigned to you")
    list_bugs(unassigned_bugs, "Unassigned bugs")
    list_bugs(other_bugs, "Bugs assigned to others")
