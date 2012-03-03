# Copyright (C) 2008-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Robert Lehmann <mail@robertlehmann.de>
#                         Thomas Habets <thomas@habets.pp.se>
#                         Valtteri Kokkoniemi <rvk@iki.fi>
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

"""Define the :class:`Bug` class for representing bugs.
"""

import copy
import os
import os.path
import errno
import sys
import time
import types
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
import xml.sax.saxutils

import libbe
import libbe.util.id
from libbe.storage.util.properties import Property, doc_property, \
    local_property, defaulting_property, checked_property, cached_property, \
    primed_property, change_hook_property, settings_property
import libbe.storage.util.settings_object as settings_object
import libbe.storage.util.mapfile as mapfile
import libbe.comment as comment
import libbe.util.utility as utility

if libbe.TESTING == True:
    import doctest


### Define and describe valid bug categories
# Use a tuple of (category, description) tuples since we don't have
# ordered dicts in Python yet http://www.python.org/dev/peps/pep-0372/

# in order of increasing severity.  (name, description) pairs
severity_def = (
  ("target", "The issue is a target or milestone, not a bug."),
  ("wishlist","A feature that could improve usefulness, but not a bug."),
  ("minor","The standard bug level."),
  ("serious","A bug that requires workarounds."),
  ("critical","A bug that prevents some features from working at all."),
  ("fatal","A bug that makes the package unusable."))

# in order of increasing resolution
# roughly following http://www.bugzilla.org/docs/3.2/en/html/lifecycle.html
active_status_def = (
  ("unconfirmed","A possible bug which lacks independent existance confirmation."),
  ("open","A working bug that has not been assigned to a developer."),
  ("assigned","A working bug that has been assigned to a developer."),
  ("test","The code has been adjusted, but the fix is still being tested."))
inactive_status_def = (
  ("closed", "The bug is no longer relevant."),
  ("fixed", "The bug should no longer occur."),
  ("wontfix","It's not a bug, it's a feature."))


### Convert the description tuples to more useful formats

severity_values = ()
severity_description = {}
severity_index = {}
def load_severities(severity_def):
    global severity_values
    global severity_description
    global severity_index
    if severity_def == None:
        return
    severity_values = tuple([val for val,description in severity_def])
    severity_description = dict(severity_def)
    severity_index = {}
    for i,severity in enumerate(severity_values):
        severity_index[severity] = i
load_severities(severity_def)

active_status_values = []
inactive_status_values = []
status_values = []
status_description = {}
status_index = {}
def load_status(active_status_def, inactive_status_def):
    global active_status_values
    global inactive_status_values
    global status_values
    global status_description
    global status_index
    if active_status_def == None:
        active_status_def = globals()["active_status_def"]
    if inactive_status_def == None:
        inactive_status_def = globals()["inactive_status_def"]
    active_status_values = tuple([val for val,description in active_status_def])
    inactive_status_values = tuple([val for val,description in inactive_status_def])
    status_values = active_status_values + inactive_status_values
    status_description = dict(tuple(active_status_def) + tuple(inactive_status_def))
    status_index = {}
    for i,status in enumerate(status_values):
        status_index[status] = i
load_status(active_status_def, inactive_status_def)


