# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Alexander Belchenko <bialix@ukr.net>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
#                         W. Trevor King <wking@drexel.edu>
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
Define the BugDir class for representing bug comments.
"""

import copy
import errno
import os
import os.path
import time

import libbe
import libbe.storage as storage
from libbe.storage.util.properties import Property, doc_property, \
    local_property, defaulting_property, checked_property, \
    fn_checked_property, cached_property, primed_property, \
    change_hook_property, settings_property
import libbe.storage.util.settings_object as settings_object
import libbe.storage.util.mapfile as mapfile
import libbe.bug as bug
import libbe.util.utility as utility

if libbe.TESTING == True:
    import doctest
    import sys
    import unittest

    import libbe.storage.base


class NoBugDir(Exception):
    def __init__(self, path):
        msg = "The directory \"%s\" has no bug directory." % path
        Exception.__init__(self, msg)
        self.path = path

class NoRootEntry(Exception):
    def __init__(self, path):
        self.path = path
        Exception.__init__(self, "Specified root does not exist: %s" % path)

class AlreadyInitialized(Exception):
    def __init__(self, path):
        self.path = path
        Exception.__init__(self,
                           "Specified root is already initialized: %s" % path)

class MultipleBugMatches(ValueError):
    def __init__(self, shortname, matches):
        msg = ("More than one bug matches %s.  "
               "Please be more specific.\n%s" % (shortname, matches))
        ValueError.__init__(self, msg)
        self.shortname = shortname
        self.matches = matches

class NoBugMatches(KeyError):
    def __init__(self, shortname):
        msg = "No bug matches %s" % shortname
        KeyError.__init__(self, msg)
        self.shortname = shortname

class DiskAccessRequired (Exception):
    def __init__(self, goal):
        msg = "Cannot %s without accessing the disk" % goal
        Exception.__init__(self, msg)


class BugDir (list, settings_object.SavedSettingsObject):
    """
    TODO: simple bugdir manipulation examples...
    """

    settings_properties = []
    required_saved_properties = []
    _prop_save_settings = settings_object.prop_save_settings
    _prop_load_settings = settings_object.prop_load_settings
    def _versioned_property(settings_properties=settings_properties,
                            required_saved_properties=required_saved_properties,
                            **kwargs):
        if "settings_properties" not in kwargs:
            kwargs["settings_properties"] = settings_properties
        if "required_saved_properties" not in kwargs:
            kwargs["required_saved_properties"]=required_saved_properties
        return settings_object.versioned_property(**kwargs)

    @_versioned_property(name="target",
                         doc="The current project development target.")
    def target(): return {}

    def _setup_severities(self, severities):
        if severities not in [None, settings_object.EMPTY]:
            bug.load_severities(severities)
    def _set_severities(self, old_severities, new_severities):
        self._setup_severities(new_severities)
        self._prop_save_settings(old_severities, new_severities)
    @_versioned_property(name="severities",
                         doc="The allowed bug severities and their descriptions.",
                         change_hook=_set_severities)
    def severities(): return {}

    def _setup_status(self, active_status, inactive_status):
        bug.load_status(active_status, inactive_status)
    def _set_active_status(self, old_active_status, new_active_status):
        self._setup_status(new_active_status, self.inactive_status)
        self._prop_save_settings(old_active_status, new_active_status)
    @_versioned_property(name="active_status",
                         doc="The allowed active bug states and their descriptions.",
                         change_hook=_set_active_status)
    def active_status(): return {}

    def _set_inactive_status(self, old_inactive_status, new_inactive_status):
        self._setup_status(self.active_status, new_inactive_status)
        self._prop_save_settings(old_inactive_status, new_inactive_status)
    @_versioned_property(name="inactive_status",
                         doc="The allowed inactive bug states and their descriptions.",
                         change_hook=_set_inactive_status)
    def inactive_status(): return {}

    def _extra_strings_check_fn(value):
        return utility.iterable_full_of_strings(value, \
                         alternative=settings_object.EMPTY)
    def _extra_strings_change_hook(self, old, new):
        self.extra_strings.sort() # to make merging easier
        self._prop_save_settings(old, new)
    @_versioned_property(name="extra_strings",
                         doc="Space for an array of extra strings.  Useful for storing state for functionality implemented purely in becommands/<some_function>.py.",
                         default=[],
                         check_fn=_extra_strings_check_fn,
                         change_hook=_extra_strings_change_hook,
                         mutable=True)
    def extra_strings(): return {}

    def _bug_map_gen(self):
        map = {}
        for bug in self:
            map[bug.uuid] = bug
        for uuid in self.uuids():
            if uuid not in map:
                map[uuid] = None
        self._bug_map_value = map # ._bug_map_value used by @local_property

    @Property
    @primed_property(primer=_bug_map_gen)
    @local_property("bug_map")
    @doc_property(doc="A dict of (bug-uuid, bug-instance) pairs.")
    def _bug_map(): return {}

    def __init__(self, storage, uuid=None, from_storage=False):
        list.__init__(self)
        settings_object.SavedSettingsObject.__init__(self)
        self.storage = storage
        self.id = libbe.util.id.ID(self, 'bugdir')
        self.uuid = uuid
        if from_storage == True:
            if self.uuid == None:
                self.uuid = [c for c in self.storage.children()
                             if c != 'version'][0]
            self.load_settings()
        else:
            if self.uuid == None:
                self.uuid = libbe.util.id.uuid_gen()
            self.settings = {}
            self._setup_saved_settings()
            if self.storage != None and self.storage.is_writeable():
                self.save()

    # methods for saving/loading/accessing settings and properties.

    def load_settings(self, settings_mapfile=None):
        if settings_mapfile == None:
            settings_mapfile = \
                self.storage.get(self.id.storage('settings'), default='\n')
        try:
            self.settings = mapfile.parse(settings_mapfile)
        except mapfile.InvalidMapfileContents, e:
            raise Exception('Invalid settings file for bugdir %s\n'
                            '(BE version missmatch?)' % self.id.user())
        self._setup_saved_settings()
        #self._setup_user_id(self.user_id)
        self._setup_severities(self.severities)
        self._setup_status(self.active_status, self.inactive_status)

    def save_settings(self):
        mf = mapfile.generate(self._get_saved_settings())
        self.storage.set(self.id.storage('settings'), mf)

    def load_all_bugs(self):
        """
        Warning: this could take a while.
        """
        self._clear_bugs()
        for uuid in self.uuids():
            self._load_bug(uuid)

    def save(self):
        """
        Save any loaded contents to storage.  Because of lazy loading
        of bugs and comments, this is actually not too inefficient.

        However, if self.storage.is_writeable() == True, then any
        changes are automatically written to storage as soon as they
        happen, so calling this method will just waste time (unless
        something else has been messing with your stored files).
        """
        self.storage.add(self.id.storage(), directory=True)
        self.storage.add(self.id.storage('settings'), parent=self.id.storage(),
                         directory=False)
        self.save_settings()
        for bug in self:
            bug.save()

    # methods for managing bugs

    def uuids(self):
        uuids = []
        # list the uuids in memory
        for bug in self:
            uuids.append(bug.uuid)
            yield bug.uuid
        if self.storage != None and self.storage.is_readable():
            # and the ones that are still just in storage
            child_uuids = libbe.util.id.child_uuids(
                self.storage.children(self.id.storage()))
            for id in child_uuids:
                if id not in uuids:
                    yield id

    def _clear_bugs(self):
        while len(self) > 0:
            self.pop()
        self._bug_map_gen()

    def _load_bug(self, uuid):
        bg = bug.Bug(bugdir=self, uuid=uuid, from_storage=True)
        self.append(bg)
        self._bug_map_gen()
        return bg

    def new_bug(self, summary=None, _uuid=None):
        bg = bug.Bug(bugdir=self, uuid=_uuid, summary=summary,
                     from_storage=False)
        self.append(bg)
        self._bug_map_gen()
        return bg

    def remove_bug(self, bug):
        self.remove(bug)
        if self.storage != None and self.storage.is_writeable():
            bug.remove()

    def bug_from_uuid(self, uuid):
        if not self.has_bug(uuid):
            raise NoBugMatches('No bug matches %s\n  bug map: %s\n  repo: %s' \
                               % (uuid, self._bug_map, self.storage))
        if self._bug_map[uuid] == None:
            self._load_bug(uuid)
        return self._bug_map[uuid]

    def has_bug(self, bug_uuid):
        if bug_uuid not in self._bug_map:
            self._bug_map_gen()
            if bug_uuid not in self._bug_map:
                return False
        return True

    # methods for id generation

    def sibling_uuids(self):
        return []

    # methods for managing duplicate BugDirs

    def duplicate_bugdir(self, revision):
        """
        Duplicate bugdirs are read-only copies used for generating
        diffs between revisions.
        """
        s = copy.deepcopy(self.storage)
        s.writeable = False
        class RevisionedStorageGet (object):
            def __init__(self, storage, default_revision):
                self.s = storage
                self.sget = self.s.get
                self.r = default_revision
            def get(self, *args, **kwargs):
                if not 'revision' in kwargs or kwargs['revision'] == None:
                    kwargs['revision'] = self.r
                return self.sget(*args, **kwargs)
        rsg = RevisionedStorageGet(s, revision)
        s.get = rsg.get
        dbd = BugDir(s, from_storage=True)
#        dbd = copy.copy(self)
#        dbd.storage = copy.copy(self.storage)
#        dbd._bug_map = copy.copy(self._bug_map)
#        dbd.storage.writeable = False
#        added,changed,removed = self.storage.changed_since(revision)
#        for id in added:
#            pass
#        for id in removed:
#            pass
#        for id in changed:
#            parsed = libbe.util.id.parse_id(id)
#            if parsed['type'] == 'bugdir':
#                assert parsed['remaining'] == ['settings'], parsed['remaining']
#                dbd._settings = copy.copy(self._settings)
#                mf = self.storage.get(self.id.storage('settings'), default='\n',
#                                      revision=revision)
#                dbd.load_settings(mf)
#            else:
#                if parsed['bug'] not in self:
#                    self._load_bug(parsed['bug'])
#                    dbd._load_bug(parsed['bug'])
#                else:
#                    bug = copy.copy(self._bug_map[parsed['bug']])
#                    bug.settings = copy.copy(bug.settings)
#                    dbd._bug_map[parsed['bug']] = bug
#                if parsed['type'] == 'bug':
#                    assert parsed['remaining'] == ['values'], parsed['remaining']
#                    mf = self.storage.get(self.id.storage('values'), default='\n',
#                                          revision=revision)
#                    bug.load_settings(mf)
#                elif parsed['type'] == 'comment':
#                    assert parsed['remaining'] in [['values'], ['body']], \
#                        parsed['remaining']
#                    bug.comment_root = copy.deepcopy(bug.comment_root)
#                    comment = bug.comment_from_uuid(parsed['comment'])
#                    if parsed['remaining'] == ['values']:
#                        mf = self.storage.get(self.id.storage('values'), default='\n',
#                                              revision=revision)
#                        comment.load_settings(mf)
#                    else:
#                        body = self.storage.get(self.id.storage('body'), default='\n',
#                                                revision=revision)
#                        comment.body = body
#                else:
#                    assert 1==0, 'Unkown type "%s" for id "%s"' % (type, id)
#        dbd.storage.readable = False # so we won't read in added bugs, etc.
        return dbd

if libbe.TESTING == True:
    class SimpleBugDir (BugDir):
        """
        For testing.  Set memory=True for a memory-only bugdir.
        >>> bugdir = SimpleBugDir()
        >>> uuids = list(bugdir.uuids())
        >>> uuids.sort()
        >>> print uuids
        ['a', 'b']
        >>> bugdir.cleanup()
        """
        def __init__(self, memory=True, versioned=False):
            if memory == True:
                storage = None
            else:
                dir = utility.Dir()
                self._dir_ref = dir # postpone cleanup since dir.cleanup() removes dir.
                if versioned == False:
                    storage = libbe.storage.base.Storage(dir.path)
                else:
                    storage = libbe.storage.base.VersionedStorage(dir.path)
                storage.init()
                storage.connect()
            BugDir.__init__(self, storage=storage, uuid='abc123')
            bug_a = self.new_bug(summary='Bug A', _uuid='a')
            bug_a.creator = 'John Doe <jdoe@example.com>'
            bug_a.time = 0
            bug_b = self.new_bug(summary='Bug B', _uuid='b')
            bug_b.creator = 'Jane Doe <jdoe@example.com>'
            bug_b.time = 0
            bug_b.status = 'closed'
            if self.storage != None:
                self.storage.disconnect() # flush to storage
                self.storage.connect()

        def cleanup(self):
            if self.storage != None:
                self.storage.writeable = True
                self.storage.disconnect()
                self.storage.destroy()
            if hasattr(self, '_dir_ref'):
                self._dir_ref.cleanup()

        def flush_reload(self):
            if self.storage != None:
                self.storage.disconnect()
                self.storage.connect()
                self._clear_bugs()

#    class BugDirTestCase(unittest.TestCase):
#        def setUp(self):
#            self.dir = utility.Dir()
#            self.bugdir = BugDir(self.dir.path, sink_to_existing_root=False,
#                                 allow_storage_init=True)
#            self.storage = self.bugdir.storage
#        def tearDown(self):
#            self.bugdir.cleanup()
#            self.dir.cleanup()
#        def fullPath(self, path):
#            return os.path.join(self.dir.path, path)
#        def assertPathExists(self, path):
#            fullpath = self.fullPath(path)
#            self.failUnless(os.path.exists(fullpath)==True,
#                            "path %s does not exist" % fullpath)
#            self.assertRaises(AlreadyInitialized, BugDir,
#                              self.dir.path, assertNewBugDir=True)
#        def versionTest(self):
#            if self.storage != None and self.storage.versioned == False:
#                return
#            original = self.bugdir.storage.commit("Began versioning")
#            bugA = self.bugdir.bug_from_uuid("a")
#            bugA.status = "fixed"
#            self.bugdir.save()
#            new = self.storage.commit("Fixed bug a")
#            dupdir = self.bugdir.duplicate_bugdir(original)
#            self.failUnless(dupdir.root != self.bugdir.root,
#                            "%s, %s" % (dupdir.root, self.bugdir.root))
#            bugAorig = dupdir.bug_from_uuid("a")
#            self.failUnless(bugA != bugAorig,
#                            "\n%s\n%s" % (bugA.string(), bugAorig.string()))
#            bugAorig.status = "fixed"
#            self.failUnless(bug.cmp_status(bugA, bugAorig)==0,
#                            "%s, %s" % (bugA.status, bugAorig.status))
#            self.failUnless(bug.cmp_severity(bugA, bugAorig)==0,
#                            "%s, %s" % (bugA.severity, bugAorig.severity))
#            self.failUnless(bug.cmp_assigned(bugA, bugAorig)==0,
#                            "%s, %s" % (bugA.assigned, bugAorig.assigned))
#            self.failUnless(bug.cmp_time(bugA, bugAorig)==0,
#                            "%s, %s" % (bugA.time, bugAorig.time))
#            self.failUnless(bug.cmp_creator(bugA, bugAorig)==0,
#                            "%s, %s" % (bugA.creator, bugAorig.creator))
#            self.failUnless(bugA == bugAorig,
#                            "\n%s\n%s" % (bugA.string(), bugAorig.string()))
#            self.bugdir.remove_duplicate_bugdir()
#            self.failUnless(os.path.exists(dupdir.root)==False,
#                            str(dupdir.root))
#        def testRun(self):
#            self.bugdir.new_bug(uuid="a", summary="Ant")
#            self.bugdir.new_bug(uuid="b", summary="Cockroach")
#            self.bugdir.new_bug(uuid="c", summary="Praying mantis")
#            length = len(self.bugdir)
#            self.failUnless(length == 3, "%d != 3 bugs" % length)
#            uuids = list(self.bugdir.uuids())
#            self.failUnless(len(uuids) == 3, "%d != 3 uuids" % len(uuids))
#            self.failUnless(uuids == ["a","b","c"], str(uuids))
#            bugA = self.bugdir.bug_from_uuid("a")
#            bugAprime = self.bugdir.bug_from_shortname("a")
#            self.failUnless(bugA == bugAprime, "%s != %s" % (bugA, bugAprime))
#            self.bugdir.save()
#            self.versionTest()
#        def testComments(self, sync_with_disk=False):
#            if sync_with_disk == True:
#                self.bugdir.set_sync_with_disk(True)
#            self.bugdir.new_bug(uuid="a", summary="Ant")
#            bug = self.bugdir.bug_from_uuid("a")
#            comm = bug.comment_root
#            rep = comm.new_reply("Ants are small.")
#            rep.new_reply("And they have six legs.")
#            if sync_with_disk == False:
#                self.bugdir.save()
#                self.bugdir.set_sync_with_disk(True)
#            self.bugdir._clear_bugs()
#            bug = self.bugdir.bug_from_uuid("a")
#            bug.load_comments()
#            if sync_with_disk == False:
#                self.bugdir.set_sync_with_disk(False)
#            self.failUnless(len(bug.comment_root)==1, len(bug.comment_root))
#            for index,comment in enumerate(bug.comments()):
#                if index == 0:
#                    repLoaded = comment
#                    self.failUnless(repLoaded.uuid == rep.uuid, repLoaded.uuid)
#                    self.failUnless(comment.sync_with_disk == sync_with_disk,
#                                    comment.sync_with_disk)
#                    self.failUnless(comment.content_type == "text/plain",
#                                    comment.content_type)
#                    self.failUnless(repLoaded.settings["Content-type"] == \
#                                        "text/plain",
#                                    repLoaded.settings)
#                    self.failUnless(repLoaded.body == "Ants are small.",
#                                    repLoaded.body)
#                elif index == 1:
#                    self.failUnless(comment.in_reply_to == repLoaded.uuid,
#                                    repLoaded.uuid)
#                    self.failUnless(comment.body == "And they have six legs.",
#                                    comment.body)
#                else:
#                    self.failIf(True,
#                                "Invalid comment: %d\n%s" % (index, comment))
#        def testSyncedComments(self):
#            self.testComments(sync_with_disk=True)

    class SimpleBugDirTestCase (unittest.TestCase):
        def setUp(self):
            # create a pre-existing bugdir in a temporary directory
            self.dir = utility.Dir()
            self.storage = libbe.storage.base.Storage(self.dir.path)
            self.storage.init()
            self.storage.connect()
            self.bugdir = BugDir(self.storage)
            self.bugdir.new_bug(summary="Hopefully not imported",
                                _uuid="preexisting")
            self.storage.disconnect()
            self.storage.connect()
        def tearDown(self):
            if self.storage != None:
                self.storage.disconnect()
                self.storage.destroy()
            self.dir.cleanup()
        def testOnDiskCleanLoad(self):
            """
            SimpleBugDir(memory==False) should not import
            preexisting bugs.
            """
            bugdir = SimpleBugDir(memory=False)
            self.failUnless(bugdir.storage.is_readable() == True,
                            bugdir.storage.is_readable())
            self.failUnless(bugdir.storage.is_writeable() == True,
                            bugdir.storage.is_writeable())
            uuids = sorted([bug.uuid for bug in bugdir])
            self.failUnless(uuids == ['a', 'b'], uuids)
            bugdir.flush_reload()
            uuids = sorted(bugdir.uuids())
            self.failUnless(uuids == ['a', 'b'], uuids)
            uuids = sorted([bug.uuid for bug in bugdir])
            self.failUnless(uuids == [], uuids)
            bugdir.load_all_bugs()
            uuids = sorted([bug.uuid for bug in bugdir])
            self.failUnless(uuids == ['a', 'b'], uuids)
            bugdir.cleanup()
        def testInMemoryCleanLoad(self):
            """
            SimpleBugDir(memory==True) should not import
            preexisting bugs.
            """
            bugdir = SimpleBugDir(memory=True)
            self.failUnless(bugdir.storage == None, bugdir.storage)
            uuids = sorted([bug.uuid for bug in bugdir])
            self.failUnless(uuids == ['a', 'b'], uuids)
            uuids = sorted([bug.uuid for bug in bugdir])
            self.failUnless(uuids == ['a', 'b'], uuids)
            bugdir._clear_bugs()
            uuids = sorted(bugdir.uuids())
            self.failUnless(uuids == [], uuids)
            uuids = sorted([bug.uuid for bug in bugdir])
            self.failUnless(uuids == [], uuids)
            bugdir.cleanup()

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])

#    def _get_settings(self, settings_path, for_duplicate_bugdir=False):
#        allow_no_storage = not self.storage.path_in_root(settings_path)
#        if allow_no_storage == True:
#            assert for_duplicate_bugdir == True
#        if self.sync_with_disk == False and for_duplicate_bugdir == False:
#            # duplicates can ignore this bugdir's .sync_with_disk status
#            raise DiskAccessRequired("_get settings")
#        try:
#            settings = mapfile.map_load(self.storage, settings_path, allow_no_storage)
#        except storage.NoSuchFile:
#            settings = {"storage_name": "None"}
#        return settings

#    def _save_settings(self, settings_path, settings,
#                       for_duplicate_bugdir=False):
#        allow_no_storage = not self.storage.path_in_root(settings_path)
#        if allow_no_storage == True:
#            assert for_duplicate_bugdir == True
#        if self.sync_with_disk == False and for_duplicate_bugdir == False:
#            # duplicates can ignore this bugdir's .sync_with_disk status
#            raise DiskAccessRequired("_save settings")
#        self.storage.mkdir(self.get_path(), allow_no_storage)
#        mapfile.map_save(self.storage, settings_path, settings, allow_no_storage)
