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
import errno
import time
import copy
import unittest
import doctest

from properties import Property, doc_property, local_property, \
    defaulting_property, checked_property, fn_checked_property, \
    cached_property, primed_property, change_hook_property, \
    settings_property
import settings_object
import mapfile
import bug
import rcs
import encoding
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

class InvalidValue(ValueError):
    def __init__(self, name, value):
        msg = "Cannot assign value %s to %s" % (value, name)
        Exception.__init__(self, msg)
        self.name = name
        self.value = value

class MultipleBugMatches(ValueError):
    def __init__(self, shortname, matches):
        msg = ("More than one bug matches %s.  "
               "Please be more specific.\n%s" % shortname, matches)
        ValueError.__init__(self, msg)
        self.shortname = shortnamename
        self.matches = matches


TREE_VERSION_STRING = "Bugs Everywhere Tree 1 0\n"


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
    
    When rooted in non-bugdir directory, BugDirs live completely in
    memory until the first call to .save().  This creates a '.be'
    sub-directory containing configurations options, bugs, comments,
    etc.  Once this sub-directory has been created (possibly by
    another BugDir instance) any changes to the BugDir in memory will
    be flushed to the file system automatically.  However, the BugDir
    will only load information from the file system when it loads new
    bugs/comments that it doesn't already have in memory, or when it
    explicitly asked to do so (e.g. .load() or __init__(from_disk=True)).
    
    Allow RCS initialization
    ========================
    
    This one is for testing purposes.  Setting it to True allows the
    BugDir to search for an installed RCS backend and initialize it in
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
                         doc="The current project development target")
    def target(): return {}

    def _guess_encoding(self):
        return encoding.get_encoding()
    def _check_encoding(value):
        if value != None and value != settings_object.EMPTY:
            return encoding.known_encoding(value)
    def _setup_encoding(self, new_encoding):
        if new_encoding != None and new_encoding != settings_object.EMPTY:
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

    def _guess_user_id(self):
        return self.rcs.get_user_id()
    def _set_user_id(self, old_user_id, new_user_id):
        self.rcs.user_id = new_user_id
        self._prop_save_settings(old_user_id, new_user_id)

    @_versioned_property(name="user_id",
                         doc=
"""The user's prefered name, e.g 'John Doe <jdoe@example.com>'.  Note
that the Arch RCS backend *enforces* ids with this format.""",
                         change_hook=_set_user_id,
                         generator=_guess_user_id)
    def user_id(): return {}

    @_versioned_property(name="rcs_name",
                         doc="""The name of the current RCS.  Kept seperate to make saving/loading
settings easy.  Don't set this attribute.  Set .rcs instead, and
.rcs_name will be automatically adjusted.""",
                         default="None",
                         allowed=["None", "Arch", "bzr", "git", "hg"])
    def rcs_name(): return {}

    def _get_rcs(self, rcs_name=None):
        """Get and root a new revision control system"""
        if rcs_name == None:
            rcs_name = self.rcs_name
        new_rcs = rcs.rcs_by_name(rcs_name)
        self._change_rcs(None, new_rcs)
        return new_rcs
    def _change_rcs(self, old_rcs, new_rcs):
        new_rcs.encoding = self.encoding
        new_rcs.root(self.root)
        self.rcs_name = new_rcs.name

    @Property
    @change_hook_property(hook=_change_rcs)
    @cached_property(generator=_get_rcs)
    @local_property("rcs")
    @doc_property(doc="A revision control system instance.")
    def rcs(): return {}

    def _bug_map_gen(self):
        map = {}
        for bug in self:
            map[bug.uuid] = bug
        for uuid in self.list_uuids():
            if uuid not in map:
                map[uuid] = None
        self._bug_map_value = map # ._bug_map_value used by @local_property
    
    @Property
    @primed_property(primer=_bug_map_gen)
    @local_property("bug_map")
    @doc_property(doc="A dict of (bug-uuid, bug-instance) pairs.")
    def _bug_map(): return {}

    def _setup_severities(self, severities):
        if severities != None and severities != settings_object.EMPTY:
            bug.load_severities(severities)
    def _set_severities(self, old_severities, new_severities):
        self._setup_severities(new_severities)
        self._prop_save_settings(old_severities, new_severities)
    @_versioned_property(name="severities",
                         doc="The allowed bug severities and their descriptions.",
                         change_hook=_set_severities)
    def severities(): return {}


    def __init__(self, root=None, sink_to_existing_root=True,
                 assert_new_BugDir=False, allow_rcs_init=False,
                 manipulate_encodings=True,
                 from_disk=False, rcs=None):
        list.__init__(self)
        settings_object.SavedSettingsObject.__init__(self)
        self._manipulate_encodings = manipulate_encodings
        if root == None:
            root = os.getcwd()
        if sink_to_existing_root == True:
            self.root = self._find_root(root)
        else:
            if not os.path.exists(root):
                raise NoRootEntry(root)
            self.root = root
        # get a temporary rcs until we've loaded settings
        self.sync_with_disk = False
        self.rcs = self._guess_rcs()
        
        if from_disk == True:
            self.sync_with_disk = True
            self.load()
        else:
            self.sync_with_disk = False
            if assert_new_BugDir == True:
                if os.path.exists(self.get_path()):
                    raise AlreadyInitialized, self.get_path()
            if rcs == None:
                rcs = self._guess_rcs(allow_rcs_init)
            self.rcs = rcs
            user_id = self.rcs.get_user_id()

    def _find_root(self, path):
        """
        Search for an existing bug database dir and it's ancestors and
        return a BugDir rooted there.
        """
        if not os.path.exists(path):
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
                raise NoBugDir(path)
            return beroot
        
    def get_version(self, path=None, use_none_rcs=False):
        if use_none_rcs == True:
            RCS = rcs.rcs_by_name("None")
            RCS.root(self.root)
            RCS.encoding = encoding.get_encoding()
        else:
            RCS = self.rcs

        if path == None:
            path = self.get_path("version")
        tree_version = RCS.get_file_contents(path)
        return tree_version

    def set_version(self):
        self.rcs.set_file_contents(self.get_path("version"),
                                   TREE_VERSION_STRING)

    def get_path(self, *args):
        my_dir = os.path.join(self.root, ".be")
        if len(args) == 0:
            return my_dir
        assert args[0] in ["version", "settings", "bugs"], str(args)
        return os.path.join(my_dir, *args)

    def _guess_rcs(self, allow_rcs_init=False):
        deepdir = self.get_path()
        if not os.path.exists(deepdir):
            deepdir = os.path.dirname(deepdir)
        new_rcs = rcs.detect_rcs(deepdir)
        install = False
        if new_rcs.name == "None":
            if allow_rcs_init == True:
                new_rcs = rcs.installed_rcs()
                new_rcs.init(self.root)
        return new_rcs

    def load(self):
        version = self.get_version(use_none_rcs=True)
        if version != TREE_VERSION_STRING:
            raise NotImplementedError, \
                "BugDir cannot handle version '%s' yet." % version
        else:
            if not os.path.exists(self.get_path()):
                raise NoBugDir(self.get_path())
            self.load_settings()
            
            self.rcs = rcs.rcs_by_name(self.rcs_name)
            self._setup_encoding(self.encoding)
            self._setup_severities(self.severities)

    def load_all_bugs(self):
        "Warning: this could take a while."
        self._clear_bugs()
        for uuid in self.list_uuids():
            self._load_bug(uuid)

    def save(self):
        self.rcs.mkdir(self.get_path())
        self.set_version()
        self.save_settings()
        self.rcs.mkdir(self.get_path("bugs"))
        for bug in self:
            bug.save()

    def load_settings(self):
        self.settings = self._get_settings(self.get_path("settings"))
        self._setup_saved_settings()

    def _get_settings(self, settings_path):
        allow_no_rcs = not self.rcs.path_in_root(settings_path)
        # allow_no_rcs=True should only be for the special case of
        # configuring duplicate bugdir settings
        
        try:
            settings = mapfile.map_load(self.rcs, settings_path, allow_no_rcs)
        except rcs.NoSuchFile:
            settings = {"rcs_name": "None"}
        return settings

    def save_settings(self):
        settings = self._get_saved_settings()
        self._save_settings(self.get_path("settings"), settings)

    def _save_settings(self, settings_path, settings):
        allow_no_rcs = not self.rcs.path_in_root(settings_path)
        # allow_no_rcs=True should only be for the special case of
        # configuring duplicate bugdir settings
        mapfile.map_save(self.rcs, settings_path, settings, allow_no_rcs)

    def duplicate_bugdir(self, revision):
        duplicate_path = self.rcs.duplicate_repo(revision)

        # setup revision RCS as None, since the duplicate may not be
        # initialized for versioning
        duplicate_settings_path = os.path.join(duplicate_path,
                                               ".be", "settings")
        duplicate_settings = self._get_settings(duplicate_settings_path)
        if "rcs_name" in duplicate_settings:
            duplicate_settings["rcs_name"] = "None"
            duplicate_settings["user_id"] = self.user_id
            self._save_settings(duplicate_settings_path, duplicate_settings)

        return BugDir(duplicate_path, from_disk=True, manipulate_encodings=self._manipulate_encodings)

    def remove_duplicate_bugdir(self):
        self.rcs.remove_duplicate_repo()

    def list_uuids(self):
        uuids = []
        if os.path.exists(self.get_path()):
            # list the uuids on disk
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
        bg = bug.Bug(bugdir=self, uuid=uuid, from_disk=True)
        self.append(bg)
        self._bug_map_gen()
        return bg

    def new_bug(self, uuid=None, summary=None):
        bg = bug.Bug(bugdir=self, uuid=uuid, summary=summary)
        self.append(bg)
        self._bug_map_gen()
        return bg

    def remove_bug(self, bug):
        self.remove(bug)
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
        >>> bd = simple_bug_dir()
        >>> bug_a = bd.bug_from_shortname('a')
        >>> print type(bug_a)
        <class 'libbe.bug.Bug'>
        >>> print bug_a
        a:om: Bug A
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
        raise KeyError("No bug matches %s" % shortname)

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
    assert os.path.exists(dir.path)
    bugdir = BugDir(dir.path, sink_to_existing_root=False, allow_rcs_init=True,
                    manipulate_encodings=False)
    bugdir._dir_ref = dir # postpone cleanup since dir.__del__() removes dir.
    bug_a = bugdir.new_bug("a", summary="Bug A")
    bug_a.creator = "John Doe <jdoe@example.com>"
    bug_a.time = 0
    bug_b = bugdir.new_bug("b", summary="Bug B")
    bug_b.creator = "Jane Doe <jdoe@example.com>"
    bug_b.time = 0
    bug_b.status = "closed"
    bugdir.save()
    return bugdir


