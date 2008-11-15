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
import os
import os.path
import errno
import names
import mapfile
import time
import utility
from rcs import rcs_by_name


### Define and describe valid bug categories
# Use a tuple of (category, description) tuples since we don't have
# ordered dicts in Python yet http://www.python.org/dev/peps/pep-0372/

# in order of increasing severity
severity_level_def = (
  ("wishlist","A feature that could improve usefullness, but not a bug."),
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
  ("wontfix","It's not a bug, it's a feature."),
  ("disabled", "?"))


### Convert the description tuples to more useful formats

severity_values = tuple([val for val,description in severity_level_def])
severity_description = dict(severity_level_def)
severity_index = {}
for i in range(len(severity_values)):
    severity_index[severity_values[i]] = i

active_status_values = tuple(val for val,description in active_status_def)
inactive_status_values = tuple(val for val,description in inactive_status_def)
status_values = active_status_values + inactive_status_values
status_description = dict(active_status_def+inactive_status_def)
status_index = {}
for i in range(len(status_values)):
    status_index[status_values[i]] = i


def checked_property(name, valid):
    """
    Provide access to an attribute name, testing for valid values.
    """
    def getter(self):
        value = getattr(self, "_"+name)
        if value not in valid:
            raise InvalidValue(name, value)
        return value

    def setter(self, value):
        if value not in valid:
            raise InvalidValue(name, value)
        return setattr(self, "_"+name, value)
    return property(getter, setter)


class Bug(object):
    severity = checked_property("severity", severity_values)
    status = checked_property("status", status_values)

    def __init__(self, path, uuid, rcs_name, bugdir):
        self.path = path
        self.uuid = uuid
        if uuid is not None:
            dict = mapfile.map_load(self.get_path("values"))
        else:
            dict = {}

        self.rcs_name = rcs_name
        self.bugdir = bugdir
        
        self.summary = dict.get("summary")
        self.creator = dict.get("creator")
        self.target = dict.get("target")
        self.status = dict.get("status", "open")
        self.severity = dict.get("severity", "minor")
        self.assigned = dict.get("assigned")
        self.time = dict.get("time")
        if self.time is not None:
            self.time = utility.str_to_time(self.time)

    def __repr__(self):
        return "Bug(uuid=%r)" % self.uuid

    def string(self, bugs=None, shortlist=False):
        if shortlist == False:
            if bugs == None:
                bugs = list(self.bugdir.list())
            htime = utility.handy_time(bug.time)
            ftime = utility.time_to_str(bug.time)
            info = [("ID", bug.uuid),
                    ("Short name", unique_name(bug, bugs)),
                    ("Severity", bug.severity),
                    ("Status", bug.status),
                    ("Assigned", bug.assigned),
                    ("Target", bug.target),
                    ("Creator", bug.creator),
                    ("Created", "%s (%s)" % (htime, ftime))]
            newinfo = []
            for k,v in info:
                if v == None:
                    newinfo.append((k,""))
                else:
                    newinfo.append((k,v))
            info = newinfo
            longest_key_len = max([len(k) for k,v in info])
            infolines = ["  %*s : %s\n" % (longest_key_len,k,v) for k,v in info]
            return "".join(infolines) + "%s\n" % bug.summary
        else:
            statuschar = bug.status[0]
            severitychar = bug.severity[0]
            chars = "%c%c" % (statuschar, severitychar)
            return "%s:%s: %s\n" % (cmdutil.unique_name(bug, bugs), chars, bug.summary)        
    def __str__(self):
        return self.string(shortlist=True)
    def get_path(self, file):
        return os.path.join(self.path, self.uuid, file)

    def _get_active(self):
        return self.status in active_status_values

    active = property(_get_active)

    def add_attr(self, map, name):
        value = getattr(self, name)
        if value is not None:
            map[name] = value

    def save(self):
        map = {}
        self.add_attr(map, "assigned")
        self.add_attr(map, "summary")
        self.add_attr(map, "creator")
        self.add_attr(map, "target")
        self.add_attr(map, "status")
        self.add_attr(map, "severity")
        if self.time is not None:
            map["time"] = utility.time_to_str(self.time)
        path = self.get_path("values")
        mapfile.map_save(rcs_by_name(self.rcs_name), path, map)

    def _get_rcs(self):
        return rcs_by_name(self.rcs_name)

    rcs = property(_get_rcs)

    def new_comment(self):
        if not os.path.exists(self.get_path("comments")):
            self.rcs.mkdir(self.get_path("comments"))
        comm = Comment(None, self)
        comm.uuid = names.uuid()
        return comm

    def get_comment(self, uuid):
        return Comment(uuid, self)

    def iter_comment_ids(self):
        path = self.get_path("comments")
        if not os.path.isdir(path):
            return
        try:
            for uuid in os.listdir(path):
                if (uuid.startswith('.')):
                    continue
                yield uuid
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            return

    def list_comments(self):
        comments = [Comment(id, self) for id in self.iter_comment_ids()]
        comments.sort(cmp_time)
        return comments

def new_bug(dir, uuid=None):
    bug = dir.new_bug(uuid)
    bug.creator = names.creator()
    bug.severity = "minor"
    bug.status = "open"
    bug.time = time.time()
    return bug

def new_comment(bug, body=None):
    comm = bug.new_comment()
    comm.From = names.creator()
    comm.time = time.time()
    comm.body = body
    return comm

