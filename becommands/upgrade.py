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
"""Upgrade the bugs to the latest format"""
import os.path
import errno
from libbe import bugdir, rcs, cmdutil

def execute(args):
    options, args = get_parser().parse_args(args)
    root = bugdir.tree_root(".", old_version=True)
    for uuid in root.list_uuids():
        old_bug = OldBug(root.bugs_path, uuid)
        
        new_bug = bugdir.Bug(root.bugs_path, None)
        new_bug.uuid = old_bug.uuid
        new_bug.summary = old_bug.summary
        new_bug.creator = old_bug.creator
        new_bug.target = old_bug.target
        new_bug.status = old_bug.status
        new_bug.severity = old_bug.severity

        new_bug.save()
    for uuid in root.list_uuids():
        old_bug = OldBug(root.bugs_path, uuid)
        old_bug.delete()

    bugdir.set_version(root.dir)

def file_property(name, valid=None):
    def getter(self):
        value = self._get_value(name) 
        if valid is not None:
            if value not in valid:
                raise InvalidValue(name, value)
        return value
    def setter(self, value):
        if valid is not None:
            if value not in valid and value is not None:
                raise InvalidValue(name, value)
        return self._set_value(name, value)
    return property(getter, setter)


class OldBug(object):
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
    def delete(self):
        self.summary = None
        self.creator = None
        self.target = None
        self.status = None
        self.severity = None
        self._set_value("name", None)

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
            try:
                rcs.unlink(self.get_path(name))
            except OSError, e:
                if e.errno != 2:
                    raise
        else:
            rcs.set_file_contents(self.get_path(name), "%s\n" % value)

def get_parser():
    parser = cmdutil.CmdOptionParser("be upgrade")
    return parser

longhelp="""
Upgrade the bug storage to the latest format.
"""

def help():
    return get_parser().help_str() + longhelp
