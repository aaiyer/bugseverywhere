# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""
Handle conversion between the various BE storage formats.
"""

import codecs
import os, os.path
import sys

import libbe
import libbe.bug
import libbe.storage.util.mapfile as mapfile
from libbe.storage import STORAGE_VERSIONS, STORAGE_VERSION
#import libbe.storage.vcs # delay import to avoid cyclic dependency
import libbe.ui.util.editor
import libbe.util
import libbe.util.encoding as encoding
import libbe.util.id


class Upgrader (object):
    "Class for converting between different on-disk BE storage formats."
    initial_version = None
    final_version = None
    def __init__(self, repo):
        import libbe.storage.vcs

        self.repo = repo
        vcs_name = self._get_vcs_name()
        if vcs_name == None:
            vcs_name = 'None'
        self.vcs = libbe.storage.vcs.vcs_by_name(vcs_name)
        self.vcs.repo = self.repo
        self.vcs.root()

    def get_path(self, *args):
        """
        Return the absolute path using args relative to .be.
        """
        dir = os.path.join(self.repo, '.be')
        if len(args) == 0:
            return dir
        return os.path.join(dir, *args)

    def _get_vcs_name(self):
        return None

    def check_initial_version(self):
        path = self.get_path('version')
        version = encoding.get_file_contents(path, decode=True).rstrip('\n')
        assert version == self.initial_version, '%s: %s' % (path, version)

    def set_version(self):
        path = self.get_path('version')
        encoding.set_file_contents(path, self.final_version+'\n')
        self.vcs._vcs_update(path)

    def upgrade(self):
        print >> sys.stderr, 'upgrading bugdir from "%s" to "%s"' \
            % (self.initial_version, self.final_version)
        self.check_initial_version()
        self.set_version()
        self._upgrade()

    def _upgrade(self):
        raise NotImplementedError


class Upgrade_1_0_to_1_1 (Upgrader):
    initial_version = "Bugs Everywhere Tree 1 0"
    final_version = "Bugs Everywhere Directory v1.1"
    def _get_vcs_name(self):
        path = self.get_path('settings')
        settings = encoding.get_file_contents(path)
        for line in settings.splitlines(False):
            fields = line.split('=')
            if len(fields) == 2 and fields[0] == 'rcs_name':
                return fields[1]
        return None
            
    def _upgrade_mapfile(self, path):
        contents = encoding.get_file_contents(path, decode=True)
        old_format = False
        for line in contents.splitlines():
            if len(line.split('=')) == 2:
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
            contents = mapfile.generate(map)
            encoding.set_file_contents(path, contents)
            self.vcs._vcs_update(path)

    def _upgrade(self):
        """
        Comment value field "From" -> "Author".
        Homegrown mapfile -> YAML.
        """
        path = self.get_path('settings')
        self._upgrade_mapfile(path)
        for bug_uuid in os.listdir(self.get_path('bugs')):
            path = self.get_path('bugs', bug_uuid, 'values')
            self._upgrade_mapfile(path)
            c_path = ['bugs', bug_uuid, 'comments']
            if not os.path.exists(self.get_path(*c_path)):
                continue # no comments for this bug
            for comment_uuid in os.listdir(self.get_path(*c_path)):
                path_list = c_path + [comment_uuid, 'values']
                path = self.get_path(*path_list)
                self._upgrade_mapfile(path)
                settings = mapfile.parse(
                    encoding.get_file_contents(path))
                if 'From' in settings:
                    settings['Author'] = settings.pop('From')
                    encoding.set_file_contents(
                        path, mapfile.generate(settings))
                    self.vcs._vcs_update(path)


class Upgrade_1_1_to_1_2 (Upgrader):
    initial_version = "Bugs Everywhere Directory v1.1"
    final_version = "Bugs Everywhere Directory v1.2"
    def _get_vcs_name(self):
        path = self.get_path('settings')
        settings = mapfile.parse(encoding.get_file_contents(path))
        if 'rcs_name' in settings:
            return settings['rcs_name']
        return None
            
    def _upgrade(self):
        """
        BugDir settings field "rcs_name" -> "vcs_name".
        """
        path = self.get_path('settings')
        settings = mapfile.parse(encoding.get_file_contents(path))
        if 'rcs_name' in settings:
            settings['vcs_name'] = settings.pop('rcs_name')
            encoding.set_file_contents(path, mapfile.generate(settings))
            self.vcs._vcs_update(path)

class Upgrade_1_2_to_1_3 (Upgrader):
    initial_version = "Bugs Everywhere Directory v1.2"
    final_version = "Bugs Everywhere Directory v1.3"
    def __init__(self, *args, **kwargs):
        Upgrader.__init__(self, *args, **kwargs)
        self._targets = {} # key: target text,value: new target bug

    def _get_vcs_name(self):
        path = self.get_path('settings')
        settings = mapfile.parse(encoding.get_file_contents(path))
        if 'vcs_name' in settings:
            return settings['vcs_name']
        return None

    def _save_bug_settings(self, bug):
        # The target bugs don't have comments
        path = self.get_path('bugs', bug.uuid, 'values')
        if not os.path.exists(path):
            self.vcs._add_path(path, directory=False)
        path = self.get_path('bugs', bug.uuid, 'values')
        mf = mapfile.generate(bug._get_saved_settings())
        encoding.set_file_contents(path, mf)
        self.vcs._vcs_update(path)

    def _target_bug(self, target_text):
        if target_text not in self._targets:
            bug = libbe.bug.Bug(summary=target_text)
            bug.severity = 'target'
            self._targets[target_text] = bug
        return self._targets[target_text]

    def _upgrade_bugdir_mapfile(self):
        path = self.get_path('settings')
        mf = encoding.get_file_contents(path)
        if mf == libbe.util.InvalidObject:
            return # settings file does not exist
        settings = mapfile.parse(mf)
        if 'target' in settings:
            settings['target'] = self._target_bug(settings['target']).uuid
            mf = mapfile.generate(settings)
            encoding.set_file_contents(path, mf)
            self.vcs._vcs_update(path)

    def _upgrade_bug_mapfile(self, bug_uuid):
        import libbe.command.depend as dep
        path = self.get_path('bugs', bug_uuid, 'values')
        mf = encoding.get_file_contents(path)
        if mf == libbe.util.InvalidObject:
            return # settings file does not exist
        settings = mapfile.parse(mf)
        if 'target' in settings:
            target_bug = self._target_bug(settings['target'])

            blocked_by_string = '%s%s' % (dep.BLOCKED_BY_TAG, bug_uuid)
            dep._add_remove_extra_string(target_bug, blocked_by_string, add=True)
            blocks_string = dep._generate_blocks_string(target_bug)
            estrs = settings.get('extra_strings', [])
            estrs.append(blocks_string)
            settings['extra_strings'] = sorted(estrs)

            settings.pop('target')
            mf = mapfile.generate(settings)
            encoding.set_file_contents(path, mf)
            self.vcs._vcs_update(path)

    def _upgrade(self):
        """
        Bug value field "target" -> target bugs.
        Bugdir value field "target" -> pointer to current target bug.
        """
        for bug_uuid in os.listdir(self.get_path('bugs')):
            self._upgrade_bug_mapfile(bug_uuid)
        self._upgrade_bugdir_mapfile()
        for bug in self._targets.values():
            self._save_bug_settings(bug)

class Upgrade_1_3_to_1_4 (Upgrader):
    initial_version = "Bugs Everywhere Directory v1.3"
    final_version = "Bugs Everywhere Directory v1.4"
    def _get_vcs_name(self):
        path = self.get_path('settings')
        settings = mapfile.parse(encoding.get_file_contents(path))
        if 'vcs_name' in settings:
            return settings['vcs_name']
        return None

    def _upgrade(self):
        """
        add new directory "./be/BUGDIR-UUID"
        "./be/bugs" -> "./be/BUGDIR-UUID/bugs"
        "./be/settings" -> "./be/BUGDIR-UUID/settings"
        """
        self.repo = os.path.abspath(self.repo)
        basenames = [p for p in os.listdir(self.get_path())]
        if not 'bugs' in basenames and not 'settings' in basenames \
                and len([p for p in basenames if len(p)==36]) == 1:
            return # the user has upgraded the directory.
        basenames = [p for p in basenames if p in ['bugs','settings']]
        uuid = libbe.util.id.uuid_gen()
        add = [self.get_path(uuid)]
        move = [(self.get_path(p), self.get_path(uuid, p)) for p in basenames]
        msg = ['Upgrading BE directory version v1.3 to v1.4',
               '',
               "Because BE's VCS drivers don't support 'move',",
               'please make the following changes with your VCS',
               'and re-run BE.  Note that you can choose a different',
               'bugdir UUID to preserve uniformity across branches',
               'of a distributed repository.'
               '',
               'add',
               '  ' + '\n  '.join(add),
               'move',
               '  ' + '\n  '.join(['%s %s' % (a,b) for a,b in move]),
               ]
        self.vcs._cached_path_id.destroy()
        raise Exception('Need user assistance\n%s' % '\n'.join(msg))


upgraders = [Upgrade_1_0_to_1_1,
             Upgrade_1_1_to_1_2,
             Upgrade_1_2_to_1_3,
             Upgrade_1_3_to_1_4]
upgrade_classes = {}
for upgrader in upgraders:
    upgrade_classes[(upgrader.initial_version,upgrader.final_version)]=upgrader

def upgrade(path, current_version,
            target_version=STORAGE_VERSION):
    """
    Call the appropriate upgrade function to convert current_version
    to target_version.  If a direct conversion function does not exist,
    use consecutive conversion functions.
    """
    if current_version not in STORAGE_VERSIONS:
        raise NotImplementedError, \
            "Cannot handle version '%s' yet." % current_version
    if target_version not in STORAGE_VERSIONS:
        raise NotImplementedError, \
            "Cannot handle version '%s' yet." % current_version

    if (current_version, target_version) in upgrade_classes:
        # direct conversion
        upgrade_class = upgrade_classes[(current_version, target_version)]
        u = upgrade_class(path)
        u.upgrade()
    else:
        # consecutive single-step conversion
        i = STORAGE_VERSIONS.index(current_version)
        while True:
            version_a = STORAGE_VERSIONS[i]
            version_b = STORAGE_VERSIONS[i+1]
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
