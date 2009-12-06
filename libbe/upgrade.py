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

import libbe
import bug
import encoding
import mapfile
import vcs
if libbe.TESTING == True:
    import doctest

# a list of all past versions
BUGDIR_DISK_VERSIONS = ["Bugs Everywhere Tree 1 0",
                        "Bugs Everywhere Directory v1.1",
                        "Bugs Everywhere Directory v1.2",
                        "Bugs Everywhere Directory v1.3"]

# the current version
BUGDIR_DISK_VERSION = BUGDIR_DISK_VERSIONS[-1]

class Upgrader (object):
    "Class for converting "
    initial_version = None
    final_version = None
    def __init__(self, root):
        self.root = root
        # use the "None" VCS to ensure proper encoding/decoding and
        # simplify path construction.
        self.vcs = vcs.vcs_by_name("None")
        self.vcs.root(self.root)
        self.vcs.encoding = encoding.get_encoding()

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
        version = self.vcs.get_file_contents(path).rstrip("\n")
        assert version == self.initial_version, version

    def set_version(self):
        path = self.get_path("version")
        self.vcs.set_file_contents(path, self.final_version+"\n")

    def upgrade(self):
        print >> sys.stderr, "upgrading bugdir from '%s' to '%s'" \
            % (self.initial_version, self.final_version)
        self.check_initial_version()
        self.set_version()
        self._upgrade()

    def _upgrade(self):
        raise NotImplementedError


class Upgrade_1_0_to_1_1 (Upgrader):
    initial_version = "Bugs Everywhere Tree 1 0"
    final_version = "Bugs Everywhere Directory v1.1"
    def _upgrade_mapfile(self, path):
        contents = self.vcs.get_file_contents(path)
        old_format = False
        for line in contents.splitlines():
            if len(line.split("=")) == 2:
                old_format = True
                break
        if old_format == True:
            # translate to YAML.
            newlines = []
            for line in contents.splitlines():
                line = line.rstrip('\n')
                if len(line) == 0:
                    continue
                fields = line.split("=")
                if len(fields) == 2:
                    key,value = fields
                    newlines.append('%s: "%s"' % (key, value.replace('"','\\"')))
                else:
                    newlines.append(line)
            contents = '\n'.join(newlines)
            # load the YAML and save
            map = mapfile.parse(contents)
            mapfile.map_save(self.vcs, path, map)

    def _upgrade(self):
        """
        Comment value field "From" -> "Author".
        Homegrown mapfile -> YAML.
        """
        path = self.get_path("settings")
        self._upgrade_mapfile(path)
        for bug_uuid in os.listdir(self.get_path("bugs")):
            path = self.get_path("bugs", bug_uuid, "values")
            self._upgrade_mapfile(path)
            c_path = ["bugs", bug_uuid, "comments"]
            if not os.path.exists(self.get_path(*c_path)):
                continue # no comments for this bug
            for comment_uuid in os.listdir(self.get_path(*c_path)):
                path_list = c_path + [comment_uuid, "values"]
                path = self.get_path(*path_list)
                self._upgrade_mapfile(path)
                settings = mapfile.map_load(self.vcs, path)
                if "From" in settings:
                    settings["Author"] = settings.pop("From")
                    mapfile.map_save(self.vcs, path, settings)


class Upgrade_1_1_to_1_2 (Upgrader):
    initial_version = "Bugs Everywhere Directory v1.1"
    final_version = "Bugs Everywhere Directory v1.2"
    def _upgrade(self):
        """
        BugDir settings field "rcs_name" -> "vcs_name".
        """
        path = self.get_path("settings")
        settings = mapfile.map_load(self.vcs, path)
        if "rcs_name" in settings:
            settings["vcs_name"] = settings.pop("rcs_name")
            mapfile.map_save(self.vcs, path, settings)

class Upgrade_1_2_to_1_3 (Upgrader):
    initial_version = "Bugs Everywhere Directory v1.2"
    final_version = "Bugs Everywhere Directory v1.3"
    def __init__(self, *args, **kwargs):
        Upgrader.__init__(self, *args, **kwargs)
        self._targets = {} # key: target text,value: new target bug
        path = self.get_path('settings')
        settings = mapfile.map_load(self.vcs, path)
        if 'vcs_name' in settings:
            old_vcs = self.vcs
            self.vcs = vcs.vcs_by_name(settings['vcs_name'])
            self.vcs.root(self.root)
            self.vcs.encoding = old_vcs.encoding

    def _target_bug(self, target_text):
        if target_text not in self._targets:
            _bug = bug.Bug(bugdir=self, summary=target_text)
            # note: we're not a bugdir, but all Bug.save() needs is
            # .root, .vcs, and .get_path(), which we have.
            _bug.severity = 'target'
            self._targets[target_text] = _bug
        return self._targets[target_text]

    def _upgrade_bugdir_mapfile(self):
        path = self.get_path('settings')
        settings = mapfile.map_load(self.vcs, path)
        if 'target' in settings:
            settings['target'] = self._target_bug(settings['target']).uuid
            mapfile.map_save(self.vcs, path, settings)

    def _upgrade_bug_mapfile(self, bug_uuid):
        import becommands.depend
        path = self.get_path('bugs', bug_uuid, 'values')
        settings = mapfile.map_load(self.vcs, path)
        if 'target' in settings:
            target_bug = self._target_bug(settings['target'])
            _bug = bug.Bug(bugdir=self, uuid=bug_uuid, from_disk=True)
            # note: we're not a bugdir, but all Bug.load_settings()
            # needs is .root, .vcs, and .get_path(), which we have.
            becommands.depend.add_block(target_bug, _bug)
            _bug.settings.pop('target')
            _bug.save()

    def _upgrade(self):
        """
        Bug value field "target" -> target bugs.
        Bugdir value field "target" -> pointer to current target bug.
        """
        for bug_uuid in os.listdir(self.get_path('bugs')):
            self._upgrade_bug_mapfile(bug_uuid)
        self._upgrade_bugdir_mapfile()
        for _bug in self._targets.values():
            _bug.save()

upgraders = [Upgrade_1_0_to_1_1,
             Upgrade_1_1_to_1_2,
             Upgrade_1_2_to_1_3]
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

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
