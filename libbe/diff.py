"""Compare two bug trees"""
from libbe import cmdutil, bugdir

def diff(old_tree, new_tree):
    old_bug_map = old_tree.bug_map()
    new_bug_map = new_tree.bug_map()
    added = []
    removed = []
    modified = []
    for old_bug in old_bug_map.itervalues():
        new_bug = new_bug_map.get(old_bug.uuid)
        if new_bug is None :
            removed.append(old_bug)
        else:
            if old_bug != new_bug:
                modified.append((old_bug, new_bug))
    for new_bug in new_bug_map.itervalues():
        if not old_bug_map.has_key(new_bug.uuid):
            added.append(new_bug)
    return (removed, modified, added)


def reference_diff(bugdir, spec=None):
    return diff(bugdir.get_reference_bugdir(spec), bugdir)
    
def diff_report(diff_data, bug_dir):
    (removed, modified, added) = diff_data
    bugs = list(bug_dir.list())
    def modified_cmp(left, right):
        return bugdir.cmp_severity(left[1], right[1])

    added.sort(bugdir.cmp_severity)
    removed.sort(bugdir.cmp_severity)
    modified.sort(modified_cmp)

    if len(added) > 0: 
        print "New bug reports:"
        for bug in added:
            print cmdutil.bug_summary(bug, bugs, no_target=True)

    if len(modified) > 0:
        printed = False
        for old_bug, new_bug in modified:
            change_str = bug_changes(old_bug, new_bug, bugs)
            if change_str is None:
                continue
            if not printed:
                printed = True
                print "Modified bug reports:"
            print change_str

    if len(removed) > 0: 
        print "Removed bug reports:"
        for bug in removed:
            print cmdutil.bug_summary(bug, bugs, no_target=True)
   
def change_lines(old, new, attributes):
    change_list = []    
    for attr in attributes:
        old_attr = getattr(old, attr)
        new_attr = getattr(new, attr)
        if old_attr != new_attr:
            change_list.append((attr, old_attr, new_attr))
    if len(change_list) >= 0:
        return change_list
    else:
        return None

def bug_changes(old, new, bugs):
    change_list = change_lines(old, new, ("time", "creator", "severity",
    "target", "summary", "status", "assigned"))
    if len(change_list) == 0:
        return None
    return "%s%s\n" % (cmdutil.bug_summary(new, bugs, shortlist=True), 
                       "\n".join(["%s: %s -> %s" % f for f in change_list]))


