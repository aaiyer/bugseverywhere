import os
import os.path
import cmdutil
import errno
import names
import rcs
import mapfile

class NoBugDir(Exception):
    def __init__(self, path):
        msg = "The directory \"%s\" has no bug directory." % path
        Exception.__init__(self, msg)
        self.path = path
    

def tree_root(dir):
    rootdir = os.path.realpath(dir)
    while (True):
        versionfile=os.path.join(rootdir, ".be/version")
        if os.path.exists(versionfile):
            test_version(versionfile)
            break;
        elif rootdir == "/":
            raise NoBugDir(dir)
        rootdir=os.path.dirname(rootdir)
    return BugDir(os.path.join(rootdir, ".be"))

def test_version(path):
    assert (file(path, "rb").read() == "Bugs Everywhere Tree 0 0\n")

def create_bug_dir(path):
    root = os.path.join(path, ".be")
    rcs.mkdir(root)
    rcs.mkdir(os.path.join(root, "bugs"))
    rcs.set_file_contents(os.path.join(root, "version"), 
        "Bugs Everywhere Tree 0 0\n")

    return BugDir(path)

class BugDir:
    def __init__(self, dir):
        self.dir = dir
        self.bugs_path = os.path.join(self.dir, "bugs")


    def list(self):
        for uuid in os.listdir(self.bugs_path):
            if (uuid.startswith('.')):
                continue
            yield Bug(self.bugs_path, uuid)

    def new_bug(self):
        uuid = names.uuid()
        path = os.path.join(self.bugs_path, uuid)
        rcs.mkdir(path)
        return Bug(self.bugs_path, uuid)
class InvalidValue(Exception):
    def __init__(self, name, value):
        msg = "Cannot assign value %s to %s" % (value, name)
        Exception.__init__(self, msg)
        self.name = name
        self.value = value

def file_property(name, valid=None):
    def getter(self):
        value = self._get_value(name) 
        if valid is not None:
            if value not in valid:
                raise InvalidValue(name, value)
        return value
    def setter(self, value):
        if valid is not None:
            if value not in valid:
                raise InvalidValue(name, value)
        return self._set_value(name, value)
    return property(getter, setter)

class Bug(object):
    def __init__(self, path, uuid):
        self.path = os.path.join(path, uuid)
        self.uuid = uuid

    def get_path(self, file):
        return os.path.join(self.path, file)

    summary = file_property("summary")
    creator = file_property("creator")
    target = file_property("target")
    status = file_property("status", valid=("open", "closed"))
    severity = file_property("severity", valid=("wishlist", "minor", "serious",
                                                "critical", "fatal"))

    def _get_active(self):
        return self.status == "open"

    active = property(_get_active)

    def _get_value(self, name):
        try:
            return file(self.get_path(name), "rb").read().rstrip("\n")
        except IOError, e:
            if e.errno == errno.EEXIST:
                return None

    def _set_value(self, name, value):
        if value is None:
            rcs.unlink(self.get_path(name))
        rcs.set_file_contents(self.get_path(name), "%s\n" % value)

    def add_attr(self, map, name):
        value = self.__getattribute__(name)
        if value is not None:
            map[name] = value

    def save(self):
        map = {}
        self.add_attr(map, "summary")
        self.add_attr(map, "creator")
        self.add_attr(map, "target")
        self.add_attr(map, "status")
        self.add_attr(map, "severity")
        path = self.get_path("values")
        output = file(path, "wb")
        if not os.path.exists(path):
            rcs.add_id(path)
        mapfile.generate(output, map)

