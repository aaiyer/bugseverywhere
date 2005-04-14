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

    if len(modified) > 0 and False:
        print "modified bug reports:"
        for old_bug, new_bug in modified: 
            print cmdutil.bug_summary(new_bug, bugs, no_target=True)

    if len(removed) > 0: 
        print "Removed bug reports:"
        for bug in removed:
            print cmdutil.bug_summary(bug, bugs, no_target=True)
   


