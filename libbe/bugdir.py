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
import sys
import time
import unittest
import doctest

import bug
import encoding
from properties import Property, doc_property, local_property, \
    defaulting_property, checked_property, fn_checked_property, \
    cached_property, primed_property, change_hook_property, \
    settings_property
import mapfile
import vcs
import settings_object
import upgrade
import utility


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
    Sink to existing root
    ======================

    Consider the following usage case:
    You have a bug directory rooted in
      /path/to/source
    by which I mean the '.be' directory is at
      /path/to/source/.be
    However, you're of in some subdirectory like
      /path/to/source/GUI/testing
    and you want to comment on a bug.  Setting sink_to_root=True wen
    you initialize your BugDir will cause it to search for the '.be'
    file in the ancestors of the path you passed in as 'root'.
      /path/to/source/GUI/testing/.be     miss
      /path/to/source/GUI/.be             miss
      /path/to/source/.be                 hit!
    So it still roots itself appropriately without much work for you.

    File-system access
    ==================

    BugDirs live completely in memory when .sync_with_disk is False.
    This is the default configuration setup by BugDir(from_disk=False).
    If .sync_with_disk == True (e.g. BugDir(from_disk=True)), then
    any changes to the BugDir will be immediately written to disk.

    If you want to change .sync_with_disk, we suggest you use
    .set_sync_with_disk(), which propogates the new setting through to
    all bugs/comments/etc. that have been loaded into memory.  If
    you've been living in memory and want to move to
    .sync_with_disk==True, but you're not sure if anything has been
    changed in memory, a call to save() immediately before the
    .set_sync_with_disk(True) call is a safe move.

    Regardless of .sync_with_disk, a call to .save() will write out
    all the contents that the BugDir instance has loaded into memory.
    If sync_with_disk has been True over the course of all interesting
    changes, this .save() call will be a waste of time.

    The BugDir will only load information from the file system when it
    loads new settings/bugs/comments that it doesn't already have in
    memory and .sync_with_disk == True.

    Allow VCS initialization
    ========================

    This one is for testing purposes.  Setting it to True allows the
    BugDir to search for an installed VCS backend and initialize it in
    the root directory.  This is a convenience option for supporting
    tests of versioning functionality (e.g. .duplicate_bugdir).

    Disable encoding manipulation
    =============================

    This one is for testing purposed.  You might have non-ASCII
    Unicode in your bugs, comments, files, etc.  BugDir instances try
    and support your preferred encoding scheme (e.g. "utf-8") when
    dealing with stream and file input/output.  For stream output,
    this involves replacing sys.stdout and sys.stderr
    (libbe.encode.set_IO_stream_encodings).  However this messes up
    doctest's output catching.  In order to support doctest tests
    using BugDirs, set manipulate_encodings=False, and stick to ASCII
    in your tests.
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

    def _guess_encoding(self):
        return encoding.get_encoding()
    def _check_encoding(value):
        if value != None:
            return encoding.known_encoding(value)
    def _setup_encoding(self, new_encoding):
        # change hook called before generator.
        if new_encoding not in [None, settings_object.EMPTY]:
            if self._manipulate_encodings == True:
                encoding.set_IO_stream_encodings(new_encoding)
    def _set_encoding(self, old_encoding, new_encoding):
        self._setup_encoding(new_encoding)
        self._prop_save_settings(old_encoding, new_encoding)

    @_versioned_property(name="encoding",
                         doc="""The default input/output encoding to use (e.g. "utf-8").""",
                         change_hook=_set_encoding,
                         generator=_guess_encoding,
                         check_fn=_check_encoding)
    def encoding(): return {}

    def _setup_user_id(self, user_id):
        self.vcs.user_id = user_id
    def _guess_user_id(self):
        return self.vcs.get_user_id()
    def _set_user_id(self, old_user_id, new_user_id):
        self._setup_user_id(new_user_id)
        self._prop_save_settings(old_user_id, new_user_id)

    @_versioned_property(name="user_id",
                         doc=
"""The user's prefered name, e.g. 'John Doe <jdoe@example.com>'.  Note
that the Arch VCS backend *enforces* ids with this format.""",
                         change_hook=_set_user_id,
                         generator=_guess_user_id)
    def user_id(): return {}

    @_versioned_property(name="default_assignee",
                         doc=
"""The default assignee for new bugs e.g. 'John Doe <jdoe@example.com>'.""")
    def default_assignee(): return {}

    @_versioned_property(name="vcs_name",
                         doc="""The name of the current VCS.  Kept seperate to make saving/loading
settings easy.  Don't set this attribute.  Set .vcs instead, and
.vcs_name will be automatically adjusted.""",
                         default="None",
                         allowed=["None"]+vcs.VCS_ORDER)
    def vcs_name(): return {}

    def _get_vcs(self, vcs_name=None):
        """Get and root a new revision control system"""
        if vcs_name == None:
            vcs_name = self.vcs_name
        new_vcs = vcs.vcs_by_name(vcs_name)
        self._change_vcs(None, new_vcs)
        return new_vcs
    def _change_vcs(self, old_vcs, new_vcs):
        new_vcs.encoding = self.encoding
        new_vcs.root(self.root)
        self.vcs_name = new_vcs.name

    @Property
    @change_hook_property(hook=_change_vcs)
    @cached_property(generator=_get_vcs)
    @local_property("vcs")
    @doc_property(doc="A revision control system instance.")
    def vcs(): return {}

    def _bug_map_gen(self):
        map = {}
        for bug in self:
            map[bug.uuid] = bug
        for uuid in self.list_uuids():
            if uuid not in map:
                map[uuid] = None
        self._bug_map_value = map # ._bug_map_value used by @local_property

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

    @Property
    @primed_property(primer=_bug_map_gen)
    @local_property("bug_map")
    @doc_property(doc="A dict of (bug-uuid, bug-instance) pairs.")
    def _bug_map(): return {}

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


    def __init__(self, root=None, sink_to_existing_root=True,
                 assert_new_BugDir=False, allow_vcs_init=False,
                 manipulate_encodings=True, from_disk=False, vcs=None):
        list.__init__(self)
        settings_object.SavedSettingsObject.__init__(self)
        self._manipulate_encodings = manipulate_encodings
        if root == None:
            root = os.getcwd()
        if sink_to_existing_root == True:
            self.root = self._find_root(root)
        else:
            if not os.path.exists(root):
                self.root = None
                raise NoRootEntry(root)
            self.root = root
        # get a temporary vcs until we've loaded settings
        self.sync_with_disk = False
        self.vcs = self._guess_vcs()

        if from_disk == True:
            self.sync_with_disk = True
            self.load()
        else:
            self.sync_with_disk = False
            if assert_new_BugDir == True:
                if os.path.exists(self.get_path()):
                    raise AlreadyInitialized, self.get_path()
            if vcs == None:
                vcs = self._guess_vcs(allow_vcs_init)
            self.vcs = vcs
            self._setup_user_id(self.user_id)

    def cleanup(self):
        self.vcs.cleanup()

    # methods for getting the BugDir situated in the filesystem

    def _find_root(self, path):
        """
        Search for an existing bug database dir and it's ancestors and
        return a BugDir rooted there.  Only called by __init__, and
        then only if sink_to_existing_root == True.
        """
        if not os.path.exists(path):
            self.root = None
            raise NoRootEntry(path)
        versionfile=utility.search_parent_directories(path,
                                                      os.path.join(".be", "version"))
        if versionfile != None:
            beroot = os.path.dirname(versionfile)
            root = os.path.dirname(beroot)
            return root
        else:
            beroot = utility.search_parent_directories(path, ".be")
            if beroot == None:
                self.root = None
                raise NoBugDir(path)
            return beroot

    def _guess_vcs(self, allow_vcs_init=False):
        """
        Only called by __init__.
        """
        deepdir = self.get_path()
        if not os.path.exists(deepdir):
            deepdir = os.path.dirname(deepdir)
        new_vcs = vcs.detect_vcs(deepdir)
        install = False
        if new_vcs.name == "None":
            if allow_vcs_init == True:
                new_vcs = vcs.installed_vcs()
                new_vcs.init(self.root)
        return new_vcs

    # methods for saving/loading/accessing settings and properties.

    def get_path(self, *args):
        """
        Return a path relative to .root.
        """
        dir = os.path.join(self.root, ".be")
        if len(args) == 0:
            return dir
        assert args[0] in ["version", "settings", "bugs"], str(args)
        return os.path.join(dir, *args)

    def _get_settings(self, settings_path, for_duplicate_bugdir=False):
        allow_no_vcs = not self.vcs.path_in_root(settings_path)
        if allow_no_vcs == True:
            assert for_duplicate_bugdir == True
        if self.sync_with_disk == False and for_duplicate_bugdir == False:
            # duplicates can ignore this bugdir's .sync_with_disk status
            raise DiskAccessRequired("_get settings")
        try:
            settings = mapfile.map_load(self.vcs, settings_path, allow_no_vcs)
        except vcs.NoSuchFile:
            settings = {"vcs_name": "None"}
        return settings

    def _save_settings(self, settings_path, settings,
                       for_duplicate_bugdir=False):
        allow_no_vcs = not self.vcs.path_in_root(settings_path)
        if allow_no_vcs == True:
            assert for_duplicate_bugdir == True
        if self.sync_with_disk == False and for_duplicate_bugdir == False:
            # duplicates can ignore this bugdir's .sync_with_disk status
            raise DiskAccessRequired("_save settings")
        self.vcs.mkdir(self.get_path(), allow_no_vcs)
        mapfile.map_save(self.vcs, settings_path, settings, allow_no_vcs)

    def load_settings(self):
        self.settings = self._get_settings(self.get_path("settings"))
        self._setup_saved_settings()
        self._setup_user_id(self.user_id)
        self._setup_encoding(self.encoding)
        self._setup_severities(self.severities)
        self._setup_status(self.active_status, self.inactive_status)
        self.vcs = vcs.vcs_by_name(self.vcs_name)
        self._setup_user_id(self.user_id)

    def save_settings(self):
        settings = self._get_saved_settings()
        self._save_settings(self.get_path("settings"), settings)

    def get_version(self, path=None, use_none_vcs=False,
                    for_duplicate_bugdir=False):
        """
        Requires disk access.
        """
        if self.sync_with_disk == False:
            raise DiskAccessRequired("get version")
        if use_none_vcs == True:
            VCS = vcs.vcs_by_name("None")
            VCS.root(self.root)
            VCS.encoding = encoding.get_encoding()
        else:
            VCS = self.vcs

        if path == None:
            path = self.get_path("version")
        allow_no_vcs = not VCS.path_in_root(path)
        if allow_no_vcs == True:
            assert for_duplicate_bugdir == True
        version = VCS.get_file_contents(
            path, allow_no_vcs=allow_no_vcs).rstrip("\n")
        return version

    def set_version(self):
        """
        Requires disk access.
        """
        if self.sync_with_disk == False:
            raise DiskAccessRequired("set version")
        self.vcs.mkdir(self.get_path())
        self.vcs.set_file_contents(self.get_path("version"),
                                   upgrade.BUGDIR_DISK_VERSION+"\n")

    # methods controlling disk access

    def set_sync_with_disk(self, value):
        """
        Adjust .sync_with_disk for the BugDir and all it's children.
        See the BugDir docstring for a description of the role of
        .sync_with_disk.
        """
        self.sync_with_disk = value
        for bug in self:
            bug.set_sync_with_disk(value)

    def load(self):
        """
        Reqires disk access
        """
        version = self.get_version(use_none_vcs=True)
        if version != upgrade.BUGDIR_DISK_VERSION:
            upgrade.upgrade(self.root, version)
        else:
            if not os.path.exists(self.get_path()):
                raise NoBugDir(self.get_path())
            self.load_settings()

    def load_all_bugs(self):
        """
        Requires disk access.
        Warning: this could take a while.
        """
        if self.sync_with_disk == False:
            raise DiskAccessRequired("load all bugs")
        self._clear_bugs()
        for uuid in self.list_uuids():
            self._load_bug(uuid)

    def save(self):
        """
        Note that this command writes to disk _regardless_ of the
        status of .sync_with_disk.

        Save any loaded contents to disk.  Because of lazy loading of
        bugs and comments, this is actually not too inefficient.

        However, if .sync_with_disk = True, then any changes are
        automatically written to disk as soon as they happen, so
        calling this method will just waste time (unless something
        else has been messing with your on-disk files).

        Requires disk access.
        """
        sync_with_disk = self.sync_with_disk
        if sync_with_disk == False:
            self.set_sync_with_disk(True)
        self.set_version()
        self.save_settings()
        for bug in self:
            bug.save()
        if sync_with_disk == False:
            self.set_sync_with_disk(sync_with_disk)

    # methods for managing duplicate BugDirs

    def duplicate_bugdir(self, revision):
        duplicate_path = self.vcs.duplicate_repo(revision)

        duplicate_version_path = os.path.join(duplicate_path, ".be", "version")
        try:
            version = self.get_version(duplicate_version_path,
                                       for_duplicate_bugdir=True)
        except DiskAccessRequired:
            self.sync_with_disk = True # temporarily allow access
            version = self.get_version(duplicate_version_path,
                                       for_duplicate_bugdir=True)
            self.sync_with_disk = False
        if version != upgrade.BUGDIR_DISK_VERSION:
            upgrade.upgrade(duplicate_path, version)

        # setup revision VCS as None, since the duplicate may not be
        # initialized for versioning
        duplicate_settings_path = os.path.join(duplicate_path,
                                               ".be", "settings")
        duplicate_settings = self._get_settings(duplicate_settings_path,
                                                for_duplicate_bugdir=True)
        if "vcs_name" in duplicate_settings:
            duplicate_settings["vcs_name"] = "None"
            duplicate_settings["user_id"] = self.user_id
        if "disabled" in bug.status_values:
            # Hack to support old versions of BE bugs
            duplicate_settings["inactive_status"] = self.inactive_status
        self._save_settings(duplicate_settings_path, duplicate_settings,
                            for_duplicate_bugdir=True)

        return BugDir(duplicate_path, from_disk=True, manipulate_encodings=self._manipulate_encodings)

    def remove_duplicate_bugdir(self):
        self.vcs.remove_duplicate_repo()

    # methods for managing bugs

    def list_uuids(self):
        uuids = []
        if self.sync_with_disk == True and os.path.exists(self.get_path()):
            # list the uuids on disk
            if os.path.exists(self.get_path("bugs")):
                for uuid in os.listdir(self.get_path("bugs")):
                    if not (uuid.startswith('.')):
                        uuids.append(uuid)
                        yield uuid
        # and the ones that are still just in memory
        for bug in self:
            if bug.uuid not in uuids:
                uuids.append(bug.uuid)
                yield bug.uuid

    def _clear_bugs(self):
        while len(self) > 0:
            self.pop()
        self._bug_map_gen()

    def _load_bug(self, uuid):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("_load bug")
        bg = bug.Bug(bugdir=self, uuid=uuid, from_disk=True)
        self.append(bg)
        self._bug_map_gen()
        return bg

    def new_bug(self, uuid=None, summary=None):
        bg = bug.Bug(bugdir=self, uuid=uuid, summary=summary)
        bg.set_sync_with_disk(self.sync_with_disk)
        if bg.sync_with_disk == True:
            bg.save()
        self.append(bg)
        self._bug_map_gen()
        return bg

    def remove_bug(self, bug):
        self.remove(bug)
        if bug.sync_with_disk == True:
            bug.remove()

    def bug_shortname(self, bug):
        """
        Generate short names from uuids.  Picks the minimum number of
        characters (>=3) from the beginning of the uuid such that the
        short names are unique.

        Obviously, as the number of bugs in the database grows, these
        short names will cease to be unique.  The complete uuid should be
        used for long term reference.
        """
        chars = 3
        for uuid in self._bug_map.keys():
            if bug.uuid == uuid:
                continue
            while (bug.uuid[:chars] == uuid[:chars]):
                chars+=1
        return bug.uuid[:chars]

    def bug_from_shortname(self, shortname):
        """
        >>> bd = SimpleBugDir(sync_with_disk=False)
        >>> bug_a = bd.bug_from_shortname('a')
        >>> print type(bug_a)
        <class 'libbe.bug.Bug'>
        >>> print bug_a
        a:om: Bug A
        >>> bd.cleanup()
        """
        matches = []
        self._bug_map_gen()
        for uuid in self._bug_map.keys():
            if uuid.startswith(shortname):
                matches.append(uuid)
        if len(matches) > 1:
            raise MultipleBugMatches(shortname, matches)
        if len(matches) == 1:
            return self.bug_from_uuid(matches[0])
        raise NoBugMatches(shortname)

    def bug_from_uuid(self, uuid):
        if not self.has_bug(uuid):
            raise KeyError("No bug matches %s\n  bug map: %s\n  root: %s" \
                               % (uuid, self._bug_map, self.root))
        if self._bug_map[uuid] == None:
            self._load_bug(uuid)
        return self._bug_map[uuid]

    def has_bug(self, bug_uuid):
        if bug_uuid not in self._bug_map:
            self._bug_map_gen()
            if bug_uuid not in self._bug_map:
                return False
        return True


