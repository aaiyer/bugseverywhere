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
import cmdutil
import errno
import names
import mapfile
import time
import utility
from rcs import rcs_by_name

class NoBugDir(Exception):
    def __init__(self, path):
        msg = "The directory \"%s\" has no bug directory." % path
        Exception.__init__(self, msg)
        self.path = path

 
def iter_parent_dirs(cur_dir):
    cur_dir = os.path.realpath(cur_dir)
    old_dir = None
    while True:
        yield cur_dir
        old_dir = cur_dir
        cur_dir = os.path.normpath(os.path.join(cur_dir, '..'))
        if old_dir == cur_dir:
            break;


def tree_root(dir, old_version=False):
    for rootdir in iter_parent_dirs(dir):
        versionfile=os.path.join(rootdir, ".be", "version")
        if os.path.exists(versionfile):
            if not old_version:
                test_version(versionfile)
            return BugDir(os.path.join(rootdir, ".be"))
        elif not os.path.exists(rootdir):
            raise NoRootEntry(rootdir)
        old_rootdir = rootdir
        rootdir=os.path.join('..', rootdir)
    
    raise NoBugDir(dir)

class BadTreeVersion(Exception):
    def __init__(self, version):
        Exception.__init__(self, "Unsupported tree version: %s" % version)
        self.version = version

def test_version(path):
    tree_version = file(path, "rb").read()
    if tree_version != TREE_VERSION_STRING:
        raise BadTreeVersion(tree_version)

def set_version(path, rcs):
    rcs.set_file_contents(os.path.join(path, "version"), TREE_VERSION_STRING)
    

TREE_VERSION_STRING = "Bugs Everywhere Tree 1 0\n"

class NoRootEntry(Exception):
    def __init__(self, path):
        self.path = path
        Exception.__init__(self, "Specified root does not exist: %s" % path)

class AlreadyInitialized(Exception):
    def __init__(self, path):
        self.path = path
        Exception.__init__(self, 
                           "Specified root is already initialized: %s" % path)

def create_bug_dir(path, rcs):
    """
    >>> import no_rcs, tests
    >>> create_bug_dir('/highly-unlikely-to-exist', no_rcs)
    Traceback (most recent call last):
    NoRootEntry: Specified root does not exist: /highly-unlikely-to-exist
    >>> test_dir = os.path.dirname(tests.bug_arch_dir().dir)
    >>> try:
    ...     create_bug_dir(test_dir, no_rcs)
    ... except AlreadyInitialized, e:
    ...     print "Already Initialized"
    Already Initialized
    """
    root = os.path.join(path, ".be")
    try:
        rcs.mkdir(root, paranoid=True)
    except OSError, e:
        if e.errno == errno.ENOENT:
            raise NoRootEntry(path)
        elif e.errno == errno.EEXIST:
            raise AlreadyInitialized(path)
        else:
            raise
    rcs.mkdir(os.path.join(root, "bugs"))
    set_version(root, rcs)
    map_save(rcs, os.path.join(root, "settings"), {"rcs_name": rcs.name})
    return BugDir(os.path.join(path, ".be"))


def setting_property(name, valid=None):
    def getter(self):
        value = self.settings.get(name) 
        if valid is not None:
            if value not in valid:
                raise InvalidValue(name, value)
        return value

    def setter(self, value):
        if valid is not None:
            if value not in valid and value is not None:
                raise InvalidValue(name, value)
        if value is None:
            del self.settings[name]
        else:
            self.settings[name] = value
        self.save_settings()
    return property(getter, setter)


class BugDir:
    def __init__(self, dir):
        self.dir = dir
        self.bugs_path = os.path.join(self.dir, "bugs")
        try:
            self.settings = map_load(os.path.join(self.dir, "settings"))
        except NoSuchFile:
            self.settings = {"rcs_name": "None"}

    rcs_name = setting_property("rcs_name", ("None", "bzr", "Arch"))
    _rcs = None

    target = setting_property("target")

    def save_settings(self):
        map_save(self.rcs, os.path.join(self.dir, "settings"), self.settings)

    def get_rcs(self):
        if self._rcs is not None and self.rcs_name == self._rcs.name:
            return self._rcs
        self._rcs = rcs_by_name(self.rcs_name)
        return self._rcs

    rcs = property(get_rcs)

    def get_reference_bugdir(self, spec):
        return BugDir(self.rcs.path_in_reference(self.dir, spec))

    def list(self):
        for uuid in self.list_uuids():
            yield self.get_bug(uuid)

    def bug_map(self):
        bugs = {}
        for bug in self.list():
            bugs[bug.uuid] = bug
        return bugs

    def get_bug(self, uuid):
        return Bug(self.bugs_path, uuid, self.rcs_name)

    def list_uuids(self):
        for uuid in os.listdir(self.bugs_path):
            if (uuid.startswith('.')):
                continue
            yield uuid

    def new_bug(self, uuid=None):
        if uuid is None:
            uuid = names.uuid()
        path = os.path.join(self.bugs_path, uuid)
        self.rcs.mkdir(path)
        bug = Bug(self.bugs_path, None, self.rcs_name)
        bug.uuid = uuid
        return bug

