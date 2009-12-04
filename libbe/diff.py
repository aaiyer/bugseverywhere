# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
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

"""Compare two bug trees."""

import difflib

import libbe
from libbe import bugdir, bug, settings_object, tree
from libbe.utility import time_to_str
if libbe.TESTING == True:
    import doctest


class DiffTree (tree.Tree):
    """
    A tree holding difference data for easy report generation.
    >>> bugdir = DiffTree("bugdir")
    >>> bdsettings = DiffTree("settings", data="target: None -> 1.0")
    >>> bugdir.append(bdsettings)
    >>> bugs = DiffTree("bugs", "bug-count: 5 -> 6")
    >>> bugdir.append(bugs)
    >>> new = DiffTree("new", "new bugs: ABC, DEF")
    >>> bugs.append(new)
    >>> rem = DiffTree("rem", "removed bugs: RST, UVW")
    >>> bugs.append(rem)
    >>> print bugdir.report_string()
    target: None -> 1.0
    bug-count: 5 -> 6
      new bugs: ABC, DEF
      removed bugs: RST, UVW
    >>> print "\\n".join(bugdir.paths())
    bugdir
    bugdir/settings
    bugdir/bugs
    bugdir/bugs/new
    bugdir/bugs/rem
    >>> bugdir.child_by_path("/") == bugdir
    True
    >>> bugdir.child_by_path("/bugs") == bugs
    True
    >>> bugdir.child_by_path("/bugs/rem") == rem
    True
    >>> bugdir.child_by_path("bugdir") == bugdir
    True
    >>> bugdir.child_by_path("bugdir/") == bugdir
    True
    >>> bugdir.child_by_path("bugdir/bugs") == bugs
    True
    >>> bugdir.child_by_path("/bugs").masked = True
    >>> print bugdir.report_string()
    target: None -> 1.0
    """
    def __init__(self, name, data=None, data_part_fn=str,
                 requires_children=False, masked=False):
        tree.Tree.__init__(self)
        self.name = name
        self.data = data
        self.data_part_fn = data_part_fn
        self.requires_children = requires_children
        self.masked = masked
    def paths(self, parent_path=None):
        paths = []
        if parent_path == None:
            path = self.name
        else:
            path = "%s/%s" % (parent_path, self.name)
        paths.append(path)
        for child in self:
            paths.extend(child.paths(path))
        return paths
    def child_by_path(self, path):
        if hasattr(path, "split"): # convert string path to a list of names
            names = path.split("/")
            if names[0] == "":
                names[0] = self.name # replace root with self
            if len(names) > 1 and names[-1] == "":
                names = names[:-1] # strip empty tail
        else: # it was already an array
            names = path
        assert len(names) > 0, path
        if names[0] == self.name:
            if len(names) == 1:
                return self
            for child in self:
                if names[1] == child.name:
                    return child.child_by_path(names[1:])
        if len(names) == 1:
            raise KeyError, "%s doesn't match '%s'" % (names, self.name)
        raise KeyError, "%s points to child not in %s" % (names, [c.name for c in self])
    def report_string(self):
        return "\n".join(self.report())
    def report(self, root=None, parent=None, depth=0):
        if root == None:
            root = self.make_root()
        if self.masked == True:
            return None
        data_part = self.data_part(depth)
        if self.requires_children == True and len(self) == 0:
            pass
        else:
            self.join(root, parent, data_part)
            if data_part != None:
                depth += 1
        for child in self:
            child.report(root, self, depth)
        return root
    def make_root(self):
        return []
    def join(self, root, parent, data_part):
        if data_part != None:
            root.append(data_part)
    def data_part(self, depth, indent=True):
        if self.data == None:
            return None
        if hasattr(self, "_cached_data_part"):
            return self._cached_data_part
        data_part = self.data_part_fn(self.data)
        if indent == True:
            data_part_lines = data_part.splitlines()
            indent = "  "*(depth)
            line_sep = "\n"+indent
            data_part = indent+line_sep.join(data_part_lines)
        self._cached_data_part = data_part
        return data_part

