# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         W. Trevor King <wking@drexel.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Compare two bug trees"""
from libbe import cmdutil, bugdir, bug
from libbe.utility import time_to_str
import doctest

def bug_diffs(old_bugdir, new_bugdir):
    added = []
    removed = []
    modified = []
    for uuid in old_bugdir.list_uuids():
        old_bug = old_bugdir.bug_from_uuid(uuid)
        try:
            new_bug = new_bugdir.bug_from_uuid(uuid)
            old_bug.load_comments()
            new_bug.load_comments()
            if old_bug != new_bug:
                modified.append((old_bug, new_bug))
        except KeyError:
            removed.append(old_bug)
    for uuid in new_bugdir.list_uuids():
        if not old_bugdir.has_bug(uuid):
            new_bug = new_bugdir.bug_from_uuid(uuid)
            added.append(new_bug)
    return (removed, modified, added)

def diff_report(bug_diffs_data, old_bugdir, new_bugdir):
    bugs_removed,bugs_modified,bugs_added = bug_diffs_data
    def modified_cmp(left, right):
        return bug.cmp_severity(left[1], right[1])

    bugs_added.sort(bug.cmp_severity)
    bugs_removed.sort(bug.cmp_severity)
    bugs_modified.sort(modified_cmp)
    lines = []
    
    if old_bugdir.settings != new_bugdir.settings:
        bugdir_settings = sorted(new_bugdir.settings_properties)
        bugdir_settings.remove("rcs_name") # tweaked by bugdir.duplicate_bugdir
        change_list = change_lines(old_bugdir, new_bugdir, bugdir_settings)
        if len(change_list) >  0:
            lines.append("Modified bug directory:")
            change_strings = ["%s: %s -> %s" % f for f in change_list]
            lines.extend(change_strings)
            lines.append("")
    if len(bugs_added) > 0:
        lines.append("New bug reports:")
        for bg in bugs_added:
            lines.extend(bg.string(shortlist=True).splitlines())
        lines.append("")
    if len(bugs_modified) > 0:
        printed = False
        for old_bug, new_bug in bugs_modified:
            change_str = bug_changes(old_bug, new_bug)
            if change_str is None:
                continue
            if not printed:
                printed = True
                lines.append("Modified bug reports:")
            lines.extend(change_str.splitlines())
        if printed == True:
            lines.append("")
    if len(bugs_removed) > 0:
        lines.append("Removed bug reports:")
        for bg in bugs_removed:
            lines.extend(bg.string(shortlist=True).splitlines())
        lines.append("")
    
    return "\n".join(lines).rstrip("\n")

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

def bug_changes(old, new):
    bug_settings = sorted(new.settings_properties)
    change_list = change_lines(old, new, bug_settings)
    change_strings = ["%s: %s -> %s" % f for f in change_list]

    old_comment_ids = [c.uuid for c in old.comments()]
    new_comment_ids = [c.uuid for c in new.comments()]
    for comment_id in new_comment_ids:
        if comment_id not in old_comment_ids:
            summary = comment_summary(new.comment_from_uuid(comment_id), "new")
            change_strings.append(summary)
    for comment_id in old_comment_ids:
        if comment_id not in new_comment_ids:
            summary = comment_summary(new.comment_from_uuid(comment_id),
                                      "removed")
            change_strings.append(summary)

    if len(change_strings) == 0:
        return None
    return "%s\n  %s" % (new.string(shortlist=True),
                         "  \n".join(change_strings))


def comment_summary(comment, status):
    return "%8s comment from %s on %s" % (status, comment.From, 
                                          time_to_str(comment.time))

suite = doctest.DocTestSuite()