class Bug (settings_object.SavedSettingsObject):
    """A bug (or issue) is a place to store attributes and attach
    :class:`~libbe.comment.Comment`\s.  In mailing-list terms, a bug is
    analogous to a thread.  Bugs are normally stored in
    :class:`~libbe.bugdir.BugDir`\s.

    >>> b = Bug()
    >>> print b.status
    open
    >>> print b.severity
    minor

    There are two formats for time, int and string.  Setting either
    one will adjust the other appropriately.  The string form is the
    one stored in the bug's settings file on disk.

    >>> print type(b.time)
    <type 'int'>
    >>> print type(b.time_string)
    <type 'str'>
    >>> b.time = 0
    >>> print b.time_string
    Thu, 01 Jan 1970 00:00:00 +0000
    >>> b.time_string="Thu, 01 Jan 1970 00:01:00 +0000"
    >>> b.time
    60
    >>> print b.settings["time"]
    Thu, 01 Jan 1970 00:01:00 +0000
    """
    settings_properties = []
    required_saved_properties = []
    _prop_save_settings = settings_object.prop_save_settings
    _prop_load_settings = settings_object.prop_load_settings
    def _versioned_property(settings_properties=settings_properties,
                            required_saved_properties=required_saved_properties,
                            **kwargs):
        if "settings_properties" not in kwargs:
            kwargs["settings_properties"] = settings_properties
        if "required_saved_properties" not in kwargs:
            kwargs["required_saved_properties"]=required_saved_properties
        return settings_object.versioned_property(**kwargs)

    @_versioned_property(name="severity",
                         doc="A measure of the bug's importance",
                         default="minor",
                         check_fn=lambda s: s in severity_values,
                         require_save=True)
    def severity(): return {}

    @_versioned_property(name="status",
                         doc="The bug's current status",
                         default="open",
                         check_fn=lambda s: s in status_values,
                         require_save=True)
    def status(): return {}

    @property
    def active(self):
        return self.status in active_status_values

    @_versioned_property(name="creator",
                         doc="The user who entered the bug into the system")
    def creator(): return {}

    @_versioned_property(name="reporter",
                         doc="The user who reported the bug")
    def reporter(): return {}

    @_versioned_property(name="assigned",
                         doc="The developer in charge of the bug")
    def assigned(): return {}

    @_versioned_property(name="time",
                         doc="An RFC 2822 timestamp for bug creation")
    def time_string(): return {}

    def _get_time(self):
        if self.time_string == None:
            self._cached_time_string = None
            self._cached_time = None
            return None
        if (not hasattr(self, '_cached_time_string')
            or self.time_string != self._cached_time_string):
            self._cached_time_string = self.time_string
            self._cached_time = utility.str_to_time(self.time_string)
        return self._cached_time
    def _set_time(self, value):
        if not hasattr(self, '_cached_time') or value != self._cached_time:
            self.time_string = utility.time_to_str(value)
            self._cached_time_string = self.time_string
            self._cached_time = value
    time = property(fget=_get_time,
                    fset=_set_time,
                    doc="An integer version of .time_string")

    def _extra_strings_check_fn(value):
        return utility.iterable_full_of_strings(value, \
                         alternative=settings_object.EMPTY)
    def _extra_strings_change_hook(self, old, new):
        self.extra_strings.sort() # to make merging easier
        self._prop_save_settings(old, new)
    @_versioned_property(name="extra_strings",
                         doc="Space for an array of extra strings.  Useful for storing state for functionality implemented purely in becommands/<some_function>.py.",
                         default=[],
                         check_fn=_extra_strings_check_fn,
                         change_hook=_extra_strings_change_hook,
                         mutable=True)
    def extra_strings(): return {}

    @_versioned_property(name="summary",
                         doc="A one-line bug description")
    def summary(): return {}

    def _get_comment_root(self, load_full=False):
        if self.storage != None and self.storage.is_readable():
            return comment.load_comments(self, load_full=load_full)
        else:
            return comment.Comment(self, uuid=comment.INVALID_UUID)

    @Property
    @cached_property(generator=_get_comment_root)
    @local_property("comment_root")
    @doc_property(doc="The trunk of the comment tree.  We use a dummy root comment by default, because there can be several comment threads rooted on the same parent bug.  To simplify comment interaction, we condense these threads into a single thread with a Comment dummy root.")
    def comment_root(): return {}

    def __init__(self, bugdir=None, uuid=None, from_storage=False,
                 load_comments=False, summary=None):
        settings_object.SavedSettingsObject.__init__(self)
        self.bugdir = bugdir
        self.storage = None
        self.uuid = uuid
        self.id = libbe.util.id.ID(self, 'bug')
        if from_storage == False:
            if uuid == None:
                self.uuid = libbe.util.id.uuid_gen()
            self.time = int(time.time()) # only save to second precision
            self.summary = summary
            dummy = self.comment_root
        if self.bugdir != None:
            self.storage = self.bugdir.storage
        if from_storage == False:
            if self.storage != None and self.storage.is_writeable():
                self.save()

    def __repr__(self):
        return "Bug(uuid=%r)" % self.uuid

    def __str__(self):
        return self.string(shortlist=True)

    def __cmp__(self, other):
        return cmp_full(self, other)

    # serializing methods

    def _setting_attr_string(self, setting):
        value = getattr(self, setting)
        if value == None:
            return ""
        if type(value) not in types.StringTypes:
            return str(value)
        return value

    def string(self, shortlist=False, show_comments=False):
        if shortlist == False:
            if self.time == None:
                timestring = ""
            else:
                htime = utility.handy_time(self.time)
                timestring = "%s (%s)" % (htime, self.time_string)
            info = [("ID", self.uuid),
                    ("Short name", self.id.user()),
                    ("Severity", self.severity),
                    ("Status", self.status),
                    ("Assigned", self._setting_attr_string("assigned")),
                    ("Reporter", self._setting_attr_string("reporter")),
                    ("Creator", self._setting_attr_string("creator")),
                    ("Created", timestring)]
            for estr in self.extra_strings:
                info.append(('Extra string', estr))
            longest_key_len = max([len(k) for k,v in info])
            infolines = ["  %*s : %s\n" %(longest_key_len,k,v) for k,v in info]
            bugout = "".join(infolines) + "%s" % self.summary.rstrip('\n')
        else:
            statuschar = self.status[0]
            severitychar = self.severity[0]
            chars = "%c%c" % (statuschar, severitychar)
            bugout = "%s:%s: %s" % (self.id.user(),chars,self.summary.rstrip('\n'))

        if show_comments == True:
            self.comment_root.sort(cmp=libbe.comment.cmp_time, reverse=True)
            comout = self.comment_root.string_thread(flatten=False)
            output = bugout + '\n' + comout.rstrip('\n')
        else :
            output = bugout
        return output

    def xml(self, indent=0, show_comments=False):
        if self.time == None:
            timestring = ""
        else:
            timestring = utility.time_to_str(self.time)

        info = [('uuid', self.uuid),
                ('short-name', self.id.user()),
                ('severity', self.severity),
                ('status', self.status),
                ('assigned', self.assigned),
                ('reporter', self.reporter),
                ('creator', self.creator),
                ('created', timestring),
                ('summary', self.summary)]
        lines = ['<bug>']
        for (k,v) in info:
            if v is not None:
                lines.append('  <%s>%s</%s>' % (k,xml.sax.saxutils.escape(v),k))
        for estr in self.extra_strings:
            lines.append('  <extra-string>%s</extra-string>' % estr)
        if show_comments == True:
            comout = self.comment_root.xml_thread(indent=indent+2)
            if len(comout) > 0:
                lines.append(comout)
        lines.append('</bug>')
        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def from_xml(self, xml_string, preserve_uuids=False, verbose=True):
        u"""
        Note: If a bug uuid is given, set .alt_id to it's value.
        >>> bugA = Bug(uuid="0123", summary="Need to test Bug.from_xml()")
        >>> bugA.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> bugA.creator = u'Fran\xe7ois'
        >>> bugA.extra_strings += ['TAG: very helpful']
        >>> commA = bugA.comment_root.new_reply(body='comment A')
        >>> commB = bugA.comment_root.new_reply(body='comment B')
        >>> commC = commA.new_reply(body='comment C')
        >>> xml = bugA.xml(show_comments=True)
        >>> bugB = Bug()
        >>> bugB.from_xml(xml, verbose=True)
        >>> bugB.xml(show_comments=True) == xml
        False
        >>> bugB.uuid = bugB.alt_id
        >>> for comm in bugB.comments():
        ...     comm.uuid = comm.alt_id
        ...     comm.alt_id = None
        >>> bugB.xml(show_comments=True) == xml
        True
        >>> bugB.explicit_attrs  # doctest: +NORMALIZE_WHITESPACE
        ['severity', 'status', 'creator', 'time', 'summary']
        >>> len(list(bugB.comments()))
        3
        >>> bugC = Bug()
        >>> bugC.from_xml(xml, preserve_uuids=True)
        >>> bugC.uuid == bugA.uuid
        True
        """
        if type(xml_string) == types.UnicodeType:
            xml_string = xml_string.strip().encode('unicode_escape')
        if hasattr(xml_string, 'getchildren'): # already an ElementTree Element
            bug = xml_string
        else:
            bug = ElementTree.XML(xml_string)
        if bug.tag != 'bug':
            raise utility.InvalidXML( \
                'bug', bug, 'root element must be <comment>')
        tags=['uuid','short-name','severity','status','assigned',
              'reporter', 'creator','created','summary','extra-string']
        self.explicit_attrs = []
        uuid = None
        estrs = []
        comments = []
        for child in bug.getchildren():
            if child.tag == 'short-name':
                pass
            elif child.tag == 'comment':
                comm = comment.Comment(bug=self)
                comm.from_xml(
                    child, preserve_uuids=preserve_uuids, verbose=verbose)
                comments.append(comm)
                continue
            elif child.tag in tags:
                if child.text == None or len(child.text) == 0:
                    text = settings_object.EMPTY
                else:
                    text = xml.sax.saxutils.unescape(child.text)
                    text = text.decode('unicode_escape').strip()
                if child.tag == 'uuid' and not preserve_uuids:
                    uuid = text
                    continue # don't set the bug's uuid tag.
                elif child.tag == 'created':
                    if text is not settings_object.EMPTY:
                        self.time = utility.str_to_time(text)
                        self.explicit_attrs.append('time')
                    continue
                elif child.tag == 'extra-string':
                    estrs.append(text)
                    continue # don't set the bug's extra_string yet.
                attr_name = child.tag.replace('-','_')
                self.explicit_attrs.append(attr_name)
                setattr(self, attr_name, text)
            elif verbose == True:
                print >> sys.stderr, 'Ignoring unknown tag %s in %s' \
                    % (child.tag, comment.tag)
        if uuid != self.uuid:
            if not hasattr(self, 'alt_id') or self.alt_id == None:
                self.alt_id = uuid
        self.extra_strings = estrs
        self.add_comments(comments, ignore_missing_references=True)

    def add_comment(self, comment, *args, **kwargs):
        """
        Add a comment too the current bug, under the parent specified
        by comment.in_reply_to.
        Note: If a bug uuid is given, set .alt_id to it's value.

        >>> bugA = Bug(uuid='0123', summary='Need to test Bug.add_comment()')
        >>> bugA.creator = 'Jack'
        >>> commA = bugA.comment_root.new_reply(body='comment A')
        >>> commA.uuid = 'commA'
        >>> commB = comment.Comment(body='comment B')
        >>> commB.uuid = 'commB'
        >>> bugA.add_comment(commB)
        >>> commC = comment.Comment(body='comment C')
        >>> commC.uuid = 'commC'
        >>> commC.in_reply_to = commA.uuid
        >>> bugA.add_comment(commC)
        >>> print bugA.xml(show_comments=True)  # doctest: +ELLIPSIS
        <bug>
          <uuid>0123</uuid>
          <short-name>/012</short-name>
          <severity>minor</severity>
          <status>open</status>
          <creator>Jack</creator>
          <created>...</created>
          <summary>Need to test Bug.add_comment()</summary>
          <comment>
            <uuid>commA</uuid>
            <short-name>/012/commA</short-name>
            <author></author>
            <date>...</date>
            <content-type>text/plain</content-type>
            <body>comment A</body>
          </comment>
          <comment>
            <uuid>commC</uuid>
            <short-name>/012/commC</short-name>
            <in-reply-to>commA</in-reply-to>
            <author></author>
            <date>...</date>
            <content-type>text/plain</content-type>
            <body>comment C</body>
          </comment>
          <comment>
            <uuid>commB</uuid>
            <short-name>/012/commB</short-name>
            <author></author>
            <date>...</date>
            <content-type>text/plain</content-type>
            <body>comment B</body>
          </comment>
        </bug>
        """
        self.add_comments([comment], **kwargs)

    def add_comments(self, comments, default_parent=None,
                     ignore_missing_references=False):
        """
        Convert a raw list of comments to single root comment.  If a
        comment does not specify a parent with .in_reply_to, the
        parent defaults to .comment_root, but you can specify another
        default parent via default_parent.
        """
        uuid_map = {}
        if default_parent == None:
            default_parent = self.comment_root
        for c in list(self.comments()) + comments:
            assert c.uuid != None
            assert c.uuid not in uuid_map
            uuid_map[c.uuid] = c
            if c.alt_id != None:
                uuid_map[c.alt_id] = c
        uuid_map[None] = self.comment_root
        uuid_map[comment.INVALID_UUID] = self.comment_root
        if default_parent != self.comment_root:
            assert default_parent.uuid in uuid_map, default_parent.uuid
        for c in comments:
            if c.in_reply_to == None \
                    and default_parent.uuid != comment.INVALID_UUID:
                c.in_reply_to = default_parent.uuid
            elif c.in_reply_to == comment.INVALID_UUID:
                c.in_reply_to = None
            try:
                parent = uuid_map[c.in_reply_to]
            except KeyError:
                if ignore_missing_references == True:
                    print >> sys.stderr, \
                        'Ignoring missing reference to %s' % c.in_reply_to
                    parent = default_parent
                    if parent.uuid != comment.INVALID_UUID:
                        c.in_reply_to = parent.uuid
                else:
                    raise comment.MissingReference(c)
            c.bug = self
            parent.append(c)

    def merge(self, other, accept_changes=True,
              accept_extra_strings=True, accept_comments=True,
              change_exception=False):
        """
        Merge info from other into this bug.  Overrides any attributes
        in self that are listed in other.explicit_attrs.

        >>> bugA = Bug(uuid='0123', summary='Need to test Bug.merge()')
        >>> bugA.date = 'Thu, 01 Jan 1970 00:00:00 +0000'
        >>> bugA.creator = 'Frank'
        >>> bugA.extra_strings += ['TAG: very helpful']
        >>> bugA.extra_strings += ['TAG: favorite']
        >>> commA = bugA.comment_root.new_reply(body='comment A')
        >>> commA.uuid = 'uuid-commA'
        >>> bugB = Bug(uuid='3210', summary='More tests for Bug.merge()')
        >>> bugB.date = 'Fri, 02 Jan 1970 00:00:00 +0000'
        >>> bugB.creator = 'John'
        >>> bugB.explicit_attrs = ['creator', 'summary']
        >>> bugB.extra_strings += ['TAG: very helpful']
        >>> bugB.extra_strings += ['TAG: useful']
        >>> commB = bugB.comment_root.new_reply(body='comment B')
        >>> commB.uuid = 'uuid-commB'
        >>> bugA.merge(bugB, accept_changes=False, accept_extra_strings=False,
        ...            accept_comments=False, change_exception=False)
        >>> print bugA.creator
        Frank
        >>> bugA.merge(bugB, accept_changes=False, accept_extra_strings=False,
        ...            accept_comments=False, change_exception=True)
        Traceback (most recent call last):
          ...
        ValueError: Merge would change creator "Frank"->"John" for bug 0123
        >>> print bugA.creator
        Frank
        >>> bugA.merge(bugB, accept_changes=True, accept_extra_strings=False,
        ...            accept_comments=False, change_exception=True)
        Traceback (most recent call last):
          ...
        ValueError: Merge would add extra string "TAG: useful" for bug 0123
        >>> print bugA.creator
        John
        >>> print bugA.extra_strings
        ['TAG: favorite', 'TAG: very helpful']
        >>> bugA.merge(bugB, accept_changes=True, accept_extra_strings=True,
        ...            accept_comments=False, change_exception=True)
        Traceback (most recent call last):
          ...
        ValueError: Merge would add comment uuid-commB (alt: None) to bug 0123
        >>> print bugA.extra_strings
        ['TAG: favorite', 'TAG: useful', 'TAG: very helpful']
        >>> bugA.merge(bugB, accept_changes=True, accept_extra_strings=True,
        ...            accept_comments=True, change_exception=True)
        >>> print bugA.xml(show_comments=True)  # doctest: +ELLIPSIS
        <bug>
          <uuid>0123</uuid>
          <short-name>/012</short-name>
          <severity>minor</severity>
          <status>open</status>
          <creator>John</creator>
          <created>...</created>
          <summary>More tests for Bug.merge()</summary>
          <extra-string>TAG: favorite</extra-string>
          <extra-string>TAG: useful</extra-string>
          <extra-string>TAG: very helpful</extra-string>
          <comment>
            <uuid>uuid-commA</uuid>
            <short-name>/012/uuid-commA</short-name>
            <author></author>
            <date>...</date>
            <content-type>text/plain</content-type>
            <body>comment A</body>
          </comment>
          <comment>
            <uuid>uuid-commB</uuid>
            <short-name>/012/uuid-commB</short-name>
            <author></author>
            <date>...</date>
            <content-type>text/plain</content-type>
            <body>comment B</body>
          </comment>
        </bug>
        """
        for attr in other.explicit_attrs:
            old = getattr(self, attr)
            new = getattr(other, attr)
            if old != new:
                if accept_changes == True:
                    setattr(self, attr, new)
                elif change_exception == True:
                    raise ValueError, \
                        'Merge would change %s "%s"->"%s" for bug %s' \
                        % (attr, old, new, self.uuid)
        for estr in other.extra_strings:
            if not estr in self.extra_strings:
                if accept_extra_strings == True:
                    self.extra_strings.append(estr)
                elif change_exception == True:
                    raise ValueError, \
                        'Merge would add extra string "%s" for bug %s' \
                        % (estr, self.uuid)
        for o_comm in other.comments():
            try:
                s_comm = self.comment_root.comment_from_uuid(o_comm.uuid)
            except KeyError, e:
                try:
                    s_comm = self.comment_root.comment_from_uuid(o_comm.alt_id)
                except KeyError, e:
                    s_comm = None
            if s_comm == None:
                if accept_comments == True:
                    o_comm_copy = copy.copy(o_comm)
                    o_comm_copy.bug = self
                    o_comm_copy.id = libbe.util.id.ID(o_comm_copy, 'comment')
                    self.comment_root.add_reply(o_comm_copy)
                elif change_exception == True:
                    raise ValueError, \
                        'Merge would add comment %s (alt: %s) to bug %s' \
                        % (o_comm.uuid, o_comm.alt_id, self.uuid)
            else:
                s_comm.merge(o_comm, accept_changes=accept_changes,
                             accept_extra_strings=accept_extra_strings,
                             change_exception=change_exception)

    # methods for saving/loading/acessing settings and properties.

    def load_settings(self, settings_mapfile=None):
        if settings_mapfile == None:
            settings_mapfile = self.storage.get(
                self.id.storage('values'), '\n')
        try:
            settings = mapfile.parse(settings_mapfile)
        except mapfile.InvalidMapfileContents, e:
            raise Exception('Invalid settings file for bug %s\n'
                            '(BE version missmatch?)' % self.id.user())
        self._setup_saved_settings(settings)

    def save_settings(self):
        mf = mapfile.generate(self._get_saved_settings())
        self.storage.set(self.id.storage('values'), mf)

    def save(self):
        """
        Save any loaded contents to storage.  Because of lazy loading
        of comments, this is actually not too inefficient.

        However, if self.storage.is_writeable() == True, then any
        changes are automatically written to storage as soon as they
        happen, so calling this method will just waste time (unless
        something else has been messing with your stored files).
        """
        assert self.storage != None, "Can't save without storage"
        if self.bugdir != None:
            parent = self.bugdir.id.storage()
        else:
            parent = None
        self.storage.add(self.id.storage(), parent=parent, directory=True)
        self.storage.add(self.id.storage('values'), parent=self.id.storage(),
                         directory=False)
        self.save_settings()
        if len(self.comment_root) > 0:
            comment.save_comments(self)

    def load_comments(self, load_full=True):
        if load_full == True:
            # Force a complete load of the whole comment tree
            self.comment_root = self._get_comment_root(load_full=True)
        else:
            # Setup for fresh lazy-loading.  Clear _comment_root, so
            # next _get_comment_root returns a fresh version.  Turn of
            # writing temporarily so we don't write our blank comment
            # tree to disk.
            w = self.storage.writeable
            self.storage.writeable = False
            self.comment_root = None
            self.storage.writeable = w

    def remove(self):
        self.storage.recursive_remove(self.id.storage())

    # methods for managing comments

    def uuids(self):
        for comment in self.comments():
            yield comment.uuid

    def comments(self):
        for comment in self.comment_root.traverse():
            yield comment

    def new_comment(self, body=None):
        comm = self.comment_root.new_reply(body=body)
        return comm

    def comment_from_uuid(self, uuid, *args, **kwargs):
        return self.comment_root.comment_from_uuid(uuid, *args, **kwargs)

    # methods for id generation

    def sibling_uuids(self):
        if self.bugdir != None:
            return self.bugdir.uuids()
        return []


