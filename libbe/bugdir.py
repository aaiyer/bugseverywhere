import os
import os.path
import cmdutil

class NoBugDir(cmdutil.UserError):
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

class BugDir:
    def __init__(self, dir):
        self.dir = dir
        self.bugs_path = os.path.join(self.dir, "bugs")


    def list(self):
        for uuid in os.listdir(self.bugs_path):
            if (uuid.startswith('.')):
                continue
            yield Bug(self.bugs_path, uuid)

def file_property(name):
    def getter(self):
        return self._get_value(name)
    def setter(self, value):
        return self._set_value(name, value)
    return property(getter, setter)

class Bug(object):
    def __init__(self, path, uuid):
        self.path = os.path.join(path, uuid)
        self.uuid = uuid

    def get_path(self, file):
        return os.path.join(self.path, file)

    def _get_name(self):
        return self._get_value("name")
    
    def _set_name(self, value):
        return self._set_value("name", value)
    
    name = file_property("name")
    summary = file_property("summary")

    def _check_status(status):
        assert status in ("open", "closed")

    def _set_status(self, status):
        self._check_status(status)
        self._set_value("status", status)

    def _get_status(self):
        status = self._get_value("status")
        assert status in ("open", "closed")
        return status

    status = property(_get_status, _set_status)

    def _get_active(self):
        return self.status == "open"

    active = property(_get_active)

    def _get_value(self, name):
        return file(self.get_path(name), "rb").read().rstrip("\n")

    def _set_value(self, name, value):
        file(self.get_path(name), "wb").write("%s\n" % value)

