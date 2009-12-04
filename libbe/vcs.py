# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Alexander Belchenko <bialix@ukr.net>
#                         Ben Finney <benf@cybersource.com.au>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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
Define the base VCS (Version Control System) class, which should be
subclassed by other Version Control System backends.  The base class
implements a "do not version" VCS.
"""

import codecs
import os
import os.path
import re
from socket import gethostname
import shutil
import sys
import tempfile

import libbe
from utility import Dir, search_parent_directories
from subproc import CommandError, invoke
from plugin import get_plugin

if libbe.TESTING == True:
    import unittest
    import doctest


# List VCS modules in order of preference.
# Don't list this module, it is implicitly last.
VCS_ORDER = ['arch', 'bzr', 'darcs', 'git', 'hg']

def set_preferred_vcs(name):
    global VCS_ORDER
    assert name in VCS_ORDER, \
        'unrecognized VCS %s not in\n  %s' % (name, VCS_ORDER)
    VCS_ORDER.remove(name)
    VCS_ORDER.insert(0, name)

def _get_matching_vcs(matchfn):
    """Return the first module for which matchfn(VCS_instance) is true"""
    for submodname in VCS_ORDER:
        module = get_plugin('libbe', submodname)
        vcs = module.new()
        if matchfn(vcs) == True:
            return vcs
        vcs.cleanup()
    return VCS()
    
def vcs_by_name(vcs_name):
    """Return the module for the VCS with the given name"""
    return _get_matching_vcs(lambda vcs: vcs.name == vcs_name)

def detect_vcs(dir):
    """Return an VCS instance for the vcs being used in this directory"""
    return _get_matching_vcs(lambda vcs: vcs.detect(dir))

def installed_vcs():
    """Return an instance of an installed VCS"""
    return _get_matching_vcs(lambda vcs: vcs.installed())



class SettingIDnotSupported(NotImplementedError):
    pass

class VCSnotRooted(Exception):
    def __init__(self):
        msg = "VCS not rooted"
        Exception.__init__(self, msg)

class PathNotInRoot(Exception):
    def __init__(self, path, root):
        msg = "Path '%s' not in root '%s'" % (path, root)
        Exception.__init__(self, msg)
        self.path = path
        self.root = root

class NoSuchFile(Exception):
    def __init__(self, pathname, root="."):
        path = os.path.abspath(os.path.join(root, pathname))
        Exception.__init__(self, "No such file: %s" % path)

class EmptyCommit(Exception):
    def __init__(self):
        Exception.__init__(self, "No changes to commit")


def new():
    return VCS()

class VCS(object):
    """
    This class implements a 'no-vcs' interface.

    Support for other VCSs can be added by subclassing this class, and
    overriding methods _vcs_*() with code appropriate for your VCS.
    
    The methods _u_*() are utility methods available to the _vcs_*()
    methods.
    """
    name = "None"
    client = "" # command-line tool for _u_invoke_client
    versioned = False
    def __init__(self, paranoid=False, encoding=sys.getdefaultencoding()):
        self.paranoid = paranoid
        self.verboseInvoke = False
        self.rootdir = None
        self._duplicateBasedir = None
        self._duplicateDirname = None
        self.encoding = encoding
        self.version = self._get_version()
    def __str__(self):
        return "<%s %s>" % (self.__class__.__name__, id(self))
    def __repr__(self):
        return str(self)
    def _vcs_version(self):
        """
        Return the VCS version string.
        """
        return "0.0"
    def _vcs_detect(self, path=None):
        """
        Detect whether a directory is revision controlled with this VCS.
        """
        return True
    def _vcs_root(self, path):
        """
        Get the VCS root.  This is the default working directory for
        future invocations.  You would normally set this to the root
        directory for your VCS.
        """
        if os.path.isdir(path)==False:
            path = os.path.dirname(path)
            if path == "":
                path = os.path.abspath(".")
        return path
    def _vcs_init(self, path):
        """
        Begin versioning the tree based at path.
        """
        pass
    def _vcs_cleanup(self):
        """
        Remove any cruft that _vcs_init() created outside of the
        versioned tree.
        """
        pass
    def _vcs_get_user_id(self):
        """
        Get the VCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the VCS has not been configured with a username, return None.
        """
        return None
    def _vcs_set_user_id(self, value):
        """
        Set the VCS's suggested user id (e.g "John Doe <jdoe@example.com>").
        This is run if the VCS has not been configured with a usename, so
        that commits will have a reasonable FROM value.
        """
        raise SettingIDnotSupported
    def _vcs_add(self, path):
        """
        Add the already created file at path to version control.
        """
        pass
    def _vcs_remove(self, path):
        """
        Remove the file at path from version control.  Optionally
        remove the file from the filesystem as well.
        """
        pass
    def _vcs_update(self, path):
        """
        Notify the versioning system of changes to the versioned file
        at path.
        """
        pass
    def _vcs_get_file_contents(self, path, revision=None, binary=False):
        """
        Get the file contents as they were in a given revision.
        Revision==None specifies the current revision.
        """
        assert revision == None, \
            "The %s VCS does not support revision specifiers" % self.name
        if binary == False:
            f = codecs.open(os.path.join(self.rootdir, path), "r", self.encoding)
        else:
            f = open(os.path.join(self.rootdir, path), "rb")
        contents = f.read()
        f.close()
        return contents
    def _vcs_duplicate_repo(self, directory, revision=None):
        """
        Get the repository as it was in a given revision.
        revision==None specifies the current revision.
        dir specifies a directory to create the duplicate in.
        """
        shutil.copytree(self.rootdir, directory, True)
    def _vcs_commit(self, commitfile, allow_empty=False):
        """
        Commit the current working directory, using the contents of
        commitfile as the comment.  Return the name of the old
        revision (or None if commits are not supported).
        
        If allow_empty == False, raise EmptyCommit if there are no
        changes to commit.
        """
        return None
    def _vcs_revision_id(self, index):
        """
        Return the name of the <index>th revision.  Index will be an
        integer (possibly <= 0).  The choice of which branch to follow
        when crossing branches/merges is not defined.

        Return None if revision IDs are not supported, or if the
        specified revision does not exist.
        """
        return None
    def _get_version(self):
        try:
            ret = self._vcs_version()
            return ret
        except OSError, e:
            if e.errno == errno.ENOENT:
                return None
            else:
                raise OSError, e
        except CommandError:
            return None
    def installed(self):
        if self.version != None:
            return True
        return False
    def detect(self, path="."):
        """
        Detect whether a directory is revision controlled with this VCS.
        """
        return self._vcs_detect(path)
    def root(self, path):
        """
        Set the root directory to the path's VCS root.  This is the
        default working directory for future invocations.
        """
        self.rootdir = self._vcs_root(path)
    def init(self, path):
        """
        Begin versioning the tree based at path.
        Also roots the vcs at path.
        """
        if os.path.isdir(path)==False:
            path = os.path.dirname(path)
        self._vcs_init(path)
        self.root(path)
    def cleanup(self):
        self._vcs_cleanup()
    def get_user_id(self):
        """
        Get the VCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the VCS has not been configured with a username, return the user's
        id.  You can override the automatic lookup procedure by setting the
        VCS.user_id attribute to a string of your choice.
        """
        if hasattr(self, "user_id"):
            if self.user_id != None:
                return self.user_id
        id = self._vcs_get_user_id()
        if id == None:
            name = self._u_get_fallback_username()
            email = self._u_get_fallback_email()
            id = self._u_create_id(name, email)
            print >> sys.stderr, "Guessing id '%s'" % id
            try:
                self.set_user_id(id)
            except SettingIDnotSupported:
                pass
        return id
    def set_user_id(self, value):
        """
        Set the VCS's suggested user id (e.g "John Doe <jdoe@example.com>").
        This is run if the VCS has not been configured with a usename, so
        that commits will have a reasonable FROM value.
        """
        self._vcs_set_user_id(value)
    def add(self, path):
        """
        Add the already created file at path to version control.
        """
        self._vcs_add(self._u_rel_path(path))
    def remove(self, path):
        """
        Remove a file from both version control and the filesystem.
        """
        self._vcs_remove(self._u_rel_path(path))
        if os.path.exists(path):
            os.remove(path)
    def recursive_remove(self, dirname):
        """
        Remove a file/directory and all its decendents from both
        version control and the filesystem.
        """
        if not os.path.exists(dirname):
            raise NoSuchFile(dirname)
        for dirpath,dirnames,filenames in os.walk(dirname, topdown=False):
            filenames.extend(dirnames)
            for path in filenames:
                fullpath = os.path.join(dirpath, path)
                if os.path.exists(fullpath) == False:
                    continue
                self._vcs_remove(self._u_rel_path(fullpath))
        if os.path.exists(dirname):
            shutil.rmtree(dirname)
    def update(self, path):
        """
        Notify the versioning system of changes to the versioned file
        at path.
        """
        self._vcs_update(self._u_rel_path(path))
    def get_file_contents(self, path, revision=None, allow_no_vcs=False, binary=False):
        """
        Get the file as it was in a given revision.
        Revision==None specifies the current revision.

        allow_no_vcs==True allows direct access to files through
        codecs.open() or open() if the vcs decides it can't handle the
        given path.
        """
        if not os.path.exists(path):
            raise NoSuchFile(path)
        if self._use_vcs(path, allow_no_vcs):
            relpath = self._u_rel_path(path)
            contents = self._vcs_get_file_contents(relpath,revision,binary=binary)
        else:
            if binary == True:
                f = codecs.open(path, "r", self.encoding)
            else:
                f = open(path, "rb")
            contents = f.read()
            f.close()
        return contents
    def set_file_contents(self, path, contents, allow_no_vcs=False, binary=False):
        """
        Set the file contents under version control.
        """
        add = not os.path.exists(path)
        if binary == False:
            f = codecs.open(path, "w", self.encoding)
        else:
            f = open(path, "wb")
        f.write(contents)
        f.close()
        
        if self._use_vcs(path, allow_no_vcs):
            if add:
                self.add(path)
            else:
                self.update(path)
    def mkdir(self, path, allow_no_vcs=False, check_parents=True):
        """
        Create (if neccessary) a directory at path under version
        control.
        """
        if check_parents == True:
            parent = os.path.dirname(path)
            if not os.path.exists(parent): # recurse through parents
                self.mkdir(parent, allow_no_vcs, check_parents)
        if not os.path.exists(path):
            os.mkdir(path)
            if self._use_vcs(path, allow_no_vcs):
                self.add(path)
        else:
            assert os.path.isdir(path)
            if self._use_vcs(path, allow_no_vcs):
                #self.update(path)# Don't update directories.  Changing files
                pass              # underneath them should be sufficient.
                
    def duplicate_repo(self, revision=None):
        """
        Get the repository as it was in a given revision.
        revision==None specifies the current revision.
        Return the path to the arbitrary directory at the base of the new repo.
        """
        # Dirname in Basedir to protect against simlink attacks.
        if self._duplicateBasedir == None:
            self._duplicateBasedir = tempfile.mkdtemp(prefix='BEvcs')
            self._duplicateDirname = \
                os.path.join(self._duplicateBasedir, "duplicate")
            self._vcs_duplicate_repo(directory=self._duplicateDirname,
                                     revision=revision)
        return self._duplicateDirname
    def remove_duplicate_repo(self):
        """
        Clean up a duplicate repo created with duplicate_repo().
        """
        if self._duplicateBasedir != None:
            shutil.rmtree(self._duplicateBasedir)
            self._duplicateBasedir = None
            self._duplicateDirname = None
    def commit(self, summary, body=None, allow_empty=False):
        """
        Commit the current working directory, with a commit message
        string summary and body.  Return the name of the old revision
        (or None if versioning is not supported).
        
        If allow_empty == False (the default), raise EmptyCommit if
        there are no changes to commit.
        """
        summary = summary.strip()+'\n'
        if body is not None:
            summary += '\n' + body.strip() + '\n'
        descriptor, filename = tempfile.mkstemp()
        revision = None
        try:
            temp_file = os.fdopen(descriptor, 'wb')
            temp_file.write(summary)
            temp_file.flush()
            self.precommit()
            revision = self._vcs_commit(filename, allow_empty=allow_empty)
            temp_file.close()
            self.postcommit()
        finally:
            os.remove(filename)
        return revision
    def precommit(self):
        """
        Executed before all attempted commits.
        """
        pass
    def postcommit(self):
        """
        Only executed after successful commits.
        """
        pass
    def revision_id(self, index=None):
        """
        Return the name of the <index>th revision.  The choice of
        which branch to follow when crossing branches/merges is not
        defined.

        Return None if index==None, revision IDs are not supported, or
        if the specified revision does not exist.
        """
        if index == None:
            return None
        return self._vcs_revision_id(index)
    def _u_any_in_string(self, list, string):
        """
        Return True if any of the strings in list are in string.
        Otherwise return False.
        """
        for list_string in list:
            if list_string in string:
                return True
        return False
    def _u_invoke(self, *args, **kwargs):
        if 'cwd' not in kwargs:
            kwargs['cwd'] = self.rootdir
        if 'verbose' not in kwargs:
            kwargs['verbose'] = self.verboseInvoke
        if 'encoding' not in kwargs:
            kwargs['encoding'] = self.encoding
        return invoke(*args, **kwargs)
    def _u_invoke_client(self, *args, **kwargs):
        cl_args = [self.client]
        cl_args.extend(args)
        return self._u_invoke(cl_args, **kwargs)
    def _u_search_parent_directories(self, path, filename):
        """
        Find the file (or directory) named filename in path or in any
        of path's parents.
        
        e.g.
          search_parent_directories("/a/b/c", ".be")
        will return the path to the first existing file from
          /a/b/c/.be
          /a/b/.be
          /a/.be
          /.be
        or None if none of those files exist.
        """
        return search_parent_directories(path, filename)
    def _use_vcs(self, path, allow_no_vcs):
        """
        Try and decide if _vcs_add/update/mkdir/etc calls will
        succeed.  Returns True is we think the vcs_call would
        succeeed, and False otherwise.
        """
        use_vcs = True
        exception = None
        if self.rootdir != None:
            if self.path_in_root(path) == False:
                use_vcs = False
                exception = PathNotInRoot(path, self.rootdir)
        else:
            use_vcs = False
            exception = VCSnotRooted
        if use_vcs == False and allow_no_vcs==False:
            raise exception
        return use_vcs
    def path_in_root(self, path, root=None):
        """
        Return the relative path to path from root.
        >>> vcs = new()
        >>> vcs.path_in_root("/a.b/c/.be", "/a.b/c")
        True
        >>> vcs.path_in_root("/a.b/.be", "/a.b/c")
        False
        """
        if root == None:
            if self.rootdir == None:
                raise VCSnotRooted
            root = self.rootdir
        path = os.path.abspath(path)
        absRoot = os.path.abspath(root)
        absRootSlashedDir = os.path.join(absRoot,"")
        if not path.startswith(absRootSlashedDir):
            return False
        return True
    def _u_rel_path(self, path, root=None):
        """
        Return the relative path to path from root.
        >>> vcs = new()
        >>> vcs._u_rel_path("/a.b/c/.be", "/a.b/c")
        '.be'
        """
        if root == None:
            if self.rootdir == None:
                raise VCSnotRooted
            root = self.rootdir
        path = os.path.abspath(path)
        absRoot = os.path.abspath(root)
        absRootSlashedDir = os.path.join(absRoot,"")
        if not path.startswith(absRootSlashedDir):
            raise PathNotInRoot(path, absRootSlashedDir)
        assert path != absRootSlashedDir, \
            "file %s == root directory %s" % (path, absRootSlashedDir)
        relpath = path[len(absRootSlashedDir):]
        return relpath
    def _u_abspath(self, path, root=None):
        """
        Return the absolute path from a path realtive to root.
        >>> vcs = new()
        >>> vcs._u_abspath(".be", "/a.b/c")
        '/a.b/c/.be'
        """
        if root == None:
            assert self.rootdir != None, "VCS not rooted"
            root = self.rootdir
        return os.path.abspath(os.path.join(root, path))
    def _u_create_id(self, name, email=None):
        """
        >>> vcs = new()
        >>> vcs._u_create_id("John Doe", "jdoe@example.com")
        'John Doe <jdoe@example.com>'
        >>> vcs._u_create_id("John Doe")
        'John Doe'
        """
        assert len(name) > 0
        if email == None or len(email) == 0:
            return name
        else:
            return "%s <%s>" % (name, email)
    def _u_parse_id(self, value):
        """
        >>> vcs = new()
        >>> vcs._u_parse_id("John Doe <jdoe@example.com>")
        ('John Doe', 'jdoe@example.com')
        >>> vcs._u_parse_id("John Doe")
        ('John Doe', None)
        >>> try:
        ...     vcs._u_parse_id("John Doe <jdoe@example.com><what?>")
        ... except AssertionError:
        ...     print "Invalid match"
        Invalid match
        """
        emailexp = re.compile("(.*) <([^>]*)>(.*)")
        match = emailexp.search(value)
        if match == None:
            email = None
            name = value
        else:
            assert len(match.groups()) == 3
            assert match.groups()[2] == "", match.groups()
            email = match.groups()[1]
            name = match.groups()[0]
        assert name != None
        assert len(name) > 0
        return (name, email)
    def _u_get_fallback_username(self):
        name = None
        for envariable in ["LOGNAME", "USERNAME"]:
            if os.environ.has_key(envariable):
                name = os.environ[envariable]
                break
        assert name != None
        return name
    def _u_get_fallback_email(self):
        hostname = gethostname()
        name = self._u_get_fallback_username()
        return "%s@%s" % (name, hostname)
    def _u_parse_commitfile(self, commitfile):
        """
        Split the commitfile created in self.commit() back into
        summary and header lines.
        """
        f = codecs.open(commitfile, "r", self.encoding)
        summary = f.readline()
        body = f.read()
        body.lstrip('\n')
        if len(body) == 0:
            body = None
        f.close()
        return (summary, body)
        

if libbe.TESTING == True:
    def setup_vcs_test_fixtures(testcase):
        """Set up test fixtures for VCS test case."""
        testcase.vcs = testcase.Class()
        testcase.dir = Dir()
        testcase.dirname = testcase.dir.path

        vcs_not_supporting_uninitialized_user_id = []
        vcs_not_supporting_set_user_id = ["None", "hg"]
        testcase.vcs_supports_uninitialized_user_id = (
            testcase.vcs.name not in vcs_not_supporting_uninitialized_user_id)
        testcase.vcs_supports_set_user_id = (
            testcase.vcs.name not in vcs_not_supporting_set_user_id)

        if not testcase.vcs.installed():
            testcase.fail(
                "%(name)s VCS not found" % vars(testcase.Class))

        if testcase.Class.name != "None":
            testcase.failIf(
                testcase.vcs.detect(testcase.dirname),
                "Detected %(name)s VCS before initialising"
                    % vars(testcase.Class))

        testcase.vcs.init(testcase.dirname)

    class VCSTestCase(unittest.TestCase):
        """Test cases for base VCS class."""

        Class = VCS

        def __init__(self, *args, **kwargs):
            super(VCSTestCase, self).__init__(*args, **kwargs)
            self.dirname = None

        def setUp(self):
            super(VCSTestCase, self).setUp()
            setup_vcs_test_fixtures(self)

        def tearDown(self):
            self.vcs.cleanup()
            self.dir.cleanup()
            super(VCSTestCase, self).tearDown()

        def full_path(self, rel_path):
            return os.path.join(self.dirname, rel_path)


    class VCS_init_TestCase(VCSTestCase):
        """Test cases for VCS.init method."""

        def test_detect_should_succeed_after_init(self):
            """Should detect VCS in directory after initialization."""
            self.failUnless(
                self.vcs.detect(self.dirname),
                "Did not detect %(name)s VCS after initialising"
                    % vars(self.Class))

        def test_vcs_rootdir_in_specified_root_path(self):
            """VCS root directory should be in specified root path."""
            rp = os.path.realpath(self.vcs.rootdir)
            dp = os.path.realpath(self.dirname)
            vcs_name = self.Class.name
            self.failUnless(
                dp == rp or rp == None,
                "%(vcs_name)s VCS root in wrong dir (%(dp)s %(rp)s)" % vars())


    class VCS_get_user_id_TestCase(VCSTestCase):
        """Test cases for VCS.get_user_id method."""

        def test_gets_existing_user_id(self):
            """Should get the existing user ID."""
            if not self.vcs_supports_uninitialized_user_id:
                return

            user_id = self.vcs.get_user_id()
            self.failUnless(
                user_id is not None,
                "unable to get a user id")


    class VCS_set_user_id_TestCase(VCSTestCase):
        """Test cases for VCS.set_user_id method."""

        def setUp(self):
            super(VCS_set_user_id_TestCase, self).setUp()

            if self.vcs_supports_uninitialized_user_id:
                self.prev_user_id = self.vcs.get_user_id()
            else:
                self.prev_user_id = "Uninitialized identity <bogus@example.org>"

            if self.vcs_supports_set_user_id:
                self.test_new_user_id = "John Doe <jdoe@example.com>"
                self.vcs.set_user_id(self.test_new_user_id)

        def tearDown(self):
            if self.vcs_supports_set_user_id:
                self.vcs.set_user_id(self.prev_user_id)
            super(VCS_set_user_id_TestCase, self).tearDown()

        def test_raises_error_in_unsupported_vcs(self):
            """Should raise an error in a VCS that doesn't support it."""
            if self.vcs_supports_set_user_id:
                return
            self.assertRaises(
                SettingIDnotSupported,
                self.vcs.set_user_id, "foo")

        def test_updates_user_id_in_supporting_vcs(self):
            """Should update the user ID in an VCS that supports it."""
            if not self.vcs_supports_set_user_id:
                return
            user_id = self.vcs.get_user_id()
            self.failUnlessEqual(
                self.test_new_user_id, user_id,
                "user id not set correctly (expected %s, got %s)"
                    % (self.test_new_user_id, user_id))


    def setup_vcs_revision_test_fixtures(testcase):
        """Set up revision test fixtures for VCS test case."""
        testcase.test_dirs = ['a', 'a/b', 'c']
        for path in testcase.test_dirs:
            testcase.vcs.mkdir(testcase.full_path(path))

        testcase.test_files = ['a/text', 'a/b/text']

        testcase.test_contents = {
            'rev_1': "Lorem ipsum",
            'uncommitted': "dolor sit amet",
            }


    class VCS_mkdir_TestCase(VCSTestCase):
        """Test cases for VCS.mkdir method."""

        def setUp(self):
            super(VCS_mkdir_TestCase, self).setUp()
            setup_vcs_revision_test_fixtures(self)

        def tearDown(self):
            for path in reversed(sorted(self.test_dirs)):
                self.vcs.recursive_remove(self.full_path(path))
            super(VCS_mkdir_TestCase, self).tearDown()

        def test_mkdir_creates_directory(self):
            """Should create specified directory in filesystem."""
            for path in self.test_dirs:
                full_path = self.full_path(path)
                self.failUnless(
                    os.path.exists(full_path),
                    "path %(full_path)s does not exist" % vars())


    class VCS_commit_TestCase(VCSTestCase):
        """Test cases for VCS.commit method."""

        def setUp(self):
            super(VCS_commit_TestCase, self).setUp()
            setup_vcs_revision_test_fixtures(self)

        def tearDown(self):
            for path in reversed(sorted(self.test_dirs)):
                self.vcs.recursive_remove(self.full_path(path))
            super(VCS_commit_TestCase, self).tearDown()

        def test_file_contents_as_specified(self):
            """Should set file contents as specified."""
            test_contents = self.test_contents['rev_1']
            for path in self.test_files:
                full_path = self.full_path(path)
                self.vcs.set_file_contents(full_path, test_contents)
                current_contents = self.vcs.get_file_contents(full_path)
                self.failUnlessEqual(test_contents, current_contents)

        def test_file_contents_as_committed(self):
            """Should have file contents as specified after commit."""
            test_contents = self.test_contents['rev_1']
            for path in self.test_files:
                full_path = self.full_path(path)
                self.vcs.set_file_contents(full_path, test_contents)
                revision = self.vcs.commit("Initial file contents.")
                current_contents = self.vcs.get_file_contents(full_path)
                self.failUnlessEqual(test_contents, current_contents)

        def test_file_contents_as_set_when_uncommitted(self):
            """Should set file contents as specified after commit."""
            if not self.vcs.versioned:
                return
            for path in self.test_files:
                full_path = self.full_path(path)
                self.vcs.set_file_contents(
                    full_path, self.test_contents['rev_1'])
                revision = self.vcs.commit("Initial file contents.")
                self.vcs.set_file_contents(
                    full_path, self.test_contents['uncommitted'])
                current_contents = self.vcs.get_file_contents(full_path)
                self.failUnlessEqual(
                    self.test_contents['uncommitted'], current_contents)

        def test_revision_file_contents_as_committed(self):
            """Should get file contents as committed to specified revision."""
            if not self.vcs.versioned:
                return
            for path in self.test_files:
                full_path = self.full_path(path)
                self.vcs.set_file_contents(
                    full_path, self.test_contents['rev_1'])
                revision = self.vcs.commit("Initial file contents.")
                self.vcs.set_file_contents(
                    full_path, self.test_contents['uncommitted'])
                committed_contents = self.vcs.get_file_contents(
                    full_path, revision)
                self.failUnlessEqual(
                    self.test_contents['rev_1'], committed_contents)

        def test_revision_id_as_committed(self):
            """Check for compatibility between .commit() and .revision_id()"""
            if not self.vcs.versioned:
                self.failUnlessEqual(self.vcs.revision_id(5), None)
                return
            committed_revisions = []
            for path in self.test_files:
                full_path = self.full_path(path)
                self.vcs.set_file_contents(
                    full_path, self.test_contents['rev_1'])
                revision = self.vcs.commit("Initial %s contents." % path)
                committed_revisions.append(revision)
                self.vcs.set_file_contents(
                    full_path, self.test_contents['uncommitted'])
                revision = self.vcs.commit("Altered %s contents." % path)
                committed_revisions.append(revision)
            for i,revision in enumerate(committed_revisions):
                self.failUnlessEqual(self.vcs.revision_id(i), revision)
                i += -len(committed_revisions) # check negative indices
                self.failUnlessEqual(self.vcs.revision_id(i), revision)
            i = len(committed_revisions)
            self.failUnlessEqual(self.vcs.revision_id(i), None)
            self.failUnlessEqual(self.vcs.revision_id(-i-1), None)

        def test_revision_id_as_committed(self):
            """Check revision id before first commit"""
            if not self.vcs.versioned:
                self.failUnlessEqual(self.vcs.revision_id(5), None)
                return
            committed_revisions = []
            for path in self.test_files:
                self.failUnlessEqual(self.vcs.revision_id(0), None)


    class VCS_duplicate_repo_TestCase(VCSTestCase):
        """Test cases for VCS.duplicate_repo method."""

        def setUp(self):
            super(VCS_duplicate_repo_TestCase, self).setUp()
            setup_vcs_revision_test_fixtures(self)

        def tearDown(self):
            self.vcs.remove_duplicate_repo()
            for path in reversed(sorted(self.test_dirs)):
                self.vcs.recursive_remove(self.full_path(path))
            super(VCS_duplicate_repo_TestCase, self).tearDown()

        def test_revision_file_contents_as_committed(self):
            """Should match file contents as committed to specified revision.
            """
            if not self.vcs.versioned:
                return
            for path in self.test_files:
                full_path = self.full_path(path)
                self.vcs.set_file_contents(
                    full_path, self.test_contents['rev_1'])
                revision = self.vcs.commit("Commit current status")
                self.vcs.set_file_contents(
                    full_path, self.test_contents['uncommitted'])
                dup_repo_path = self.vcs.duplicate_repo(revision)
                dup_file_path = os.path.join(dup_repo_path, path)
                dup_file_contents = file(dup_file_path, 'rb').read()
                self.failUnlessEqual(
                    self.test_contents['rev_1'], dup_file_contents)
                self.vcs.remove_duplicate_repo()


    def make_vcs_testcase_subclasses(vcs_class, namespace):
        """Make VCSTestCase subclasses for vcs_class in the namespace."""
        vcs_testcase_classes = [
            c for c in (
                ob for ob in globals().values() if isinstance(ob, type))
            if issubclass(c, VCSTestCase)]

        for base_class in vcs_testcase_classes:
            testcase_class_name = vcs_class.__name__ + base_class.__name__
            testcase_class_bases = (base_class,)
            testcase_class_dict = dict(base_class.__dict__)
            testcase_class_dict['Class'] = vcs_class
            testcase_class = type(
                testcase_class_name, testcase_class_bases, testcase_class_dict)
            setattr(namespace, testcase_class_name, testcase_class)


    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
