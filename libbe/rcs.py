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
from utility import Dir

def _get_matching_rcs(matchfn):
    """Return the first module for which matchfn(RCS_instance) is true"""
    import arch
    import bzr
    import hg
    import git
    for module in [arch, bzr, hg, git]:
        rcs = module.new()
        if matchfn(rcs):
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

def new():
    return RCS()

class RCS(object):
    """
    Implement the 'no-rcs' interface.

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
        Get the file as it was in a given revision.
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
    def detect(self, path=None):
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
        id.
        """
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
    def get_file_contents(self, path, revision=None):
        """
        Get the file as it was in a given revision.
        Revision==None specifies the current revision.
        """
        relpath = self._u_rel_path(path)
        return self._rcs_get_file_contents(relpath, revision)
    def set_file_contents(self, path, contents):
        """
        Set the file contents under version control.
        """
        add = not os.path.exists(path)
        file(path, "wb").write(contents)
        if add:
            self.add(path)
        else:
            self.update(path)
    def mkdir(self, path):
        """
        Created directory at path under version control.
        """
        os.mkdir(path)
        self.add(path)
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
        try :
            if self.verboseInvoke == True:
                print "%s$ %s" % (cwd, " ".join(args))
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
        if status not in expect:
            raise CommandError(error, status)
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
        path = os.path.realpath(path)
        assert os.path.exists(path)
        old_path = None
        while True:
            if os.path.exists(os.path.join(path, filename)):
                return os.path.join(path, filename)
            if path == old_path:
                return None
            old_path = path
            path = os.path.dirname(path)
    def _u_rel_path(self, path, root=None):
        """
        Return the relative path to path from root.
        >>> rcs = new()
        >>> rcs._u_rel_path("/a.b/c/.be", "/a.b/c")
        '.be'
        """
        if root == None:
            assert self.rootdir != None, "RCS not rooted"
            root = self.rootdir
        if os.path.isabs(path):
            absRoot = os.path.abspath(root)
            absRootSlashedDir = os.path.join(absRoot,"")
            assert path.startswith(absRootSlashedDir), \
                "file %s not in root %s" % (path, absRootSlashedDir)
            assert path != absRootSlashedDir, \
                "file %s == root directory %s" % (path, absRootSlashedDir)
            path = path[len(absRootSlashedDir):]
        return path
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
        

class RCStestCase(unittest.TestCase):
    Class = RCS
    def __init__(self, *args, **kwargs):
        unittest.TestCase.__init__(self, *args, **kwargs)
        self.dirname = None
    def instantiateRCS(self):
        return self.Class()
    def setUp(self):
        self.dir = Dir()
        self.dirname = self.dir.path
        self.rcs = self.instantiateRCS()
    def tearDown(self):
        del(self.rcs)
        del(self.dirname)
    def fullPath(self, path):
        return os.path.join(self.dirname, path)
    def assertPathExists(self, path):
        fullpath = self.fullPath(path)
        self.failUnless(os.path.exists(fullpath)==True,
                        "path %s does not exist" % fullpath)
    def uidTest(self):
        user_id = self.rcs.get_user_id()
        self.failUnless(user_id != None,
                        "unable to get a user id")
        user_idB = "John Doe <jdoe@example.com>"
        if self.rcs.name in ["None", "hg"]:
            self.assertRaises(SettingIDnotSupported, self.rcs.set_user_id,
                              user_idB)
        else:
            self.rcs.set_user_id(user_idB)
            self.failUnless(self.rcs.get_user_id() == user_idB,
                            "user id not set correctly (was %s, is %s)" \
                                % (user_id, self.rcs.get_user_id()))
            self.failUnless(self.rcs.set_user_id(user_id) == None,
                            "unable to restore user id %s" % user_id)
            self.failUnless(self.rcs.get_user_id() == user_id,
                            "unable to restore user id %s" % user_id)
    def versionTest(self, path):
        origpath = path
        path = self.fullPath(path)
        contentsA = "Lorem ipsum"
        contentsB = "dolor sit amet"
        self.rcs.set_file_contents(path,contentsA)
        self.failUnless(self.rcs.get_file_contents(path)==contentsA,
                        "File contents not set or read correctly")
        revision = self.rcs.commit("Commit current status")
        self.failUnless(self.rcs.get_file_contents(path)==contentsA,
                        "Committing File contents not set or read correctly")
        if self.rcs.versioned == True:
            self.rcs.set_file_contents(path,contentsB)
            self.failUnless(self.rcs.get_file_contents(path)==contentsB,
                            "File contents not set correctly after commit")
            contentsArev = self.rcs.get_file_contents(path, revision)
            self.failUnless(contentsArev==contentsA, \
                "Original file contents not saved in revision %s\n%s\n%s\n" \
                                % (revision, contentsA, contentsArev))
            dup = self.rcs.duplicate_repo(revision)
            duppath = os.path.join(dup, origpath)
            dupcont = file(duppath, "rb").read()
            self.failUnless(dupcont == contentsA)
            self.rcs.remove_duplicate_repo()
    def testRun(self):
        self.failUnless(self.rcs.installed() == True,
                        "%s RCS not found" % self.Class.name)
        if self.Class.name != "None":
            self.failUnless(self.rcs.detect(self.dirname)==False,
                            "Detected %s RCS before initializing" \
                                % self.Class.name)
        self.rcs.init(self.dirname)
        self.failUnless(self.rcs.detect(self.dirname)==True,
                        "Did not detect %s RCS after initializing" \
                            % self.Class.name)
        rp = os.path.realpath(self.rcs.rootdir)
        dp = os.path.realpath(self.dirname)
        self.failUnless(dp == rp or rp == None,
                        "%s RCS root in wrong dir (%s %s)" \
                            % (self.Class.name, dp, rp))
        self.uidTest()
        self.rcs.mkdir(self.fullPath('a'))
        self.rcs.mkdir(self.fullPath('a/b'))
        self.rcs.mkdir(self.fullPath('c'))
        self.assertPathExists('a')
        self.assertPathExists('a/b')
        self.assertPathExists('c')
        self.versionTest('a/text')
        self.versionTest('a/b/text')
        self.rcs.recursive_remove(self.fullPath('a'))

unitsuite = unittest.TestLoader().loadTestsFromTestCase(RCStestCase)
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