class SimpleBugDir (BugDir):
    """
    For testing.  Set sync_with_disk==False for a memory-only bugdir.
    >>> bugdir = SimpleBugDir()
    >>> uuids = list(bugdir.list_uuids())
    >>> uuids.sort()
    >>> print uuids
    ['a', 'b']
    >>> bugdir.cleanup()
    """
    def __init__(self, sync_with_disk=True):
        if sync_with_disk == True:
            dir = utility.Dir()
            assert os.path.exists(dir.path)
            root = dir.path
            assert_new_BugDir = True
            vcs_init = True
        else:
            root = "/"
            assert_new_BugDir = False
            vcs_init = False
        BugDir.__init__(self, root, sink_to_existing_root=False,
                    assert_new_BugDir=assert_new_BugDir,
                    allow_vcs_init=vcs_init,
                    manipulate_encodings=False)
        if sync_with_disk == True: # postpone cleanup since dir.cleanup() removes dir.
            self._dir_ref = dir
        bug_a = self.new_bug("a", summary="Bug A")
        bug_a.creator = "John Doe <jdoe@example.com>"
        bug_a.time = 0
        bug_b = self.new_bug("b", summary="Bug B")
        bug_b.creator = "Jane Doe <jdoe@example.com>"
        bug_b.time = 0
        bug_b.status = "closed"
        if sync_with_disk == True:
            self.save()
            self.set_sync_with_disk(True)
    def cleanup(self):
        if hasattr(self, "_dir_ref"):
            self._dir_ref.cleanup()
        BugDir.cleanup(self)

class BugDirTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = utility.Dir()
        self.bugdir = BugDir(self.dir.path, sink_to_existing_root=False,
                             allow_vcs_init=True)
        self.vcs = self.bugdir.vcs
    def tearDown(self):
        self.bugdir.cleanup()
        self.dir.cleanup()
    def fullPath(self, path):
        return os.path.join(self.dir.path, path)
    def assertPathExists(self, path):
        fullpath = self.fullPath(path)
        self.failUnless(os.path.exists(fullpath)==True,
                        "path %s does not exist" % fullpath)
        self.assertRaises(AlreadyInitialized, BugDir,
                          self.dir.path, assertNewBugDir=True)
    def versionTest(self):
        if self.vcs.versioned == False:
            return
        original = self.bugdir.vcs.commit("Began versioning")
        bugA = self.bugdir.bug_from_uuid("a")
        bugA.status = "fixed"
        self.bugdir.save()
        new = self.vcs.commit("Fixed bug a")
        dupdir = self.bugdir.duplicate_bugdir(original)
        self.failUnless(dupdir.root != self.bugdir.root,
                        "%s, %s" % (dupdir.root, self.bugdir.root))
        bugAorig = dupdir.bug_from_uuid("a")
        self.failUnless(bugA != bugAorig,
                        "\n%s\n%s" % (bugA.string(), bugAorig.string()))
        bugAorig.status = "fixed"
        self.failUnless(bug.cmp_status(bugA, bugAorig)==0,
                        "%s, %s" % (bugA.status, bugAorig.status))
        self.failUnless(bug.cmp_severity(bugA, bugAorig)==0,
                        "%s, %s" % (bugA.severity, bugAorig.severity))
        self.failUnless(bug.cmp_assigned(bugA, bugAorig)==0,
                        "%s, %s" % (bugA.assigned, bugAorig.assigned))
        self.failUnless(bug.cmp_time(bugA, bugAorig)==0,
                        "%s, %s" % (bugA.time, bugAorig.time))
        self.failUnless(bug.cmp_creator(bugA, bugAorig)==0,
                        "%s, %s" % (bugA.creator, bugAorig.creator))
        self.failUnless(bugA == bugAorig,
                        "\n%s\n%s" % (bugA.string(), bugAorig.string()))
        self.bugdir.remove_duplicate_bugdir()
        self.failUnless(os.path.exists(dupdir.root)==False, str(dupdir.root))
    def testRun(self):
        self.bugdir.new_bug(uuid="a", summary="Ant")
        self.bugdir.new_bug(uuid="b", summary="Cockroach")
        self.bugdir.new_bug(uuid="c", summary="Praying mantis")
        length = len(self.bugdir)
        self.failUnless(length == 3, "%d != 3 bugs" % length)
        uuids = list(self.bugdir.list_uuids())
        self.failUnless(len(uuids) == 3, "%d != 3 uuids" % len(uuids))
        self.failUnless(uuids == ["a","b","c"], str(uuids))
        bugA = self.bugdir.bug_from_uuid("a")
        bugAprime = self.bugdir.bug_from_shortname("a")
        self.failUnless(bugA == bugAprime, "%s != %s" % (bugA, bugAprime))
        self.bugdir.save()
        self.versionTest()
    def testComments(self, sync_with_disk=False):
        if sync_with_disk == True:
            self.bugdir.set_sync_with_disk(True)
        self.bugdir.new_bug(uuid="a", summary="Ant")
        bug = self.bugdir.bug_from_uuid("a")
        comm = bug.comment_root
        rep = comm.new_reply("Ants are small.")
        rep.new_reply("And they have six legs.")
        if sync_with_disk == False:
            self.bugdir.save()
            self.bugdir.set_sync_with_disk(True)
        self.bugdir._clear_bugs()
        bug = self.bugdir.bug_from_uuid("a")
        bug.load_comments()
        if sync_with_disk == False:
            self.bugdir.set_sync_with_disk(False)
        self.failUnless(len(bug.comment_root)==1, len(bug.comment_root))
        for index,comment in enumerate(bug.comments()):
            if index == 0:
                repLoaded = comment
                self.failUnless(repLoaded.uuid == rep.uuid, repLoaded.uuid)
                self.failUnless(comment.sync_with_disk == sync_with_disk,
                                comment.sync_with_disk)
                self.failUnless(comment.content_type == "text/plain",
                                comment.content_type)
                self.failUnless(repLoaded.settings["Content-type"]=="text/plain",
                                repLoaded.settings)
                self.failUnless(repLoaded.body == "Ants are small.",
                                repLoaded.body)
            elif index == 1:
                self.failUnless(comment.in_reply_to == repLoaded.uuid,
                                repLoaded.uuid)
                self.failUnless(comment.body == "And they have six legs.",
                                comment.body)
            else:
                self.failIf(True, "Invalid comment: %d\n%s" % (index, comment))
    def testSyncedComments(self):
        self.testComments(sync_with_disk=True)

