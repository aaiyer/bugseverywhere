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
import time
import doctest

from beuuid import uuid_gen
import mapfile
import comment
import utility


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

    def _get_active(self):
        return self.status in active_status_values

    active = property(_get_active)

    def __init__(self, bugdir=None, uuid=None, loadNow=False, summary=None):
        self.bugdir = bugdir
        if bugdir != None:
            self.rcs = bugdir.rcs
        else:
            self.rcs = None
        if loadNow == True:
            self.uuid = uuid
            self.load()
        else:
            # Note: defaults should match those in Bug.load()
            if uuid != None:
                self.uuid = uuid
            else:
                self.uuid = uuid_gen()
            self.summary = summary
            if self.rcs != None:
                self.creator = self.rcs.get_user_id()
            else:
                self.creator = None
            self.target = None
            self.status = "open"
            self.severity = "minor"
            self.assigned = None
            self.time = time.time()
            self.comment_root = comment.Comment(self, uuid=comment.INVALID_UUID)

    def __repr__(self):
        return "Bug(uuid=%r)" % self.uuid

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
                ftime = utility.time_to_str(self.time)
                timestring = "%s (%s)" % (htime, ftime)
            info = [("ID", self.uuid),
                    ("Short name", shortname),
                    ("Severity", self.severity),
                    ("Status", self.status),
                    ("Assigned", self.assigned),
                    ("Target", self.target),
                    ("Creator", self.creator),
                    ("Created", timestring)]
            newinfo = []
            for k,v in info:
                if v == None:
                    newinfo.append((k,""))
                else:
                    newinfo.append((k,v))
            info = newinfo
            longest_key_len = max([len(k) for k,v in info])
            infolines = ["  %*s : %s\n" %(longest_key_len,k,v) for k,v in info]
            bugout = "".join(infolines) + "%s" % self.summary.rstrip('\n')
        else:
            statuschar = self.status[0]
            severitychar = self.severity[0]
            chars = "%c%c" % (statuschar, severitychar)
            bugout = "%s:%s: %s" % (shortname, chars, self.summary.rstrip('\n'))
        
        if show_comments == True:
            comout = self.comment_root.string_thread(auto_name_map=True,
                                                     bug_shortname=shortname)
            output = bugout + '\n' + comout.rstrip('\n')
        else :
            output = bugout
        return output

    def __str__(self):
        return self.string(shortlist=True)

    def __cmp__(self, other):
        return cmp_full(self, other)

    def get_path(self, name=None):
        my_dir = os.path.join(self.bugdir.get_path("bugs"), self.uuid)
        if name is None:
            return my_dir
        assert name in ["values", "comments"]
        return os.path.join(my_dir, name)

    def load(self):
        map = mapfile.map_load(self.get_path("values"))
        self.summary = map.get("summary")
        self.creator = map.get("creator")
        self.target = map.get("target")
        self.status = map.get("status", "open")
        self.severity = map.get("severity", "minor")
        self.assigned = map.get("assigned")
        self.time = map.get("time")
        if self.time is not None:
            self.time = utility.str_to_time(self.time)
        
        self.comment_root = comment.loadComments(self)

    def _add_attr(self, map, name):
        value = getattr(self, name)
        if value is not None:
            map[name] = value

    def save(self):
        assert self.summary != None, "Can't save blank bug"
        map = {}
        self._add_attr(map, "assigned")
        self._add_attr(map, "summary")
        self._add_attr(map, "creator")
        self._add_attr(map, "target")
        self._add_attr(map, "status")
        self._add_attr(map, "severity")
        if self.time is not None:
            map["time"] = utility.time_to_str(self.time)

        self.rcs.mkdir(self.get_path())
        path = self.get_path("values")
        mapfile.map_save(self.rcs, path, map)

        if len(self.comment_root) > 0:
            self.rcs.mkdir(self.get_path("comments"))
            comment.saveComments(self)

    def remove(self):
        self.comment_root.remove()
        path = self.get_path()
        self.rcs.recursive_remove(path)
    
    def new_comment(self, body=None):
        comm = comment.comment_root.new_reply(body=body)
        return comm

    def comment_from_shortname(self, shortname, *args, **kwargs):
        return self.comment_root.comment_from_shortname(shortname, *args, **kwargs)

    def comment_from_uuid(self, uuid):
        return self.comment_root.comment_from_uuid(uuid)


# the general rule for bug sorting is that "more important" bugs are
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

suite = doctest.DocTestSuite()
