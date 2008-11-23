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
import doctest

def diff(old_bugdir, new_bugdir):
    added = []
    removed = []
    modified = []
    for uuid in old_bugdir.list_uuids():
        old_bug = old_bugdir.bug_from_uuid(uuid)
        try:
            new_bug = new_bugdir.bug_from_uuid(uuid)
            if old_bug != new_bug:
                modified.append((old_bug, new_bug))
        except KeyError:
            removed.append(old_bug)
    for uuid in new_bugdir.list_uuids():
        if not old_bugdir.bug_map.has_key(new_bug.uuid):
            new_bug = new_bugdir.bug_from_uuid(uuid)
            added.append(new_bug)
    return (removed, modified, added)

def diff_report(diff_data, bug_dir):
    (removed, modified, added) = diff_data
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
            change_str = bug_changes(old_bug, new_bug, bug_dir)
            if change_str is None:
                continue
            if not printed:
                printed = True
                print "Modified bug reports:"
            print change_str

    if len(removed) > 0: 
        print "Removed bug reports:"
        for bug in removed:
            print bug.string(shortlist=True)
   
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

    old.load_comments()
    old_comment_ids = [c.uuid for c in old.comment_root.traverse()]
    new.load_comments()
    new_comment_ids = [c.uuid for c in new.comment_root.traverse()]
    change_strings = ["%s: %s -> %s" % f for f in change_list]
    for comment_id in new_comment_ids:
        if comment_id not in old_comment_ids:
            summary = comment_summary(new.comment_root.comment_from_uuid(comment_id), "new")
            change_strings.append(summary)
    for comment_id in old_comment_ids:
        if comment_id not in new_comment_ids:
            summary = comment_summary(new.comment.root.comment_from_uuid(comment_id), "removed")
            change_strings.append(summary)

    if len(change_strings) == 0:
        return None
    return "%s\n  %s" % (new.string(shortlist=True),
                         "  \n".join(change_strings))


def comment_summary(comment, status):
    return "%8s comment from %s on %s" % (status, comment.From, 
                                          time_to_str(comment.time))

suite = doctest.DocTestSuite()