class Diff (object):
    """
    Difference tree generator for BugDirs.
    >>> import copy
    >>> bd = bugdir.SimpleBugDir(sync_with_disk=False)
    >>> bd.user_id = "John Doe <j@doe.com>"
    >>> bd_new = copy.deepcopy(bd)
    >>> bd_new.target = "1.0"
    >>> a = bd_new.bug_from_uuid("a")
    >>> rep = a.comment_root.new_reply("I'm closing this bug")
    >>> rep.uuid = "acom"
    >>> rep.date = "Thu, 01 Jan 1970 00:00:00 +0000"
    >>> a.status = "closed"
    >>> b = bd_new.bug_from_uuid("b")
    >>> bd_new.remove_bug(b)
    >>> c = bd_new.new_bug("c", "Bug C")
    >>> d = Diff(bd, bd_new)
    >>> r = d.report_tree()
    >>> print "\\n".join(r.paths())
    bugdir
    bugdir/settings
    bugdir/bugs
    bugdir/bugs/new
    bugdir/bugs/new/c
    bugdir/bugs/rem
    bugdir/bugs/rem/b
    bugdir/bugs/mod
    bugdir/bugs/mod/a
    bugdir/bugs/mod/a/settings
    bugdir/bugs/mod/a/comments
    bugdir/bugs/mod/a/comments/new
    bugdir/bugs/mod/a/comments/new/acom
    bugdir/bugs/mod/a/comments/rem
    bugdir/bugs/mod/a/comments/mod
    >>> print r.report_string()
    Changed bug directory settings:
      target: None -> 1.0
    New bugs:
      c:om: Bug C
    Removed bugs:
      b:cm: Bug B
    Modified bugs:
      a:cm: Bug A
        Changed bug settings:
          status: open -> closed
        New comments:
          from John Doe <j@doe.com> on Thu, 01 Jan 1970 00:00:00 +0000
            I'm closing this bug...
    >>> bd.cleanup()
    """
    def __init__(self, old_bugdir, new_bugdir):
        self.old_bugdir = old_bugdir
        self.new_bugdir = new_bugdir

    # data assembly methods

    def _changed_bugs(self):
        """
        Search for differences in all bugs between .old_bugdir and
        .new_bugdir.  Returns
          (added_bugs, modified_bugs, removed_bugs)
        where added_bugs and removed_bugs are lists of added and
        removed bugs respectively.  modified_bugs is a list of
        (old_bug,new_bug) pairs.
        """
        if hasattr(self, "__changed_bugs"):
            return self.__changed_bugs
        added = []
        removed = []
        modified = []
        for uuid in self.new_bugdir.uuids():
            new_bug = self.new_bugdir.bug_from_uuid(uuid)
            try:
                old_bug = self.old_bugdir.bug_from_uuid(uuid)
            except KeyError:
                added.append(new_bug)
            else:
                if old_bug.sync_with_disk == True:
                    old_bug.load_comments()
                if new_bug.sync_with_disk == True:
                    new_bug.load_comments()
                if old_bug != new_bug:
                    modified.append((old_bug, new_bug))
        for uuid in self.old_bugdir.uuids():
            if not self.new_bugdir.has_bug(uuid):
                old_bug = self.old_bugdir.bug_from_uuid(uuid)
                removed.append(old_bug)
        added.sort()
        removed.sort()
        modified.sort(self._bug_modified_cmp)
        self.__changed_bugs = (added, modified, removed)
        return self.__changed_bugs
    def _bug_modified_cmp(self, left, right):
        return cmp(left[1], right[1])
    def _changed_comments(self, old, new):
        """
        Search for differences in all loaded comments between the bugs
        old and new.  Returns
          (added_comments, modified_comments, removed_comments)
        analogous to ._changed_bugs.
        """
        if hasattr(self, "__changed_comments"):
            if new.uuid in self.__changed_comments:
                return self.__changed_comments[new.uuid]
        else:
            self.__changed_comments = {}
        added = []
        removed = []
        modified = []
        old.comment_root.sort(key=lambda comm : comm.time)
        new.comment_root.sort(key=lambda comm : comm.time)
        old_comment_ids = [c.uuid for c in old.comments()]
        new_comment_ids = [c.uuid for c in new.comments()]
        for uuid in new_comment_ids:
            new_comment = new.comment_from_uuid(uuid)
            try:
                old_comment = old.comment_from_uuid(uuid)
            except KeyError:
                added.append(new_comment)
            else:
                if old_comment != new_comment:
                    modified.append((old_comment, new_comment))
        for uuid in old_comment_ids:
            if uuid not in new_comment_ids:
                new_comment = new.comment_from_uuid(uuid)
                removed.append(new_comment)
        self.__changed_comments[new.uuid] = (added, modified, removed)
        return self.__changed_comments[new.uuid]
    def _attribute_changes(self, old, new, attributes):
        """
        Take two objects old and new, and compare the value of *.attr
        for attr in the list attribute names.  Returns a list of
          (attr_name, old_value, new_value)
        tuples.
        """
        change_list = []
        for attr in attributes:
            old_value = getattr(old, attr)
            new_value = getattr(new, attr)
            if old_value != new_value:
                change_list.append((attr, old_value, new_value))
        if len(change_list) >= 0:
            return change_list
        return None
    def _settings_properties_attribute_changes(self, old, new,
                                              hidden_properties=[]):
        properties = sorted(new.settings_properties)
        for p in hidden_properties:
            properties.remove(p)
        attributes = [settings_object.setting_name_to_attr_name(None, p)
                      for p in properties]
        return self._attribute_changes(old, new, attributes)
    def _bugdir_attribute_changes(self):
        return self._settings_properties_attribute_changes( \
            self.old_bugdir, self.new_bugdir,
            ["vcs_name"]) # tweaked by bugdir.duplicate_bugdir
    def _bug_attribute_changes(self, old, new):
        return self._settings_properties_attribute_changes(old, new)
    def _comment_attribute_changes(self, old, new):
        return self._settings_properties_attribute_changes(old, new)

    # report generation methods

    def report_tree(self, diff_tree=DiffTree):
        """
        Pretty bare to make it easy to adjust to specific cases.  You
        can pass in a DiffTree subclass via diff_tree to override the
        default report assembly process.
        """
        if hasattr(self, "__report_tree"):
            return self.__report_tree
        bugdir_settings = sorted(self.new_bugdir.settings_properties)
        bugdir_settings.remove("vcs_name") # tweaked by bugdir.duplicate_bugdir
        root = diff_tree("bugdir")
        bugdir_attribute_changes = self._bugdir_attribute_changes()
        if len(bugdir_attribute_changes) > 0:
            bugdir = diff_tree("settings", bugdir_attribute_changes,
                               self.bugdir_attribute_change_string)
            root.append(bugdir)
        bug_root = diff_tree("bugs")
        root.append(bug_root)
        add,mod,rem = self._changed_bugs()
        bnew = diff_tree("new", "New bugs:", requires_children=True)
        bug_root.append(bnew)
        for bug in add:
            b = diff_tree(bug.uuid, bug, self.bug_add_string)
            bnew.append(b)
        brem = diff_tree("rem", "Removed bugs:", requires_children=True)
        bug_root.append(brem)
        for bug in rem:
            b = diff_tree(bug.uuid, bug, self.bug_rem_string)
            brem.append(b)
        bmod = diff_tree("mod", "Modified bugs:", requires_children=True)
        bug_root.append(bmod)
        for old,new in mod:
            b = diff_tree(new.uuid, (old,new), self.bug_mod_string)
            bmod.append(b)
            bug_attribute_changes = self._bug_attribute_changes(old, new)
            if len(bug_attribute_changes) > 0:
                bset = diff_tree("settings", bug_attribute_changes,
                                 self.bug_attribute_change_string)
                b.append(bset)
            if old.summary != new.summary:
                data = (old.summary, new.summary)
                bsum = diff_tree("summary", data, self.bug_summary_change_string)
                b.append(bsum)
            cr = diff_tree("comments")
            b.append(cr)
            a,m,d = self._changed_comments(old, new)
            cnew = diff_tree("new", "New comments:", requires_children=True)
            for comment in a:
                c = diff_tree(comment.uuid, comment, self.comment_add_string)
                cnew.append(c)
            crem = diff_tree("rem", "Removed comments:",requires_children=True)
            for comment in d:
                c = diff_tree(comment.uuid, comment, self.comment_rem_string)
                crem.append(c)
            cmod = diff_tree("mod","Modified comments:",requires_children=True)
            for o,n in m:
                c = diff_tree(n.uuid, (o,n), self.comment_mod_string)
                cmod.append(c)
                comm_attribute_changes = self._comment_attribute_changes(o, n)
                if len(comm_attribute_changes) > 0:
                    cset = diff_tree("settings", comm_attribute_changes,
                                     self.comment_attribute_change_string)
                if o.body != n.body:
                    data = (o.body, n.body)
                    cbody = diff_tree("cbody", data,
                                      self.comment_body_change_string)
                    c.append(cbody)
            cr.extend([cnew, crem, cmod])
        self.__report_tree = root
        return self.__report_tree

    # change data -> string methods.
    # Feel free to play with these in subclasses.

    def attribute_change_string(self, attribute_changes, indent=0):
        indent_string = "  "*indent
        change_strings = [u"%s: %s -> %s" % f for f in attribute_changes]
        for i,change_string in enumerate(change_strings):
            change_strings[i] = indent_string+change_string
        return u"\n".join(change_strings)
    def bugdir_attribute_change_string(self, attribute_changes):
        return "Changed bug directory settings:\n%s" % \
            self.attribute_change_string(attribute_changes, indent=1)
    def bug_attribute_change_string(self, attribute_changes):
        return "Changed bug settings:\n%s" % \
            self.attribute_change_string(attribute_changes, indent=1)
    def comment_attribute_change_string(self, attribute_changes):
        return "Changed comment settings:\n%s" % \
            self.attribute_change_string(attribute_changes, indent=1)
    def bug_add_string(self, bug):
        return bug.string(shortlist=True)
    def bug_rem_string(self, bug):
        return bug.string(shortlist=True)
    def bug_mod_string(self, bugs):
        old_bug,new_bug = bugs
        return new_bug.string(shortlist=True)
    def bug_summary_change_string(self, summaries):
        old_summary,new_summary = summaries
        return "summary changed:\n  %s\n  %s" % (old_summary, new_summary)
    def _comment_summary_string(self, comment):
        return "from %s on %s" % (comment.author, time_to_str(comment.time))
    def comment_add_string(self, comment):
        summary = self._comment_summary_string(comment)
        first_line = comment.body.splitlines()[0]
        return "%s\n  %s..." % (summary, first_line)
    def comment_rem_string(self, comment):
        summary = self._comment_summary_string(comment)
        first_line = comment.body.splitlines()[0]
        return "%s\n  %s..." % (summary, first_line)
    def comment_mod_string(self, comments):
        old_comment,new_comment = comments
        return self._comment_summary_string(new_comment)
    def comment_body_change_string(self, bodies):
        old_body,new_body = bodies
        return difflib.unified_diff(old_body, new_body)


if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
