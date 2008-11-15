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
"""Compare two bug trees"""
from libbe import cmdutil, bugdir
from libbe.utility import time_to_str
from libbe.bug import cmp_severity

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
        return cmp_severity(left[1], right[1])

    added.sort(cmp_severity)
    removed.sort(cmp_severity)
    modified.sort(modified_cmp)

    if len(added) > 0: 
        print "New bug reports:"
        for bug in added:
            print bug.string(shortlist=True)

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
            print bug.string(bug, bugs, shortlist=True)
   
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

    old_comment_ids = list(old.iter_comment_ids())
    new_comment_ids = list(new.iter_comment_ids())
    change_strings = ["%s: %s -> %s" % f for f in change_list]
    for comment_id in new_comment_ids:
        if comment_id not in old_comment_ids:
            summary = comment_summary(new.get_comment(comment_id), "new")
            change_strings.append(summary)
    for comment_id in old_comment_ids:
        if comment_id not in new_comment_ids:
            summary = comment_summary(new.get_comment(comment_id), "removed")
            change_strings.append(summary)

    if len(change_strings) == 0:
        return None
    return "%s%s\n" % (new.string(bugs, shortlist=True), 
                       "\n".join(change_strings))


def comment_summary(comment, status):
    return "%8s comment from %s on %s" % (status, comment.From, 
                                          time_to_str(comment.time))
