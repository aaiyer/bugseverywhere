from libbe import bugdir, cmdutil
import os
def execute(args):
    active = True
    severity = ("minor", "serious", "critical", "fatal")
    def filter(bug):
        if active is not None:
            if bug.active != active:
                return False
        if bug.severity not in severity:
            return False
        return True
    all_bugs = list(bugdir.tree_root(os.getcwd()).list())
    bugs = [b for b in all_bugs if filter(b) ]
    if len(bugs) == 0:
        print "No matching bugs found"
    for bug in bugs:
        print cmdutil.bug_summary(bug, all_bugs)
