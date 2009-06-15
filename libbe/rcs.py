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
from subprocess import Popen, PIPE
import os
import os.path
from socket import gethostname
import re
import sys
import tempfile
import shutil
import unittest
import doctest

from utility import Dir, search_parent_directories


def _get_matching_rcs(matchfn):
    """Return the first module for which matchfn(RCS_instance) is true"""
    import arch
    import bzr
    import hg
    import git
    for module in [arch, bzr, hg, git]:
        rcs = module.new()
        if matchfn(rcs) == True:
            return rcs
        else:
            del(rcs)
    return RCS()
    
def rcs_by_name(rcs_name):
    """Return the module for the RCS with the given name"""
    return _get_matching_rcs(lambda rcs: rcs.name == rcs_name)

def detect_rcs(dir):
    """Return an RCS instance for the rcs being used in this directory"""
    return _get_matching_rcs(lambda rcs: rcs.detect(dir))

def installed_rcs():
    """Return an instance of an installed RCS"""
    return _get_matching_rcs(lambda rcs: rcs.installed())


class CommandError(Exception):
    def __init__(self, err_str, status):
        Exception.__init__(self, "Command failed (%d): %s" % (status, err_str))
        self.err_str = err_str
        self.status = status

class SettingIDnotSupported(NotImplementedError):
    pass

class RCSnotRooted(Exception):
    def __init__(self):
        msg = "RCS not rooted"
        Exception.__init__(self, msg)

class PathNotInRoot(Exception):
    def __init__(self, path, root):
        msg = "Path '%s' not in root '%s'" % (path, root)
        Exception.__init__(self, msg)
        self.path = path
        self.root = root

class NoSuchFile(Exception):
    def __init__(self, pathname):
        Exception.__init__(self, "No such file: %s" % pathname)


def new():
    return RCS()

