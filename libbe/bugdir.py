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
    

def tree_root(dir, old_version=False):
    rootdir = os.path.realpath(dir)
    while (True):
        versionfile=os.path.join(rootdir, ".be/version")
        if os.path.exists(versionfile):
            if not old_version:
                test_version(versionfile)
            break;
        elif rootdir == "/":
            raise NoBugDir(dir)
        rootdir=os.path.dirname(rootdir)
    return BugDir(os.path.join(rootdir, ".be"))

class BadTreeVersion(Exception):
    def __init__(self, version):
        Exception.__init__(self, "Unsupported tree version: %s" % version)
        self.version = version

def test_version(path):
    tree_version = file(path, "rb").read()
    if tree_version != TREE_VERSION_STRING:
        raise BadTreeVersion(tree_version)

def set_version(path):
    rcs.set_file_contents(os.path.join(path, "version"), TREE_VERSION_STRING)
    

TREE_VERSION_STRING = "Bugs Everywhere Tree 1 0\n"

def create_bug_dir(path):
    root = os.path.join(path, ".be")
    rcs.mkdir(root)
    rcs.mkdir(os.path.join(root, "bugs"))
    set_version(root)

    return BugDir(path)

class BugDir:
    def __init__(self, dir):
        self.dir = dir
        self.bugs_path = os.path.join(self.dir, "bugs")

    def list(self):
        for uuid in self.list_uuids():
            yield Bug(self.bugs_path, uuid)

    def list_uuids(self):
        for uuid in os.listdir(self.bugs_path):
            if (uuid.startswith('.')):
                continue
            yield uuid

    def new_bug(self):
        uuid = names.uuid()
        path = os.path.join(self.bugs_path, uuid)
        rcs.mkdir(path)
        bug = Bug(self.bugs_path, None)
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


class Bug(object):
    status = checked_property("status", (None, "open", "closed"))
    severity = checked_property("severity", (None, "wishlist", "minor",
                                             "serious", "critical", "fatal"))

    def __init__(self, path, uuid):
        self.path = path
        self.uuid = uuid
        if uuid is not None:
            dict = mapfile.parse(file(self.get_path("values")))
        else:
            dict = {}

        self.summary = dict.get("summary")
        self.creator = dict.get("creator")
        self.target = dict.get("target")
        self.status = dict.get("status")
        self.severity = dict.get("severity")
        self.assigned = dict.get("assigned")

    def get_path(self, file):
        return os.path.join(self.path, self.uuid, file)

    def _get_active(self):
        return self.status == "open"

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
        path = self.get_path("values")
        if not os.path.exists(path):
            rcs.add_id(path)
        output = file(path, "wb")
        mapfile.generate(output, map)
