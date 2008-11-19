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
import unittest
import doctest
import names
import mapfile
import time
import utility
from rcs import rcs_by_name, installed_rcs
from bug import Bug

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

def bugdir_root(versioning_root):
    return os.path.join(versioning_root, ".be")

def create_bug_dir(path, rcs):
    """
    >>> import tests
    >>> rcs = rcs_by_name("None")
    >>> create_bug_dir('/highly-unlikely-to-exist', rcs)
    Traceback (most recent call last):
    NoRootEntry: Specified root does not exist: /highly-unlikely-to-exist
    """
    root = os.path.join(path, ".be")
    try:
        rcs.mkdir(root)
    except OSError, e:
        if e.errno == errno.ENOENT:
            raise NoRootEntry(path)
        elif e.errno == errno.EEXIST:
            raise AlreadyInitialized(path)
        else:
            raise
    rcs.mkdir(os.path.join(root, "bugs"))
    set_version(root, rcs)
    mapfile.map_save(rcs,
                     os.path.join(root, "settings"), {"rcs_name": rcs.name})
    return BugDir(bugdir_root(path))


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
            self.settings = mapfile.map_load(os.path.join(self.dir,"settings"))
        except mapfile.NoSuchFile:
            self.settings = {"rcs_name": "None"}

    rcs_name = setting_property("rcs_name",
                                ("None", "bzr", "git", "Arch", "hg"))
    _rcs = None

    target = setting_property("target")
    
    def save_settings(self):
        mapfile.map_save(self.rcs,
                         os.path.join(self.dir, "settings"), self.settings)

    def _get_rcs(self):
        if self._rcs is not None:
            if self.rcs_name == self._rcs.name:
                return self._rcs
        self._rcs = rcs_by_name(self.rcs_name)
        self._rcs.root(self.dir)
        return self._rcs

    rcs = property(_get_rcs)

    def duplicate_bugdir(self, revision):
        return BugDir(bugdir_root(self.rcs.duplicate_repo(revision)))

    def remove_duplicate_bugdir(self):
        self.rcs.remove_duplicate_repo()

    def list(self):
        for uuid in self.list_uuids():
            yield self.get_bug(uuid)

    def bug_map(self):
        bugs = {}
        for bug in self.list():
            bugs[bug.uuid] = bug
        return bugs

    def get_bug(self, uuid):
        return Bug(self.bugs_path, uuid, self.rcs, self)

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
        bug = Bug(self.bugs_path, None, self.rcs, self)
        bug.uuid = uuid
        return bug

class InvalidValue(ValueError):
    def __init__(self, name, value):
        msg = "Cannot assign value %s to %s" % (value, name)
        Exception.__init__(self, msg)
        self.name = name
        self.value = value

def simple_bug_dir():
    """
    For testing
    >>> bugdir = simple_bug_dir()
    >>> ls = list(bugdir.list_uuids())
    >>> ls.sort()
    >>> print ls
    ['a', 'b']
    """
    dir = utility.Dir()
    rcs = installed_rcs()
    rcs.init(dir.path)
    assert os.path.exists(dir.path)
    bugdir = create_bug_dir(dir.path, rcs)
    bugdir._dir_ref = dir # postpone cleanup since dir.__del__() removes dir.
    bug_a = bugdir.new_bug("a")
    bug_a.summary = "Bug A"
    bug_a.save()
    bug_b = bugdir.new_bug("b")
    bug_b.status = "closed"
    bug_b.summary = "Bug B"
    bug_b.save()
    return bugdir


class BugDirTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
    def setUp(self):
        self.dir = utility.Dir()
        self.rcs = installed_rcs()
        self.rcs.init(self.dir.path)
        self.bugdir = create_bug_dir(self.dir.path, self.rcs)
    def tearDown(self):
        del(self.rcs)
        del(self.dir)
    def fullPath(self, path):
        return os.path.join(self.dir.path, path)
    def assertPathExists(self, path):
        fullpath = self.fullPath(path)
        self.failUnless(os.path.exists(fullpath)==True,
                        "path %s does not exist" % fullpath)
    def testBugDirDuplicate(self):
        self.assertRaises(AlreadyInitialized, create_bug_dir,
                          self.dir.path, self.rcs)

unitsuite = unittest.TestLoader().loadTestsFromTestCase(BugDirTestCase)
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