class RCS(object):
    """
    This class implements a 'no-rcs' interface.

    Support for other RCSs can be added by subclassing this class, and
    overriding methods _rcs_*() with code appropriate for your RCS.
    
    The methods _u_*() are utility methods available to the _rcs_*()
    methods.
    """
    name = "None"
    client = "" # command-line tool for _u_invoke_client
    versioned = False
    def __init__(self, paranoid=False):
        self.paranoid = paranoid
        self.verboseInvoke = False
        self.rootdir = None
        self._duplicateBasedir = None
        self._duplicateDirname = None
    def __del__(self):
        self.cleanup()

    def _rcs_help(self):
        """
        Return the command help string.
        (Allows a simple test to see if the client is installed.)
        """
        pass
    def _rcs_detect(self, path=None):
        """
        Detect whether a directory is revision controlled with this RCS.
        """
        return True
    def _rcs_root(self, path):
        """
        Get the RCS root.  This is the default working directory for
        future invocations.  You would normally set this to the root
        directory for your RCS.
        """
        if os.path.isdir(path)==False:
            path = os.path.dirname(path)
            if path == "":
                path = os.path.abspath(".")
        return path
    def _rcs_init(self, path):
        """
        Begin versioning the tree based at path.
        """
        pass
    def _rcs_cleanup(self):
        """
        Remove any cruft that _rcs_init() created outside of the
        versioned tree.
        """
        pass
    def _rcs_get_user_id(self):
        """
        Get the RCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the RCS has not been configured with a username, return None.
        """
        return None
    def _rcs_set_user_id(self, value):
        """
        Set the RCS's suggested user id (e.g "John Doe <jdoe@example.com>").
        This is run if the RCS has not been configured with a usename, so
        that commits will have a reasonable FROM value.
        """
        raise SettingIDnotSupported
    def _rcs_add(self, path):
        """
        Add the already created file at path to version control.
        """
        pass
    def _rcs_remove(self, path):
        """
        Remove the file at path from version control.  Optionally
        remove the file from the filesystem as well.
        """
        pass
    def _rcs_update(self, path):
        """
        Notify the versioning system of changes to the versioned file
        at path.
        """
        pass
    def _rcs_get_file_contents(self, path, revision=None):
        """
        Get the file contents as they were in a given revision.  Don't
        worry about decoding the contents, the RCS.get_file_contents()
        method will handle that.
        
        Revision==None specifies the current revision.
        """
        assert revision == None, \
            "The %s RCS does not support revision specifiers" % self.name
        return file(os.path.join(self.rootdir, path), "rb").read()
    def _rcs_duplicate_repo(self, directory, revision=None):
        """
        Get the repository as it was in a given revision.
        revision==None specifies the current revision.
        dir specifies a directory to create the duplicate in.
        """
        shutil.copytree(self.rootdir, directory, True)
    def _rcs_commit(self, commitfile):
        """
        Commit the current working directory, using the contents of
        commitfile as the comment.  Return the name of the old
        revision.
        """
        return None
    def installed(self):
        try:
            self._rcs_help()
            return True
        except OSError, e:
            if e.errno == errno.ENOENT:
                return False
            raise e
    def detect(self, path="."):
        """
        Detect whether a directory is revision controlled with this RCS.
        """
        return self._rcs_detect(path)
    def root(self, path):
        """
        Set the root directory to the path's RCS root.  This is the
        default working directory for future invocations.
        """
        self.rootdir = self._rcs_root(path)
    def init(self, path):
        """
        Begin versioning the tree based at path.
        Also roots the rcs at path.
        """
        if os.path.isdir(path)==False:
            path = os.path.dirname(path)
        self._rcs_init(path)
        self.root(path)
    def cleanup(self):
        self._rcs_cleanup()
    def get_user_id(self):
        """
        Get the RCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the RCS has not been configured with a username, return the user's
        id.  You can override the automatic lookup procedure by setting the
        RCS.user_id attribute to a string of your choice.
        """
        if hasattr(self, "user_id"):
            if self.user_id != None:
                return self.user_id
        id = self._rcs_get_user_id()
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
        Set the RCS's suggested user id (e.g "John Doe <jdoe@example.com>").
        This is run if the RCS has not been configured with a usename, so
        that commits will have a reasonable FROM value.
        """
        self._rcs_set_user_id(value)
    def add(self, path):
        """
        Add the already created file at path to version control.
        """
        self._rcs_add(self._u_rel_path(path))
    def remove(self, path):
        """
        Remove a file from both version control and the filesystem.
        """
        self._rcs_remove(self._u_rel_path(path))
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
                self._rcs_remove(self._u_rel_path(fullpath))
        if os.path.exists(dirname):
            shutil.rmtree(dirname)
    def update(self, path):
        """
        Notify the versioning system of changes to the versioned file
        at path.
        """
        self._rcs_update(self._u_rel_path(path))
    def get_file_contents(self, path, revision=None, allow_no_rcs=False):
        """
        Get the file as it was in a given revision.
        Revision==None specifies the current revision.
        """
        if not os.path.exists(path):
            raise NoSuchFile(path)
        if self._use_rcs(path, allow_no_rcs):
            relpath = self._u_rel_path(path)
            contents = self._rcs_get_file_contents(relpath,revision)
        else:
            contents = file(path, "rb").read()
        return contents.decode("utf-8")
    def set_file_contents(self, path, contents, allow_no_rcs=False):
        """
        Set the file contents under version control.
        """
        add = not os.path.exists(path)
        file(path, "wb").write(contents.encode("utf-8"))
        
        if self._use_rcs(path, allow_no_rcs):
            if add:
                self.add(path)
            else:
                self.update(path)
    def mkdir(self, path, allow_no_rcs=False):
        """
        Create (if neccessary) a directory at path under version
        control.
        """
        if not os.path.exists(path):
            os.mkdir(path)
            if self._use_rcs(path, allow_no_rcs):
                self.add(path)
        else:
            assert os.path.isdir(path)
            if self._use_rcs(path, allow_no_rcs):
                self.update(path)
    def duplicate_repo(self, revision=None):
        """
        Get the repository as it was in a given revision.
        revision==None specifies the current revision.
        Return the path to the arbitrary directory at the base of the new repo.
        """
        # Dirname in Baseir to protect against simlink attacks.
        if self._duplicateBasedir == None:
            self._duplicateBasedir = tempfile.mkdtemp(prefix='BErcs')
            self._duplicateDirname = \
                os.path.join(self._duplicateBasedir, "duplicate")
            self._rcs_duplicate_repo(directory=self._duplicateDirname,
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
    def commit(self, summary, body=None):
        """
        Commit the current working directory, with a commit message
        string summary and body.  Return the name of the old revision
        (or None if versioning is not supported).
        """
        if body is not None:
            summary += '\n' + body
        descriptor, filename = tempfile.mkstemp()
        revision = None
        try:
            temp_file = os.fdopen(descriptor, 'wb')
            temp_file.write(summary)
            temp_file.flush()
            revision = self._rcs_commit(filename)
            temp_file.close()
        finally:
            os.remove(filename)
        return revision
    def precommit(self, directory):
        pass
    def postcommit(self, directory):
        pass
    def _u_invoke(self, args, expect=(0,), cwd=None):
        if cwd == None:
            cwd = self.rootdir
        if self.verboseInvoke == True:
            print >> sys.stderr, "%s$ %s" % (cwd, " ".join(args))
        try :
            if sys.platform != "win32":
                q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=cwd)
            else:
                # win32 don't have os.execvp() so have to run command in a shell
                q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, 
                          shell=True, cwd=cwd)
        except OSError, e :
            strerror = "%s\nwhile executing %s" % (e.args[1], args)
            raise CommandError(strerror, e.args[0])
        output, error = q.communicate()
        status = q.wait()
        if self.verboseInvoke == True:
            print >> sys.stderr, "%d\n%s%s" % (status, output, error)
        if status not in expect:
            strerror = "%s\nwhile executing %s\n%s" % (args[1], args, error)
            raise CommandError(strerror, status)
        return status, output, error
    def _u_invoke_client(self, *args, **kwargs):
        directory = kwargs.get('directory',None)
        expect = kwargs.get('expect', (0,))
        cl_args = [self.client]
        cl_args.extend(args)
        return self._u_invoke(cl_args, expect, cwd=directory)
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
    def _use_rcs(self, path, allow_no_rcs):
        """
        Try and decide if _rcs_add/update/mkdir/etc calls will
        succeed.  Returns True is we think the rcs_call would
        succeeed, and False otherwise.
        """
        use_rcs = True
        exception = None
        if self.rootdir != None:
            if self.path_in_root(path) == False:
                use_rcs = False
                exception = PathNotInRoot(path, self.rootdir)
        else:
            use_rcs = False
            exception = RCSnotRooted
        if use_rcs == False and allow_no_rcs==False:
            raise exception
        return use_rcs
    def path_in_root(self, path, root=None):
        """
        Return the relative path to path from root.
        >>> rcs = new()
        >>> rcs.path_in_root("/a.b/c/.be", "/a.b/c")
        True
        >>> rcs.path_in_root("/a.b/.be", "/a.b/c")
        False
        """
        if root == None:
            if self.rootdir == None:
                raise RCSnotRooted
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
        >>> rcs = new()
        >>> rcs._u_rel_path("/a.b/c/.be", "/a.b/c")
        '.be'
        """
        if root == None:
            if self.rootdir == None:
                raise RCSnotRooted
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
        >>> rcs = new()
        >>> rcs._u_abspath(".be", "/a.b/c")
        '/a.b/c/.be'
        """
        if root == None:
            assert self.rootdir != None, "RCS not rooted"
            root = self.rootdir
        return os.path.abspath(os.path.join(root, path))
    def _u_create_id(self, name, email=None):
        """
        >>> rcs = new()
        >>> rcs._u_create_id("John Doe", "jdoe@example.com")
        'John Doe <jdoe@example.com>'
        >>> rcs._u_create_id("John Doe")
        'John Doe'
        """
        assert len(name) > 0
        if email == None or len(email) == 0:
            return name
        else:
            return "%s <%s>" % (name, email)
    def _u_parse_id(self, value):
        """
        >>> rcs = new()
        >>> rcs._u_parse_id("John Doe <jdoe@example.com>")
        ('John Doe', 'jdoe@example.com')
        >>> rcs._u_parse_id("John Doe")
        ('John Doe', None)
        >>> try:
        ...     rcs._u_parse_id("John Doe <jdoe@example.com><what?>")
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
        f = file(commitfile, "rb")
        summary = f.readline()
        body = f.read()
        body.lstrip('\n')
        if len(body) == 0:
            body = None
        f.close
        return (summary, body)
        