class InvalidValue(Exception):
    def __init__(self, name, value):
        msg = "Cannot assign value %s to %s" % (value, name)
        Exception.__init__(self, msg)
        self.name = name
        self.value = value


def checked_property(name, valid):
    def getter(self):
        value = self.__getattribute__("_"+name)
        if value not in valid:
            raise InvalidValue(name, value)
        return value

    def setter(self, value):
        if value not in valid:
            raise InvalidValue(name, value)
        return self.__setattr__("_"+name, value)
    return property(getter, setter)

severity_levels = ("wishlist", "minor", "serious", "critical", "fatal")
active_status = ("open", "in-progress", "waiting", "new", "verified")
inactive_status = ("closed", "disabled", "fixed", "wontfix", "waiting")

severity_value = {}
for i in range(len(severity_levels)):
    severity_value[severity_levels[i]] = i

class Bug(object):
    status = checked_property("status", (None,)+active_status+inactive_status)
    severity = checked_property("severity", (None, "wishlist", "minor",
                                             "serious", "critical", "fatal"))

    def __init__(self, path, uuid, rcs_name):
        self.path = path
        self.uuid = uuid
        if uuid is not None:
            dict = map_load(self.get_path("values"))
        else:
            dict = {}

        self.rcs_name = rcs_name

        self.summary = dict.get("summary")
        self.creator = dict.get("creator")
        self.target = dict.get("target")
        self.status = dict.get("status")
        self.severity = dict.get("severity")
        self.assigned = dict.get("assigned")
        self.time = dict.get("time")
        if self.time is not None:
            self.time = utility.str_to_time(self.time)

    def get_path(self, file):
        return os.path.join(self.path, self.uuid, file)

    def _get_active(self):
        return self.status in active_status

    active = property(_get_active)

    def add_attr(self, map, name):
        value = self.__getattribute__(name)
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
        map_save(rcs_by_name(self.rcs_name), path, map)

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
        try:
            for uuid in os.listdir(self.get_path("comments")):
                if (uuid.startswith('.')):
                    continue
                yield uuid
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise
            return

    def list_comments(self):
        comments = [Comment(id, self) for id in self.iter_comment_ids()]
        comments.sort(cmp_date)
        return comments

def cmp_date(comm1, comm2):
    return cmp(comm1.date, comm2.date)

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
    comm.date = time.time()
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
        value = obj.__getattribute__(name)
        if value is not None:
            map[map_names[name]] = value


class Comment(object):
    def __init__(self, uuid, bug):
        object.__init__(self)
        self.uuid = uuid 
        self.bug = bug
        if self.uuid is not None and self.bug is not None:
            mapfile = map_load(self.get_path("values"))
            self.date = utility.str_to_time(mapfile["Date"])
            self.From = mapfile["From"]
            self.in_reply_to = mapfile.get("In-reply-to")
            self.body = file(self.get_path("body")).read()
        else:
            self.date = None
            self.From = None
            self.in_reply_to = None
            self.body = None

    def save(self):
        map_file = {"Date": utility.time_to_str(self.date)}
        add_headers(self, map_file, ("From", "in_reply_to"))
        if not os.path.exists(self.get_path(None)):
            self.bug.rcs.mkdir(self.get_path(None))
        map_save(self.bug.rcs, self.get_path("values"), map_file)
        self.bug.rcs.set_file_contents(self.get_path("body"), self.body)
            

    def get_path(self, name):
        my_dir = os.path.join(self.bug.get_path("comments"), self.uuid)
        if name is None:
            return my_dir
        return os.path.join(my_dir, name)
        
def pyname_to_header(name):
    return name.capitalize().replace('_', '-')
    
    
def map_save(rcs, path, map):
    """Save the map as a mapfile to the specified path"""
    add = not os.path.exists(path)
    output = file(path, "wb")
    mapfile.generate(output, map)
    if add:
        rcs.add_id(path)

class NoSuchFile(Exception):
    def __init__(self, pathname):
        Exception.__init__(self, "No such file: %s" % pathname)


def map_load(path):
    try:
        return mapfile.parse(file(path, "rb"))
    except IOError, e:
        if e.errno != errno.ENOENT:
            raise e
        raise NoSuchFile(path)


class MockBug:
    def __init__(self, severity):
        self.severity = severity

def cmp_severity(bug_1, bug_2):
    """
    Compare the severity levels of two bugs, with more sever bugs comparing
    as less.

    >>> cmp_severity(MockBug(None), MockBug(None))
    0
    >>> cmp_severity(MockBug("wishlist"), MockBug(None)) < 0
    True
    >>> cmp_severity(MockBug(None), MockBug("wishlist")) > 0
    True
    >>> cmp_severity(MockBug("critical"), MockBug("wishlist")) < 0
    True
    """
    val_1 = severity_value.get(bug_1.severity)
    val_2 = severity_value.get(bug_2.severity)
    return -cmp(val_1, val_2)
