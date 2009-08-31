# Copyright (C) 2008-2009 Chris Ball <cjb@laptop.org>
#                         Thomas Habets <thomas@habets.pp.se>
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

"""
Define the Bug class for representing bugs.
"""

import os
import os.path
import errno
import time
import types
import xml.sax.saxutils
import doctest

from beuuid import uuid_gen
from properties import Property, doc_property, local_property, \
    defaulting_property, checked_property, cached_property, \
    primed_property, change_hook_property, settings_property
import settings_object
import mapfile
import comment
import utility


class DiskAccessRequired (Exception):
    def __init__(self, goal):
        msg = "Cannot %s without accessing the disk" % goal
        Exception.__init__(self, msg)

### Define and describe valid bug categories
# Use a tuple of (category, description) tuples since we don't have
# ordered dicts in Python yet http://www.python.org/dev/peps/pep-0372/

# in order of increasing severity.  (name, description) pairs
severity_def = (
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


class Bug(settings_object.SavedSettingsObject):
    """
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

    @_versioned_property(name="target",
                         doc="The deadline for fixing this bug")
    def target(): return {}

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
            return None
        return utility.str_to_time(self.time_string)
    def _set_time(self, value):
        self.time_string = utility.time_to_str(value)
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
        if self.sync_with_disk:
            return comment.loadComments(self, load_full=load_full)
        else:
            return comment.Comment(self, uuid=comment.INVALID_UUID)

    @Property
    @cached_property(generator=_get_comment_root)
    @local_property("comment_root")
    @doc_property(doc="The trunk of the comment tree")
    def comment_root(): return {}

    def _get_vcs(self):
        if hasattr(self.bugdir, "vcs"):
            return self.bugdir.vcs

    @Property
    @cached_property(generator=_get_vcs)
    @local_property("vcs")
    @doc_property(doc="A revision control system instance.")
    def vcs(): return {}

    def __init__(self, bugdir=None, uuid=None, from_disk=False,
                 load_comments=False, summary=None):
        settings_object.SavedSettingsObject.__init__(self)
        self.bugdir = bugdir
        self.uuid = uuid
        if from_disk == True:
            self.sync_with_disk = True
        else:
            self.sync_with_disk = False
            if uuid == None:
                self.uuid = uuid_gen()
            self.time = int(time.time()) # only save to second precision
            if self.vcs != None:
                self.creator = self.vcs.get_user_id()
            self.summary = summary

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
        return str(value)

    def xml(self, show_comments=False):
        if self.bugdir == None:
            shortname = self.uuid
        else:
            shortname = self.bugdir.bug_shortname(self)

        if self.time == None:
            timestring = ""
        else:
            timestring = utility.time_to_str(self.time)

        info = [("uuid", self.uuid),
                ("short-name", shortname),
                ("severity", self.severity),
                ("status", self.status),
                ("assigned", self.assigned),
                ("target", self.target),
                ("reporter", self.reporter),
                ("creator", self.creator),
                ("created", timestring),
                ("summary", self.summary)]
        ret = '<bug>\n'
        for (k,v) in info:
            if v is not None:
                ret += '  <%s>%s</%s>\n' % (k,xml.sax.saxutils.escape(v),k)
        for estr in self.extra_strings:
            ret += '  <extra-string>%s</extra-string>\n' % estr
        if show_comments == True:
            comout = self.comment_root.xml_thread(auto_name_map=True,
                                                  bug_shortname=shortname)
            if len(comout) > 0:
                ret += comout+'\n'
        ret += '</bug>'
        return ret

    def string(self, shortlist=False, show_comments=False):
        if self.bugdir == None:
            shortname = self.uuid
        else:
            shortname = self.bugdir.bug_shortname(self)
        if shortlist == False:
            if self.time == None:
                timestring = ""
            else:
                htime = utility.handy_time(self.time)
                timestring = "%s (%s)" % (htime, self.time_string)
            info = [("ID", self.uuid),
                    ("Short name", shortname),
                    ("Severity", self.severity),
                    ("Status", self.status),
                    ("Assigned", self._setting_attr_string("assigned")),
                    ("Target", self._setting_attr_string("target")),
                    ("Reporter", self._setting_attr_string("reporter")),
                    ("Creator", self._setting_attr_string("creator")),
                    ("Created", timestring)]
            longest_key_len = max([len(k) for k,v in info])
            infolines = ["  %*s : %s\n" %(longest_key_len,k,v) for k,v in info]
            bugout = "".join(infolines) + "%s" % self.summary.rstrip('\n')
        else:
            statuschar = self.status[0]
            severitychar = self.severity[0]
            chars = "%c%c" % (statuschar, severitychar)
            bugout = "%s:%s: %s" % (shortname,chars,self.summary.rstrip('\n'))
        
        if show_comments == True:
            # take advantage of the string_thread(auto_name_map=True)
            # SIDE-EFFECT of sorting by comment time.
            comout = self.comment_root.string_thread(flatten=False,
                                                     auto_name_map=True,
                                                     bug_shortname=shortname)
            output = bugout + '\n' + comout.rstrip('\n')
        else :
            output = bugout
        return output

    # methods for saving/loading/acessing settings and properties.

    def get_path(self, *args):
        dir = os.path.join(self.bugdir.get_path("bugs"), self.uuid)
        if len(args) == 0:
            return dir
        assert args[0] in ["values", "comments"], str(args)
        return os.path.join(dir, *args)

    def set_sync_with_disk(self, value):
        self.sync_with_disk = value
        for comment in self.comments():
            comment.set_sync_with_disk(value)

    def load_settings(self):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("load settings")
        self.settings = mapfile.map_load(self.vcs, self.get_path("values"))
        self._setup_saved_settings()

    def save_settings(self):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("save settings")
        assert self.summary != None, "Can't save blank bug"
        self.vcs.mkdir(self.get_path())
        path = self.get_path("values")
        mapfile.map_save(self.vcs, path, self._get_saved_settings())

    def save(self):
        """
        Save any loaded contents to disk.  Because of lazy loading of
        comments, this is actually not too inefficient.
        
        However, if self.sync_with_disk = True, then any changes are
        automatically written to disk as soon as they happen, so
        calling this method will just waste time (unless something
        else has been messing with your on-disk files).
        """
        sync_with_disk = self.sync_with_disk
        if sync_with_disk == False:
            self.set_sync_with_disk(True)
        self.save_settings()
        if len(self.comment_root) > 0:
            comment.saveComments(self)
        if sync_with_disk == False:
            self.set_sync_with_disk(False)

    def load_comments(self, load_full=True):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("load comments")
        if load_full == True:
            # Force a complete load of the whole comment tree
            self.comment_root = self._get_comment_root(load_full=True)
        else:
            # Setup for fresh lazy-loading.  Clear _comment_root, so
            # _get_comment_root returns a fresh version.  Turn of
            # syncing temporarily so we don't write our blank comment
            # tree to disk.
            self.sync_with_disk = False
            self.comment_root = None
            self.sync_with_disk = True

    def remove(self):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("remove")
        self.comment_root.remove()
        path = self.get_path()
        self.vcs.recursive_remove(path)
    
    # methods for managing comments

    def comments(self):
        for comment in self.comment_root.traverse():
            yield comment

    def new_comment(self, body=None):
        comm = self.comment_root.new_reply(body=body)
        return comm

    def comment_from_shortname(self, shortname, *args, **kwargs):
        return self.comment_root.comment_from_shortname(shortname,
                                                        *args, **kwargs)

    def comment_from_uuid(self, uuid):
        return self.comment_root.comment_from_uuid(uuid)

    def comment_shortnames(self, shortname=None):
        """
        SIDE-EFFECT : Comment.comment_shortnames will sort the comment
        tree by comment.time
        """
        for id, comment in self.comment_root.comment_shortnames(shortname):
            yield (id, comment)


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
    Compare the status levels of two bugs, with more 'open' bugs
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
    Compare a general attribute between two bugs using the conventional
    comparison rule for that attribute type.  If invert == True, sort
    *against* that convention.
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
cmp_target = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "target")
cmp_reporter = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "reporter")
cmp_summary = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "summary")
# chronological rankings (newer < older)
cmp_time = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "time", invert=True)

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
     cmp_reporter, cmp_target, cmp_comments, cmp_summary, cmp_uuid)

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


suite = doctest.DocTestSuite()