def setup_rcs_test_fixtures(testcase):
    """
    Set up test fixtures for RCS test case.
    """
    testcase.rcs = testcase.Class()
    testcase.dir = Dir()
    testcase.dirname = testcase.dir.path

    testcase.rcs_supports_uninitialized_user_id = (
        testcase.rcs.name not in ["git"])
    testcase.rcs_supports_set_user_id = (
        testcase.rcs.name not in ["None", "hg"])

    if not testcase.rcs.installed():
        testcase.fail(
            "%(name)s RCS not found" % vars(testcase.Class))

    if testcase.Class.name != "None":
        testcase.failIf(
            testcase.rcs.detect(testcase.dirname),
            "Detected %(name)s RCS before initialising"
                % vars(testcase.Class))

    testcase.rcs.init(testcase.dirname)


class RCSTestCase(unittest.TestCase):
    """
    Test cases for base RCS class.
    """

    Class = RCS

    def __init__(self, *args, **kwargs):
        super(RCSTestCase, self).__init__(*args, **kwargs)
        self.dirname = None

    def setUp(self):
        super(RCSTestCase, self).setUp()
        setup_rcs_test_fixtures(self)

    def tearDown(self):
        del(self.rcs)
        super(RCSTestCase, self).tearDown()

    def full_path(self, rel_path):
        return os.path.join(self.dirname, rel_path)


