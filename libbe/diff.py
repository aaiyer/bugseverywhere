# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""Tools for comparing two :class:`libbe.bug.BugDir`\s.
"""

import difflib
import types

import libbe
import libbe.bugdir
import libbe.bug
import libbe.util.tree
from libbe.storage.util.settings_object import setting_name_to_attr_name
from libbe.util.utility import time_to_str


class SubscriptionType (libbe.util.tree.Tree):
    """Trees of subscription types to allow users to select exactly what
    notifications they want to subscribe to.
    """
    def __init__(self, type_name, *args, **kwargs):
        libbe.util.tree.Tree.__init__(self, *args, **kwargs)
        self.type = type_name
    def __str__(self):
        return self.type
    def __cmp__(self, other):
        return cmp(self.type, other.type)
    def __repr__(self):
        return '<SubscriptionType: %s>' % str(self)
    def string_tree(self, indent=0):
        lines = []
        for depth,node in self.thread():
            lines.append('%s%s' % (' '*(indent+2*depth), node))
        return '\n'.join(lines)

BUGDIR_ID = 'DIR'
BUGDIR_TYPE_NEW = SubscriptionType('new')
BUGDIR_TYPE_MOD = SubscriptionType('mod')
BUGDIR_TYPE_REM = SubscriptionType('rem')
BUGDIR_TYPE_ALL = SubscriptionType('all',
                      [BUGDIR_TYPE_NEW, BUGDIR_TYPE_MOD, BUGDIR_TYPE_REM])

# same name as BUGDIR_TYPE_ALL for consistency
BUG_TYPE_ALL = SubscriptionType(str(BUGDIR_TYPE_ALL))

INVALID_TYPE = SubscriptionType('INVALID')

class InvalidType (ValueError):
    def __init__(self, type_name, type_root):
        msg = 'Invalid type %s for tree:\n%s' \
            % (type_name, type_root.string_tree(4))
        ValueError.__init__(self, msg)
        self.type_name = type_name
        self.type_root = type_root

def type_from_name(name, type_root, default=None, default_ok=False):
    if name == str(type_root):
        return type_root
    for t in type_root.traverse():
        if name == str(t):
            return t
    if default_ok:
        return default
    raise InvalidType(name, type_root)

class Subscription (object):
    """A user subscription.

    Examples
    --------

    >>> subscriptions = [Subscription('XYZ', 'all'),
    ...                  Subscription('DIR', 'new'),
    ...                  Subscription('ABC', BUG_TYPE_ALL),]
    >>> print sorted(subscriptions)
    [<Subscription: DIR (new)>, <Subscription: ABC (all)>, <Subscription: XYZ (all)>]
    """
    def __init__(self, id, subscription_type, **kwargs):
        if 'type_root' not in kwargs:
            if id == BUGDIR_ID:
                kwargs['type_root'] = BUGDIR_TYPE_ALL
            else:
                kwargs['type_root'] = BUG_TYPE_ALL
        if type(subscription_type) in types.StringTypes:
            subscription_type = type_from_name(subscription_type, **kwargs)
        self.id = id
        self.type = subscription_type
    def __cmp__(self, other):
        for attr in 'id', 'type':
            value = cmp(getattr(self, attr), getattr(other, attr))
            if value != 0:
                if self.id == BUGDIR_ID:
                    return -1
                elif other.id == BUGDIR_ID:
                    return 1
                return value
    def __str__(self):
        return str(self.type)
    def __repr__(self):
        return '<Subscription: %s (%s)>' % (self.id, self.type)

def subscriptions_from_string(string=None, subscription_sep=',', id_sep=':'):
    """Provide a simple way for non-Python interfaces to read in subscriptions.

    Examples
    --------

    >>> subscriptions_from_string(None)
    [<Subscription: DIR (all)>]
    >>> subscriptions_from_string('DIR:new,DIR:rem,ABC:all,XYZ:all')
    [<Subscription: DIR (new)>, <Subscription: DIR (rem)>, <Subscription: ABC (all)>, <Subscription: XYZ (all)>]
    >>> subscriptions_from_string('DIR::new')
    Traceback (most recent call last):
      ...
    ValueError: Invalid subscription "DIR::new", should be ID:TYPE
    """
    if string == None:
        return [Subscription(BUGDIR_ID, BUGDIR_TYPE_ALL)]
    subscriptions = []
    for subscription in string.split(','):
        fields = subscription.split(':')
        if len(fields) != 2:
            raise ValueError('Invalid subscription "%s", should be ID:TYPE'
                             % subscription)
        id,type = fields
        subscriptions.append(Subscription(id, type))
    return subscriptions

class DiffTree (libbe.util.tree.Tree):
    """A tree holding difference data for easy report generation.

    Examples
    --------

    >>> bugdir = DiffTree('bugdir')
    >>> bdsettings = DiffTree('settings', data='target: None -> 1.0')
    >>> bugdir.append(bdsettings)
    >>> bugs = DiffTree('bugs', 'bug-count: 5 -> 6')
    >>> bugdir.append(bugs)
    >>> new = DiffTree('new', 'new bugs: ABC, DEF')
    >>> bugs.append(new)
    >>> rem = DiffTree('rem', 'removed bugs: RST, UVW')
    >>> bugs.append(rem)
    >>> print bugdir.report_string()
    target: None -> 1.0
    bug-count: 5 -> 6
      new bugs: ABC, DEF
      removed bugs: RST, UVW
    >>> print '\\n'.join(bugdir.paths())
    bugdir
    bugdir/settings
    bugdir/bugs
    bugdir/bugs/new
    bugdir/bugs/rem
    >>> bugdir.child_by_path('/') == bugdir
    True
    >>> bugdir.child_by_path('/bugs') == bugs
    True
    >>> bugdir.child_by_path('/bugs/rem') == rem
    True
    >>> bugdir.child_by_path('bugdir') == bugdir
    True
    >>> bugdir.child_by_path('bugdir/') == bugdir
    True
    >>> bugdir.child_by_path('bugdir/bugs') == bugs
    True
    >>> bugdir.child_by_path('/bugs').masked = True
    >>> print bugdir.report_string()
    target: None -> 1.0
    """
    def __init__(self, name, data=None, data_part_fn=str,
                 requires_children=False, masked=False):
        libbe.util.tree.Tree.__init__(self)
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
            path = '%s/%s' % (parent_path, self.name)
        paths.append(path)
        for child in self:
            paths.extend(child.paths(path))
        return paths
    def child_by_path(self, path):
        if hasattr(path, 'split'): # convert string path to a list of names
            names = path.split('/')
            if names[0] == '':
                names[0] = self.name # replace root with self
            if len(names) > 1 and names[-1] == '':
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
        raise KeyError, '%s points to child not in %s' % (names, [c.name for c in self])
    def report_string(self):
        report = self.report()
        if report == None:
            return ''
        return '\n'.join(report)
    def report(self, root=None, parent=None, depth=0):
        if root == None:
            root = self.make_root()
        if self.masked == True:
            return root
        data_part = self.data_part(depth)
        if self.requires_children == True \
                and len([c for c in self if c.masked == False]) == 0:
            pass
        else:
            self.join(root, parent, data_part)
            if data_part != None:
                depth += 1
            for child in self:
                root = child.report(root, self, depth)
        return root
    def make_root(self):
        return []
    def join(self, root, parent, data_part):
        if data_part != None:
            root.append(data_part)
    def data_part(self, depth, indent=True):
        if self.data == None:
            return None
        if hasattr(self, '_cached_data_part'):
            return self._cached_data_part
        data_part = self.data_part_fn(self.data)
        if indent == True:
            data_part_lines = data_part.splitlines()
            indent = '  '*(depth)
            line_sep = '\n'+indent
            data_part = indent+line_sep.join(data_part_lines)
        self._cached_data_part = data_part
        return data_part

class Diff (object):
    """Difference tree generator for BugDirs.

    Examples
    --------

    >>> import copy
    >>> bd = libbe.bugdir.SimpleBugDir(memory=True)
    >>> bd_new = copy.deepcopy(bd)
    >>> bd_new.target = '1.0'
    >>> a = bd_new.bug_from_uuid('a')
    >>> rep = a.comment_root.new_reply("I'm closing this bug")
    >>> rep.uuid = 'acom'
    >>> rep.author = 'John Doe <j@doe.com>'
    >>> rep.date = 'Thu, 01 Jan 1970 00:00:00 +0000'
    >>> a.status = 'closed'
    >>> b = bd_new.bug_from_uuid('b')
    >>> bd_new.remove_bug(b)
    >>> c = bd_new.new_bug('Bug C', _uuid='c')
    >>> d = Diff(bd, bd_new)
    >>> r = d.report_tree()
    >>> print '\\n'.join(r.paths())
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
      abc/c:om: Bug C
    Removed bugs:
      abc/b:cm: Bug B
    Modified bugs:
      abc/a:cm: Bug A
        Changed bug settings:
          status: open -> closed
        New comments:
          from John Doe <j@doe.com> on Thu, 01 Jan 1970 00:00:00 +0000
            I'm closing this bug...

    You can also limit the report generation by providing a list of
    subscriptions.

    >>> subscriptions = [Subscription('DIR', BUGDIR_TYPE_NEW),
    ...                  Subscription('b', BUG_TYPE_ALL)]
    >>> r = d.report_tree(subscriptions)
    >>> print r.report_string()
    New bugs:
      abc/c:om: Bug C
    Removed bugs:
      abc/b:cm: Bug B

    While sending subscriptions to report_tree() makes the report
    generation more efficient (because you may not need to compare
    _all_ the bugs, etc.), sometimes you will have several sets of
    subscriptions.  In that case, it's better to run full_report()
    first, and then use report_tree() to avoid redundant comparisons.

    >>> d.full_report()
    >>> print d.report_tree([subscriptions[0]]).report_string()
    New bugs:
      abc/c:om: Bug C
    >>> print d.report_tree([subscriptions[1]]).report_string()
    Removed bugs:
      abc/b:cm: Bug B

    >>> bd.cleanup()
    """
    def __init__(self, old_bugdir, new_bugdir):
        self.old_bugdir = old_bugdir
        self.new_bugdir = new_bugdir

    # data assembly methods

    def _changed_bugs(self, subscriptions):
        """
        Search for differences in all bugs between .old_bugdir and
        .new_bugdir.  Returns
          (added_bugs, modified_bugs, removed_bugs)
        where added_bugs and removed_bugs are lists of added and
        removed bugs respectively.  modified_bugs is a list of
        (old_bug,new_bug) pairs.
        """
        bugdir_types = [s.type for s in subscriptions if s.id == BUGDIR_ID]
        new_uuids = []
        old_uuids = []
        for bd_type in [BUGDIR_TYPE_ALL, BUGDIR_TYPE_NEW, BUGDIR_TYPE_MOD]:
            if bd_type in bugdir_types:
                new_uuids = list(self.new_bugdir.uuids())
                break
        for bd_type in [BUGDIR_TYPE_ALL, BUGDIR_TYPE_REM]:
            if bd_type in bugdir_types:
                old_uuids = list(self.old_bugdir.uuids())
                break
        subscribed_bugs = []
        for s in subscriptions:
            if s.id != BUGDIR_ID:
                try:
                    bug = self.new_bugdir.bug_from_uuid(s.id)
                except libbe.bugdir.NoBugMatches:
                    bug = self.old_bugdir.bug_from_uuid(s.id)
                subscribed_bugs.append(bug.uuid)
        new_uuids.extend([s for s in subscribed_bugs
                          if self.new_bugdir.has_bug(s)])
        new_uuids = sorted(set(new_uuids))
        old_uuids.extend([s for s in subscribed_bugs
                          if self.old_bugdir.has_bug(s)])
        old_uuids = sorted(set(old_uuids))

        added = []
        removed = []
        modified = []
        if hasattr(self.old_bugdir, 'changed'):
            # take advantage of a RevisionedBugDir-style changed() method
            new_ids,mod_ids,rem_ids = self.old_bugdir.changed()
            for id in new_ids:
                for a_id in self.new_bugdir.storage.ancestors(id):
                    if a_id.count('/') == 0:
                        if a_id in [b.id.storage() for b in added]:
                            break
                        try:
                            bug = self.new_bugdir.bug_from_uuid(a_id)
                            added.append(bug)
                        except libbe.bugdir.NoBugMatches:
                            pass
            for id in rem_ids:
                for a_id in self.old_bugdir.storage.ancestors(id):
                    if a_id.count('/') == 0:
                        if a_id in [b.id.storage() for b in removed]:
                            break
                        try:
                            bug = self.old_bugdir.bug_from_uuid(a_id)
                            removed.append(bug)
                        except libbe.bugdir.NoBugMatches:
                            pass
            for id in mod_ids:
                for a_id in self.new_bugdir.storage.ancestors(id):
                    if a_id.count('/') == 0:
                        if a_id in [b[0].id.storage() for b in modified]:
                            break
                        try:
                            new_bug = self.new_bugdir.bug_from_uuid(a_id)
                            old_bug = self.old_bugdir.bug_from_uuid(a_id)
                            modified.append((old_bug, new_bug))
                        except libbe.bugdir.NoBugMatches:
                            pass
        else:
            for uuid in new_uuids:
                new_bug = self.new_bugdir.bug_from_uuid(uuid)
                try:
                    old_bug = self.old_bugdir.bug_from_uuid(uuid)
                except KeyError:
                    if BUGDIR_TYPE_ALL in bugdir_types \
                            or BUGDIR_TYPE_NEW in bugdir_types \
                            or uuid in subscribed_bugs:
                        added.append(new_bug)
                    continue
                if BUGDIR_TYPE_ALL in bugdir_types \
                        or BUGDIR_TYPE_MOD in bugdir_types \
                        or uuid in subscribed_bugs:
                    if old_bug.storage != None and old_bug.storage.is_readable():
                        old_bug.load_comments()
                    if new_bug.storage != None and new_bug.storage.is_readable():
                        new_bug.load_comments()
                    if old_bug != new_bug:
                        modified.append((old_bug, new_bug))
            for uuid in old_uuids:
                if not self.new_bugdir.has_bug(uuid):
                    old_bug = self.old_bugdir.bug_from_uuid(uuid)
                    removed.append(old_bug)
        added.sort()
        removed.sort()
        modified.sort(self._bug_modified_cmp)
        return (added, modified, removed)
    def _bug_modified_cmp(self, left, right):
        return cmp(left[1], right[1])
    def _changed_comments(self, old, new):
        """
        Search for differences in all loaded comments between the bugs
        old and new.  Returns
          (added_comments, modified_comments, removed_comments)
        analogous to ._changed_bugs.
        """
        if hasattr(self, '__changed_comments'):
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
                old_comment = old.comment_from_uuid(uuid)
                removed.append(old_comment)
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
        attributes = [setting_name_to_attr_name(None, p)
                      for p in properties]
        return self._attribute_changes(old, new, attributes)
    def _bugdir_attribute_changes(self):
        return self._settings_properties_attribute_changes( \
            self.old_bugdir, self.new_bugdir)
    def _bug_attribute_changes(self, old, new):
        return self._settings_properties_attribute_changes(old, new)
    def _comment_attribute_changes(self, old, new):
        return self._settings_properties_attribute_changes(old, new)

    # report generation methods

    def full_report(self, diff_tree=DiffTree):
        """
        Generate a full report for efficiency if you'll be using
        .report_tree() with several sets of subscriptions.
        """
        self._cached_full_report = self.report_tree(diff_tree=diff_tree,
                                                    allow_cached=False)
        self._cached_full_report_diff_tree = diff_tree
    def _sub_report(self, subscriptions):
        """
        Return ._cached_full_report masked for subscriptions.
        """
        root = self._cached_full_report
        bugdir_types = [s.type for s in subscriptions if s.id == BUGDIR_ID]
        subscribed_bugs = [s.id for s in subscriptions
                           if BUG_TYPE_ALL.has_descendant( \
                                     s.type, match_self=True)]
        selected_by_bug = [node.name
                           for node in root.child_by_path('bugdir/bugs')]
        if BUGDIR_TYPE_ALL in bugdir_types:
            for node in root.traverse():
                node.masked = False
            selected_by_bug = []
        else:
            try:
                node = root.child_by_path('bugdir/settings')
                node.masked = True
            except KeyError:
                pass
        for name,type in (('new', BUGDIR_TYPE_NEW),
                          ('mod', BUGDIR_TYPE_MOD),
                          ('rem', BUGDIR_TYPE_REM)):
            if type in bugdir_types:
                bugs = root.child_by_path('bugdir/bugs/%s' % name)
                for bug_node in bugs:
                    for node in bug_node.traverse():
                        node.masked = False
                selected_by_bug.remove(name)
        for name in selected_by_bug:
            bugs = root.child_by_path('bugdir/bugs/%s' % name)
            for bug_node in bugs:
                if bug_node.name in subscribed_bugs:
                    for node in bug_node.traverse():
                        node.masked = False
                else:
                    for node in bug_node.traverse():
                        node.masked = True
        return root
    def report_tree(self, subscriptions=None, diff_tree=DiffTree,
                    allow_cached=True):
        """
        Pretty bare to make it easy to adjust to specific cases.  You
        can pass in a DiffTree subclass via diff_tree to override the
        default report assembly process.
        """
        if allow_cached == True \
                and hasattr(self, '_cached_full_report') \
                and diff_tree == self._cached_full_report_diff_tree:
            return self._sub_report(subscriptions)
        if subscriptions == None:
            subscriptions = [Subscription(BUGDIR_ID, BUGDIR_TYPE_ALL)]
        bugdir_settings = sorted(self.new_bugdir.settings_properties)
        root = diff_tree('bugdir')
        bugdir_subscriptions = [s.type for s in subscriptions
                                if s.id == BUGDIR_ID]
        if BUGDIR_TYPE_ALL in bugdir_subscriptions:
            bugdir_attribute_changes = self._bugdir_attribute_changes()
            if len(bugdir_attribute_changes) > 0:
                bugdir = diff_tree('settings', bugdir_attribute_changes,
                                   self.bugdir_attribute_change_string)
                root.append(bugdir)
        bug_root = diff_tree('bugs')
        root.append(bug_root)
        add,mod,rem = self._changed_bugs(subscriptions)
        bnew = diff_tree('new', 'New bugs:', requires_children=True)
        bug_root.append(bnew)
        for bug in add:
            b = diff_tree(bug.uuid, bug, self.bug_add_string)
            bnew.append(b)
        brem = diff_tree('rem', 'Removed bugs:', requires_children=True)
        bug_root.append(brem)
        for bug in rem:
            b = diff_tree(bug.uuid, bug, self.bug_rem_string)
            brem.append(b)
        bmod = diff_tree('mod', 'Modified bugs:', requires_children=True)
        bug_root.append(bmod)
        for old,new in mod:
            b = diff_tree(new.uuid, (old,new), self.bug_mod_string)
            bmod.append(b)
            bug_attribute_changes = self._bug_attribute_changes(old, new)
            if len(bug_attribute_changes) > 0:
                bset = diff_tree('settings', bug_attribute_changes,
                                 self.bug_attribute_change_string)
                b.append(bset)
            if old.summary != new.summary:
                data = (old.summary, new.summary)
                bsum = diff_tree('summary', data, self.bug_summary_change_string)
                b.append(bsum)
            cr = diff_tree('comments')
            b.append(cr)
            a,m,d = self._changed_comments(old, new)
            cnew = diff_tree('new', 'New comments:', requires_children=True)
            for comment in a:
                c = diff_tree(comment.uuid, comment, self.comment_add_string)
                cnew.append(c)
            crem = diff_tree('rem', 'Removed comments:',requires_children=True)
            for comment in d:
                c = diff_tree(comment.uuid, comment, self.comment_rem_string)
                crem.append(c)
            cmod = diff_tree('mod','Modified comments:',requires_children=True)
            for o,n in m:
                c = diff_tree(n.uuid, (o,n), self.comment_mod_string)
                cmod.append(c)
                comm_attribute_changes = self._comment_attribute_changes(o, n)
                if len(comm_attribute_changes) > 0:
                    cset = diff_tree('settings', comm_attribute_changes,
                                     self.comment_attribute_change_string)
                if o.body != n.body:
                    data = (o.body, n.body)
                    cbody = diff_tree('cbody', data,
                                      self.comment_body_change_string)
                    c.append(cbody)
            cr.extend([cnew, crem, cmod])
        return root

    # change data -> string methods.
    # Feel free to play with these in subclasses.

    def attribute_change_string(self, attribute_changes, indent=0):
        indent_string = '  '*indent
        change_strings = [u'%s: %s -> %s' % f for f in attribute_changes]
        for i,change_string in enumerate(change_strings):
            change_strings[i] = indent_string+change_string
        return u'\n'.join(change_strings)
    def bugdir_attribute_change_string(self, attribute_changes):
        return 'Changed bug directory settings:\n%s' % \
            self.attribute_change_string(attribute_changes, indent=1)
    def bug_attribute_change_string(self, attribute_changes):
        return 'Changed bug settings:\n%s' % \
            self.attribute_change_string(attribute_changes, indent=1)
    def comment_attribute_change_string(self, attribute_changes):
        return 'Changed comment settings:\n%s' % \
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
        return 'summary changed:\n  %s\n  %s' % (old_summary, new_summary)
    def _comment_summary_string(self, comment):
        return 'from %s on %s' % (comment.author, time_to_str(comment.time))
    def comment_add_string(self, comment):
        summary = self._comment_summary_string(comment)
        first_line = comment.body.splitlines()[0]
        return '%s\n  %s...' % (summary, first_line)
    def comment_rem_string(self, comment):
        summary = self._comment_summary_string(comment)
        first_line = comment.body.splitlines()[0]
        return '%s\n  %s...' % (summary, first_line)
    def comment_mod_string(self, comments):
        old_comment,new_comment = comments
        return self._comment_summary_string(new_comment)
    def comment_body_change_string(self, bodies):
        old_body,new_body = bodies
        return ''.join(difflib.unified_diff(
                old_body.splitlines(True),
                new_body.splitlines(True),
                'before', 'after'))