# The general rule for bug sorting is that "more important" bugs are
# less than "less important" bugs.  This way sorting a list of bugs
# will put the most important bugs first in the list.  When relative
# importance is unclear, the sorting follows some arbitrary convention
# (i.e. dictionary order).

def cmp_severity(bug_1, bug_2):
    """
    Compare the severity levels of two bugs, with more severe bugs
    comparing as less.

    >>> bugA = Bug()
    >>> bugB = Bug()
    >>> bugA.severity = bugB.severity = "wishlist"
    >>> cmp_severity(bugA, bugB) == 0
    True
    >>> bugB.severity = "minor"
    >>> cmp_severity(bugA, bugB) > 0
    True
    >>> bugA.severity = "critical"
    >>> cmp_severity(bugA, bugB) < 0
    True
    """
    if not hasattr(bug_2, "severity") :
        return 1
    return -cmp(severity_index[bug_1.severity], severity_index[bug_2.severity])

def cmp_status(bug_1, bug_2):
    """
    Compare the status levels of two bugs, with more "open" bugs
    comparing as less.

    >>> bugA = Bug()
    >>> bugB = Bug()
    >>> bugA.status = bugB.status = "open"
    >>> cmp_status(bugA, bugB) == 0
    True
    >>> bugB.status = "closed"
    >>> cmp_status(bugA, bugB) < 0
    True
    >>> bugA.status = "fixed"
    >>> cmp_status(bugA, bugB) > 0
    True
    """
    if not hasattr(bug_2, "status") :
        return 1
    val_2 = status_index[bug_2.status]
    return cmp(status_index[bug_1.status], status_index[bug_2.status])