class RCS_init_TestCase(RCSTestCase):
    """
    Test cases for RCS.init method.
    """

    def test_detect_should_succeed_after_init(self):
        """
        Should detect RCS in directory after initialization.
        """
        self.failUnless(
            self.rcs.detect(self.dirname),
            "Did not detect %(name)s RCS after initialising"
                % vars(self.Class))

    def test_rcs_rootdir_in_specified_root_path(self):
        """
        RCS root directory should be in specified root path.
        """
        rp = os.path.realpath(self.rcs.rootdir)
        dp = os.path.realpath(self.dirname)
        rcs_name = self.Class.name
        self.failUnless(
            dp == rp or rp == None,
            "%(rcs_name)s RCS root in wrong dir (%(dp)s %(rp)s)" % vars())


class RCS_get_user_id_TestCase(RCSTestCase):
    """
    Test cases for RCS.get_user_id method.
    """

    def test_gets_existing_user_id(self):
        """
        Should get the existing user ID.
        """
        if not self.rcs_supports_uninitialized_user_id:
            return

        user_id = self.rcs.get_user_id()
        self.failUnless(
            user_id is not None,
            "unable to get a user id")


class RCS_set_user_id_TestCase(RCSTestCase):
    """
    Test cases for RCS.set_user_id method.
    """

    def setUp(self):
        super(RCS_set_user_id_TestCase, self).setUp()

        if self.rcs_supports_uninitialized_user_id:
            self.prev_user_id = self.rcs.get_user_id()
        else:
            self.prev_user_id = "Uninitialized identity <bogus@example.org>"

        if self.rcs_supports_set_user_id:
            self.test_new_user_id = "John Doe <jdoe@example.com>"
            self.rcs.set_user_id(self.test_new_user_id)

    def tearDown(self):
        if self.rcs_supports_set_user_id:
            self.rcs.set_user_id(self.prev_user_id)
        super(RCS_set_user_id_TestCase, self).tearDown()

    def test_raises_error_in_unsupported_vcs(self):
        """
        Should raise an error in a VCS that doesn't support it.
        """
        if self.rcs_supports_set_user_id:
            return
        self.assertRaises(
            SettingIDnotSupported,
            self.rcs.set_user_id, "foo")

    def test_updates_user_id_in_supporting_rcs(self):
        """
        Should update the user ID in an RCS that supports it.
        """
        if not self.rcs_supports_set_user_id:
            return
        user_id = self.rcs.get_user_id()
        self.failUnlessEqual(
            self.test_new_user_id, user_id,
            "user id not set correctly (expected %s, got %s)"
                % (self.test_new_user_id, user_id))


def setup_rcs_revision_test_fixtures(testcase):
    """
    Set up revision test fixtures for RCS test case.
    """
    testcase.test_dirs = ['a', 'a/b', 'c']
    for path in testcase.test_dirs:
        testcase.rcs.mkdir(testcase.full_path(path))

    testcase.test_files = ['a/text', 'a/b/text']

    testcase.test_contents = {
        'rev_1': "Lorem ipsum",
        'uncommitted': "dolor sit amet",
        }


class RCS_mkdir_TestCase(RCSTestCase):
    """
    Test cases for RCS.mkdir method.
    """

    def setUp(self):
        super(RCS_mkdir_TestCase, self).setUp()
        setup_rcs_revision_test_fixtures(self)

    def tearDown(self):
        for path in reversed(sorted(self.test_dirs)):
            self.rcs.recursive_remove(self.full_path(path))
        super(RCS_mkdir_TestCase, self).tearDown()

    def test_mkdir_creates_directory(self):
        """
        Should create specified directory in filesystem.
        """
        for path in self.test_dirs:
            full_path = self.full_path(path)
            self.failUnless(
                os.path.exists(full_path),
                "path %(full_path)s does not exist" % vars())