class BugDirTestCase(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
    def setUp(self):
        self.dir = utility.Dir()
        self.bugdir = BugDir(self.dir.path, sink_to_existing_root=False,
                             allow_rcs_init=True)
        self.rcs = self.bugdir.rcs
    def tearDown(self):
        self.rcs.cleanup()
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
        if self.rcs.versioned == False:
            return
        original = self.bugdir.rcs.commit("Began versioning")
        bugA = self.bugdir.bug_from_uuid("a")
        bugA.status = "fixed"
        self.bugdir.save()
        new = self.rcs.commit("Fixed bug a")
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
    def testComments(self):
        self.bugdir.new_bug(uuid="a", summary="Ant")
        bug = self.bugdir.bug_from_uuid("a")
        comm = bug.comment_root
        rep = comm.new_reply("Ants are small.")
        rep.new_reply("And they have six legs.")
        self.bugdir.save()
        self.bugdir._clear_bugs()        
        bug = self.bugdir.bug_from_uuid("a")
        bug.load_comments()
        self.failUnless(len(bug.comment_root)==1, len(bug.comment_root))
        for index,comment in enumerate(bug.comments()):
            if index == 0:
                repLoaded = comment
                self.failUnless(repLoaded.uuid == rep.uuid, repLoaded.uuid)
                self.failUnless(comment.sync_with_disk == True,
                                comment.sync_with_disk)
                #load_settings()
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

unitsuite = unittest.TestLoader().loadTestsFromTestCase(BugDirTestCase)
suite = unittest.TestSuite([unitsuite])#, doctest.DocTestSuite()])