def cmp_attr(bug_1, bug_2, attr, invert=False):
    """
    Compare a general attribute between two bugs using the
    conventional comparison rule for that attribute type.  If
    ``invert==True``, sort *against* that convention.

    >>> attr="severity"
    >>> bugA = Bug()
    >>> bugB = Bug()
    >>> bugA.severity = "critical"
    >>> bugB.severity = "wishlist"
    >>> cmp_attr(bugA, bugB, attr) < 0
    True
    >>> cmp_attr(bugA, bugB, attr, invert=True) > 0
    True
    >>> bugB.severity = "critical"
    >>> cmp_attr(bugA, bugB, attr) == 0
    True
    """
    if not hasattr(bug_2, attr) :
        return 1
    val_1 = getattr(bug_1, attr)
    val_2 = getattr(bug_2, attr)
    if val_1 == None: val_1 = None
    if val_2 == None: val_2 = None

    if invert == True :
        return -cmp(val_1, val_2)
    else :
        return cmp(val_1, val_2)

# alphabetical rankings (a < z)
cmp_uuid = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "uuid")
cmp_creator = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "creator")
cmp_assigned = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "assigned")
cmp_reporter = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "reporter")
cmp_summary = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "summary")
cmp_extra_strings = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "extra_strings")
# chronological rankings (newer < older)
cmp_time = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "time", invert=True)