class RCS_commit_TestCase(RCSTestCase):
    """
    Test cases for RCS.commit method.
    """

    def setUp(self):
        super(RCS_commit_TestCase, self).setUp()
        setup_rcs_revision_test_fixtures(self)

    def tearDown(self):
        for path in reversed(sorted(self.test_dirs)):
            self.rcs.recursive_remove(self.full_path(path))
        super(RCS_commit_TestCase, self).tearDown()

    def test_file_contents_as_specified(self):
        """
        Should set file contents as specified.
        """
        test_contents = self.test_contents['rev_1']
        for path in self.test_files:
            full_path = self.full_path(path)
            self.rcs.set_file_contents(full_path, test_contents)
            current_contents = self.rcs.get_file_contents(full_path)
            self.failUnlessEqual(test_contents, current_contents)

    def test_file_contents_as_committed(self):
        """
        Should have file contents as specified after commit.
        """
        test_contents = self.test_contents['rev_1']
        for path in self.test_files:
            full_path = self.full_path(path)
            self.rcs.set_file_contents(full_path, test_contents)
            revision = self.rcs.commit("Initial file contents.")
            current_contents = self.rcs.get_file_contents(full_path)
            self.failUnlessEqual(test_contents, current_contents)

    def test_file_contents_as_set_when_uncommitted(self):
        """
        Should set file contents as specified after commit.
        """
        if not self.rcs.versioned:
            return
        for path in self.test_files:
            full_path = self.full_path(path)
            self.rcs.set_file_contents(
                full_path, self.test_contents['rev_1'])
            revision = self.rcs.commit("Initial file contents.")
            self.rcs.set_file_contents(
                full_path, self.test_contents['uncommitted'])
            current_contents = self.rcs.get_file_contents(full_path)
            self.failUnlessEqual(
                self.test_contents['uncommitted'], current_contents)

    def test_revision_file_contents_as_committed(self):
        """
        Should get file contents as committed to specified revision.
        """
        if not self.rcs.versioned:
            return
        for path in self.test_files:
            full_path = self.full_path(path)
            self.rcs.set_file_contents(
                full_path, self.test_contents['rev_1'])
            revision = self.rcs.commit("Initial file contents.")
            self.rcs.set_file_contents(
                full_path, self.test_contents['uncommitted'])
            committed_contents = self.rcs.get_file_contents(
                full_path, revision)
            self.failUnlessEqual(
                self.test_contents['rev_1'], committed_contents)


class RCS_duplicate_repo_TestCase(RCSTestCase):
    """
    Test cases for RCS.duplicate_repo method.
    """

    def setUp(self):
        super(RCS_duplicate_repo_TestCase, self).setUp()
        setup_rcs_revision_test_fixtures(self)

    def tearDown(self):
        self.rcs.remove_duplicate_repo()
        for path in reversed(sorted(self.test_dirs)):
            self.rcs.recursive_remove(self.full_path(path))
        super(RCS_duplicate_repo_TestCase, self).tearDown()

    def test_revision_file_contents_as_committed(self):
        """
        Should match file contents as committed to specified revision.
        """
        if not self.rcs.versioned:
            return
        for path in self.test_files:
            full_path = self.full_path(path)
            self.rcs.set_file_contents(
                full_path, self.test_contents['rev_1'])
            revision = self.rcs.commit("Commit current status")
            self.rcs.set_file_contents(
                full_path, self.test_contents['uncommitted'])
            dup_repo_path = self.rcs.duplicate_repo(revision)
            dup_file_path = os.path.join(dup_repo_path, path)
            dup_file_contents = file(dup_file_path, 'rb').read()
            self.failUnlessEqual(
                self.test_contents['rev_1'], dup_file_contents)
            self.rcs.remove_duplicate_repo()


def make_rcs_testcase_subclasses(rcs_class, namespace):
    """
    Make RCSTestCase subclasses for rcs_class in the namespace.
    """
    rcs_testcase_classes = [
        c for c in (
            ob for ob in globals().values() if isinstance(ob, type))
        if issubclass(c, RCSTestCase)]

    for base_class in rcs_testcase_classes:
        testcase_class_name = rcs_class.__name__ + base_class.__name__
        testcase_class_bases = (base_class,)
        testcase_class_dict = dict(base_class.__dict__)
        testcase_class_dict['Class'] = rcs_class
        testcase_class = type(
            testcase_class_name, testcase_class_bases, testcase_class_dict)
        setattr(namespace, testcase_class_name, testcase_class)


unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
