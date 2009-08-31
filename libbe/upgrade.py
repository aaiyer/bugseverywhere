# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
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
Handle conversion between the various on-disk images.
"""

import os, os.path
import sys
import doctest

import encoding
import mapfile
import rcs

# a list of all past versions
BUGDIR_DISK_VERSIONS = ["Bugs Everywhere Tree 1 0",
                        "Bugs Everywhere Directory v2"]

# the current version
BUGDIR_DISK_VERSION = BUGDIR_DISK_VERSIONS[-1]

class Upgrader (object):
    "Class for converting "
    initial_version = None
    final_version = None
    def __init__(self, root):
        self.root = root
        # use the "None" RCS to ensure proper encoding/decoding and
        # simplify path construction.
        self.rcs = rcs.rcs_by_name("None")
        self.rcs.root(self.root)
        self.rcs.encoding = encoding.get_encoding()

    def get_path(self, *args):
        """
        Return a path relative to .root.
        """
        dir = os.path.join(self.root, ".be")
        if len(args) == 0:
            return dir
        assert args[0] in ["version", "settings", "bugs"], str(args)
        return os.path.join(dir, *args)

    def check_initial_version(self):
        path = self.get_path("version")
        version = self.rcs.get_file_contents(path).rstrip("\n")
        assert version == self.initial_version, version

    def set_version(self):
        path = self.get_path("version")
        self.rcs.set_file_contents(path, self.final_version+"\n")

    def upgrade(self):
        print >> sys.stderr, "upgrading bugdir from '%s' to '%s'" \
            % (self.initial_version, self.final_version)
        self.check_initial_version()
        self.set_version()
        self._upgrade()

    def _upgrade(self):
        raise NotImplementedError

class Upgrade_1_0_to_2 (Upgrader):
    initial_version = "Bugs Everywhere Tree 1 0"
    final_version = "Bugs Everywhere Directory v2"
    def _upgrade(self):
        for bug_uuid in os.listdir(self.get_path("bugs")):
            c_path = ["bugs", bug_uuid, "comments"]
            if not os.path.exists(self.get_path(*c_path)):
                continue # no comments for this bug
            for comment_uuid in os.listdir(self.get_path(*c_path)):
                path_list = c_path + [comment_uuid, "values"]
                path = self.get_path(*path_list)
                settings = mapfile.map_load(self.rcs, path)
                if "From" in settings:
                    settings["Author"] = settings.pop("From")
                    mapfile.map_save(self.rcs, path, settings)

upgraders = [Upgrade_1_0_to_2]
upgrade_classes = {}
for upgrader in upgraders:
    upgrade_classes[(upgrader.initial_version,upgrader.final_version)]=upgrader

def upgrade(path, current_version,
            target_version=BUGDIR_DISK_VERSION):
    """
    Call the appropriate upgrade function to convert current_version
    to target_version.  If a direct conversion function does not exist,
    use consecutive conversion functions.
    """
    if current_version not in BUGDIR_DISK_VERSIONS:
        raise NotImplementedError, \
            "Cannot handle version '%s' yet." % version
    if target_version not in BUGDIR_DISK_VERSIONS:
        raise NotImplementedError, \
            "Cannot handle version '%s' yet." % version

    if (current_version, target_version) in upgrade_classes:
        # direct conversion
        upgrade_class = upgrade_classes[(current_version, target_version)]
        u = upgrade_class(path)
        u.upgrade()
    else:
        # consecutive single-step conversion
        i = BUGDIR_DISK_VERSIONS.index(current_version)
        while True:
            version_a = BUGDIR_DISK_VERSIONS[i]
            version_b = BUGDIR_DISK_VERSIONS[i+1]
            try:
                upgrade_class = upgrade_classes[(version_a, version_b)]
            except KeyError:
                raise NotImplementedError, \
                    "Cannot convert version '%s' to '%s' yet." \
                    % (version_a, version_b)
            u = upgrade_class(path)
            u.upgrade()
            if version_b == target_version:
                break
            i += 1

suite = doctest.DocTestSuite()