def cmp_mine(bug_1, bug_2):
    user_id = libbe.ui.util.user.get_user_id(bug_1.storage)
    mine_1 = bug_1.assigned != user_id
    mine_2 = bug_2.assigned != user_id
    return cmp(mine_1, mine_2)

def cmp_comments(bug_1, bug_2):
    """
    Compare two bugs' comments lists.  Doesn't load any new comments,
    so you should call each bug's .load_comments() first if you want a
    full comparison.
    """
    comms_1 = sorted(bug_1.comments(), key = lambda comm : comm.uuid)
    comms_2 = sorted(bug_2.comments(), key = lambda comm : comm.uuid)
    result = cmp(len(comms_1), len(comms_2))
    if result != 0:
        return result
    for c_1,c_2 in zip(comms_1, comms_2):
        result = cmp(c_1, c_2)
        if result != 0:
            return result
    return 0

DEFAULT_CMP_FULL_CMP_LIST = \
    (cmp_status, cmp_severity, cmp_assigned, cmp_time, cmp_creator,
     cmp_reporter, cmp_comments, cmp_summary, cmp_uuid, cmp_extra_strings)

class BugCompoundComparator (object):
    def __init__(self, cmp_list=DEFAULT_CMP_FULL_CMP_LIST):
        self.cmp_list = cmp_list
    def __call__(self, bug_1, bug_2):
        for comparison in self.cmp_list :
            val = comparison(bug_1, bug_2)
            if val != 0 :
                return val
        return 0

cmp_full = BugCompoundComparator()


# define some bonus cmp_* functions
def cmp_last_modified(bug_1, bug_2):
    """
    Like cmp_time(), but use most recent comment instead of bug
    creation for the timestamp.
    """
    def last_modified(bug):
        time = bug.time
        for comment in bug.comment_root.traverse():
            if comment.time > time:
                time = comment.time
        return time
    val_1 = last_modified(bug_1)
    val_2 = last_modified(bug_2)
    return -cmp(val_1, val_2)


if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