def add_headers(obj, map, names):
    map_names = {}
    for name in names:
        map_names[name] = pyname_to_header(name)
    add_attrs(obj, map, names, map_names)

def add_attrs(obj, map, names, map_names=None):
    if map_names is None:
        map_names = {}
        for name in names:
            map_names[name] = name 
        
    for name in names:
        value = getattr(obj, name)
        if value is not None:
            map[map_names[name]] = value


class Comment(object):
    def __init__(self, uuid, bug):
        object.__init__(self)
        self.uuid = uuid 
        self.bug = bug
        if self.uuid is not None and self.bug is not None:
            map = mapfile.map_load(self.get_path("values"))
            self.time = utility.str_to_time(map["Date"])
            self.From = map["From"]
            self.in_reply_to = map.get("In-reply-to")
            self.content_type = map.get("Content-type", "text/plain")
            self.body = file(self.get_path("body")).read().decode("utf-8")
        else:
            self.time = None
            self.From = None
            self.in_reply_to = None
            self.content_type = "text/plain"
            self.body = None

    def save(self):
        map_file = {"Date": utility.time_to_str(self.time)}
        add_headers(self, map_file, ("From", "in_reply_to", "content_type"))
        if not os.path.exists(self.get_path(None)):
            self.bug.rcs.mkdir(self.get_path(None))
        mapfile.map_save(self.bug.rcs, self.get_path("values"), map_file)
        self.bug.rcs.set_file_contents(self.get_path("body"), 
                                       self.body.encode('utf-8'))
            

    def get_path(self, name):
        my_dir = os.path.join(self.bug.get_path("comments"), self.uuid)
        if name is None:
            return my_dir
        return os.path.join(my_dir, name)


def thread_comments(comments):
    child_map = {}
    top_comments = []
    for comment in comments:
        child_map[comment.uuid] = []
    for comment in comments:
        if comment.in_reply_to is None or comment.in_reply_to not in child_map:
            top_comments.append(comment)
            continue
        child_map[comment.in_reply_to].append(comment)

    def recurse_children(comment):
        child_list = []
        for child in child_map[comment.uuid]:
            child_list.append(recurse_children(child))
        return (comment, child_list)
    return [recurse_children(c) for c in top_comments]

def pyname_to_header(name):
    return name.capitalize().replace('_', '-')



class MockBug:
    def __init__(self, attr, value):
        setattr(self, attr, value)

# the general rule for bug sorting is that "more important" bugs are
# less than "less important" bugs.  This way sorting a list of bugs
# will put the most important bugs first in the list.  When relative
# importance is unclear, the sorting follows some arbitrary convention
# (i.e. dictionary order).

def cmp_severity(bug_1, bug_2):
    """
    Compare the severity levels of two bugs, with more severe bugs comparing
    as less.

    >>> attr="severity"
    >>> cmp_severity(MockBug(attr,"wishlist"), MockBug(attr,"wishlist")) == 0
    True
    >>> cmp_severity(MockBug(attr,"wishlist"), MockBug(attr,"minor")) > 0
    True
    >>> cmp_severity(MockBug(attr,"critical"), MockBug(attr,"wishlist")) < 0
    True
    """
    return -cmp(severity_index[bug_1.severity], severity_index[bug_2.severity])

def cmp_status(bug_1, bug_2):
    """
    Compare the status levels of two bugs, with more 'open' bugs
    comparing as less.

    >>> attr="status"
    >>> cmp_status(MockBug(attr,"open"), MockBug(attr,"open")) == 0
    True
    >>> cmp_status(MockBug(attr,"open"), MockBug(attr,"closed")) < 0
    True
    >>> cmp_status(MockBug(attr,"closed"), MockBug(attr,"open")) > 0
    True
    """
    val_2 = status_index[bug_2.status]
    return cmp(status_index[bug_1.status], status_index[bug_2.status])

def cmp_attr(bug_1, bug_2, attr, invert=False):
    """
    Compare a general attribute between two bugs using the conventional
    comparison rule for that attribute type.  If invert == True, sort
    *against* that convention.
    >>> attr="severity"
    >>> cmp_attr(MockBug(attr,1), MockBug(attr,2), attr, invert=False) < 0
    True
    >>> cmp_attr(MockBug(attr,1), MockBug(attr,2), attr, invert=True) > 0
    True
    >>> cmp_attr(MockBug(attr,1), MockBug(attr,1), attr) == 0
    True
    """
    if invert == True :
        return -cmp(getattr(bug_1, attr), getattr(bug_2, attr))
    else :
        return cmp(getattr(bug_1, attr), getattr(bug_2, attr))

# alphabetical rankings (a < z)
cmp_creator = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "creator")
cmp_assigned = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "assigned")
# chronological rankings (newer < older)
cmp_time = lambda bug_1, bug_2 : cmp_attr(bug_1, bug_2, "time", invert=True)

def cmp_full(bug_1, bug_2, cmp_list=(cmp_status,cmp_severity,cmp_assigned,
                                     cmp_time,cmp_creator)):
    for comparison in cmp_list :
        val = comparison(bug_1, bug_2)
        if val != 0 :
            return val
    return 0

class InvalidValue(ValueError):
    def __init__(self, name, value):
        msg = "Cannot assign value %s to %s" % (value, name)
        Exception.__init__(self, msg)
        self.name = name
        self.value = value