class SimpleBugDirTestCase (unittest.TestCase):
    def setUp(self):
        # create a pre-existing bugdir in a temporary directory
        self.dir = utility.Dir()
        self.original_working_dir = os.getcwd()
        os.chdir(self.dir.path)
        self.bugdir = BugDir(self.dir.path, sink_to_existing_root=False,
                             allow_vcs_init=True)
        self.bugdir.new_bug("preexisting", summary="Hopefully not imported")
        self.bugdir.save()
    def tearDown(self):
        os.chdir(self.original_working_dir)
        self.bugdir.cleanup()
        self.dir.cleanup()
    def testOnDiskCleanLoad(self):
        """SimpleBugDir(sync_with_disk==True) should not import preexisting bugs."""
        bugdir = SimpleBugDir(sync_with_disk=True)
        self.failUnless(bugdir.sync_with_disk==True, bugdir.sync_with_disk)
        uuids = sorted([bug.uuid for bug in bugdir])
        self.failUnless(uuids == ['a', 'b'], uuids)
        bugdir._clear_bugs()
        uuids = sorted([bug.uuid for bug in bugdir])
        self.failUnless(uuids == [], uuids)
        bugdir.load_all_bugs()
        uuids = sorted([bug.uuid for bug in bugdir])
        self.failUnless(uuids == ['a', 'b'], uuids)
        bugdir.cleanup()
    def testInMemoryCleanLoad(self):
        """SimpleBugDir(sync_with_disk==False) should not import preexisting bugs."""
        bugdir = SimpleBugDir(sync_with_disk=False)
        self.failUnless(bugdir.sync_with_disk==False, bugdir.sync_with_disk)
        uuids = sorted([bug.uuid for bug in bugdir])
        self.failUnless(uuids == ['a', 'b'], uuids)
        self.failUnlessRaises(DiskAccessRequired, bugdir.load_all_bugs)
        uuids = sorted([bug.uuid for bug in bugdir])
        self.failUnless(uuids == ['a', 'b'], uuids)
        bugdir._clear_bugs()
        uuids = sorted([bug.uuid for bug in bugdir])
        self.failUnless(uuids == [], uuids)
        bugdir.cleanup()

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
