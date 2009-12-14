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
import shutil
import sys
import tempfile

import libbe
import libbe.storage.base
import libbe.util.encoding
from libbe.storage.base import EmptyCommit, InvalidRevision
from libbe.util.utility import Dir, search_parent_directories
from libbe.util.subproc import CommandError, invoke
from libbe.util.plugin import import_by_name
#import libbe.storage.util.upgrade as upgrade

if libbe.TESTING == True:
    import unittest
    import doctest

    import libbe.ui.util.user

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
        module = import_by_name('libbe.storage.vcs.%s' % submodname)
        vcs = module.new()
        if matchfn(vcs) == True:
            return vcs
    return VCS()

def vcs_by_name(vcs_name):
    """Return the module for the VCS with the given name"""
    if vcs_name == VCS.name:
        return new()
    return _get_matching_vcs(lambda vcs: vcs.name == vcs_name)

def detect_vcs(dir):
    """Return an VCS instance for the vcs being used in this directory"""
    return _get_matching_vcs(lambda vcs: vcs._detect(dir))

def installed_vcs():
    """Return an instance of an installed VCS"""
    return _get_matching_vcs(lambda vcs: vcs.installed())


class VCSNotRooted (libbe.storage.base.ConnectionError):
    def __init__(self, vcs):
        msg = 'VCS not rooted'
        libbe.storage.base.ConnectionError.__init__(self, msg)
        self.vcs = vcs

class VCSUnableToRoot (libbe.storage.base.ConnectionError):
    def __init__(self, vcs):
        msg = 'VCS unable to root'
        libbe.storage.base.ConnectionError.__init__(self, msg)
        self.vcs = vcs

class InvalidPath (libbe.storage.base.InvalidID):
    def __init__(self, path, root, msg=None):
        if msg == None:
            msg = 'Path "%s" not in root "%s"' % (path, root)
        libbe.storage.base.InvalidID.__init__(self, msg)
        self.path = path
        self.root = root

class SpacerCollision (InvalidPath):
    def __init__(self, path, spacer):
        msg = 'Path "%s" collides with spacer directory "%s"' % (path, spacer)
        InvalidPath.__init__(self, path, root=None, msg=msg)
        self.spacer = spacer

class NoSuchFile (libbe.storage.base.InvalidID):
    def __init__(self, pathname, root='.'):
        path = os.path.abspath(os.path.join(root, pathname))
        libbe.storage.base.InvalidID.__init__(self, 'No such file: %s' % path)


class CachedPathID (object):
    """
    Storage ID <-> path policy.
      .../.be/BUGDIR/bugs/BUG/comments/COMMENT
        ^-- root path

    >>> dir = Dir()
    >>> os.mkdir(os.path.join(dir.path, '.be'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '123'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments', 'def'))
    >>> os.mkdir(os.path.join(dir.path, '.be', 'abc', 'bugs', '456'))
    >>> file(os.path.join(dir.path, '.be', 'abc', 'values'),
    ...      'w').close()
    >>> file(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'values'),
    ...      'w').close()
    >>> file(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments', 'def', 'values'),
    ...      'w').close()
    >>> c = CachedPathID()
    >>> c.root(dir.path)
    >>> c.id(os.path.join(dir.path, '.be', 'abc', 'bugs', '123', 'comments', 'def', 'values'))
    'def/values'
    >>> c.init()
    >>> sorted(os.listdir(os.path.join(c._root, '.be')))
    ['abc', 'id-cache']
    >>> c.connect()
    >>> c.path('123/values') # doctest: +ELLIPSIS
    u'.../.be/abc/bugs/123/values'
    >>> c.disconnect()
    >>> c.destroy()
    >>> sorted(os.listdir(os.path.join(c._root, '.be')))
    ['abc']
    >>> c.connect() # demonstrate auto init
    >>> sorted(os.listdir(os.path.join(c._root, '.be')))
    ['abc', 'id-cache']
    >>> c.add_id(u'xyz', parent=None) # doctest: +ELLIPSIS
    u'.../.be/xyz'
    >>> c.add_id('xyz/def', parent='xyz') # doctest: +ELLIPSIS
    u'.../.be/xyz/def'
    >>> c.add_id('qrs', parent='123') # doctest: +ELLIPSIS
    u'.../.be/abc/bugs/123/comments/qrs'
    >>> c.disconnect()
    >>> c.connect()
    >>> c.path('qrs') # doctest: +ELLIPSIS
    u'.../.be/abc/bugs/123/comments/qrs'
    >>> c.remove_id('qrs')
    >>> c.path('qrs')
    Traceback (most recent call last):
      ...
    InvalidID: 'qrs'
    >>> c.disconnect()
    >>> c.destroy()
    >>> dir.cleanup()
    """
    def __init__(self, encoding=None):
        self.encoding = libbe.util.encoding.get_filesystem_encoding()
        self._spacer_dirs = ['.be', 'bugs', 'comments']

    def root(self, path):
        self._root = os.path.abspath(path).rstrip(os.path.sep)
        self._cache_path = os.path.join(
            self._root, self._spacer_dirs[0], 'id-cache')

    def init(self):
        """
        Create cache file for an existing .be directory.
        File if multiple lines of the form:
          UUID\tPATH
        """
        self._cache = {}
        spaced_root = os.path.join(self._root, self._spacer_dirs[0])
        for dirpath, dirnames, filenames in os.walk(spaced_root):
            if dirpath == spaced_root:
                continue
            try:
                id = self.id(dirpath)
                relpath = dirpath[len(self._root)+1:]
                if id.count('/') == 0:
                    self._cache[id] = relpath
            except InvalidPath:
                pass
        self._changed = True
        self.disconnect()

    def destroy(self):
        if os.path.exists(self._cache_path):
            os.remove(self._cache_path)

    def connect(self):
        if not os.path.exists(self._cache_path):
            try:
                self.init()
            except IOError:
                raise libbe.storage.base.ConnectionError
        self._cache = {} # key: uuid, value: path
        self._changed = False
        f = codecs.open(self._cache_path, 'r', self.encoding)
        for line in f:
            fields = line.rstrip('\n').split('\t')
            self._cache[fields[0]] = fields[1]
        f.close()

    def disconnect(self):
        if self._changed == True:
            f = codecs.open(self._cache_path, 'w', self.encoding)
            for uuid,path in self._cache.items():
                f.write('%s\t%s\n' % (uuid, path))
            f.close()
        self._cache = {}

    def path(self, id, relpath=False):
        fields = id.split('/', 1)
        uuid = fields[0]
        if len(fields) == 1:
            extra = []
        else:
            extra = fields[1:]
        if uuid not in self._cache:
            raise libbe.storage.base.InvalidID(uuid)
        if relpath == True:
            return os.path.join(self._cache[uuid], *extra)
        return os.path.join(self._root, self._cache[uuid], *extra)

    def add_id(self, id, parent=None):
        if id.count('/') > 0:
            # not a UUID-level path
            assert id.startswith(parent), \
                'Strange ID: "%s" should start with "%s"' % (id, parent)
            path = self.path(id)
        elif id in self._cache:
            # already added
            path = self.path(id)
        else:
            if parent == None:
                parent_path = ''
                spacer = self._spacer_dirs[0]
            else:
                assert parent.count('/') == 0, \
                    'Strange parent ID: "%s" should be UUID' % parent
                parent_path = self.path(parent, relpath=True)
                parent_spacer = parent_path.split(os.path.sep)[-2]
                i = self._spacer_dirs.index(parent_spacer)
                spacer = self._spacer_dirs[i+1]
            path = os.path.join(parent_path, spacer, id)
            self._cache[id] = path
            self._changed = True
            path = os.path.join(self._root, path)
        return path

    def remove_id(self, id):
        if id.count('/') > 0:
            return # not a UUID-level path
        self._cache.pop(id)
        self._changed = True

    def id(self, path):
        path = os.path.abspath(path)
        if not path.startswith(self._root + os.path.sep):
            raise InvalidPath('Path %s not in root %s' % (path, self._root))
        path = path[len(self._root)+1:]
        orig_path = path
        if not path.startswith(self._spacer_dirs[0] + os.path.sep):
            raise InvalidPath(path, self._spacer_dirs[0])
        for spacer in self._spacer_dirs:
            if not path.startswith(spacer + os.path.sep):
                break
            id = path[len(spacer)+1:]
            fields = path[len(spacer)+1:].split(os.path.sep,1)
            if len(fields) == 1:
                break
            path = fields[1]
        for spacer in self._spacer_dirs:
            if id.endswith(os.path.sep + spacer):
                raise SpacerCollision(orig_path, spacer)
        if os.path.sep != '/':
            id = id.replace(os.path.sep, '/')
        return id


def new():
    return VCS()

class VCS (libbe.storage.base.VersionedStorage):
    """
    This class implements a 'no-vcs' interface.

    Support for other VCSs can be added by subclassing this class, and
    overriding methods _vcs_*() with code appropriate for your VCS.

    The methods _u_*() are utility methods available to the _vcs_*()
    methods.

    Sink to existing root
    ======================

    Consider the following usage case:
    You have a bug directory rooted in
      /path/to/source
    by which I mean the '.be' directory is at
      /path/to/source/.be
    However, you're of in some subdirectory like
      /path/to/source/GUI/testing
    and you want to comment on a bug.  Setting sink_to_root=True when
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
    changed in memory, a call to .save() immediately before the
    .set_sync_with_disk(True) call is a safe move.

    Regardless of .sync_with_disk, a call to .save() will write out
    all the contents that the BugDir instance has loaded into memory.
    If sync_with_disk has been True over the course of all interesting
    changes, this .save() call will be a waste of time.

    The BugDir will only load information from the file system when it
    loads new settings/bugs/comments that it doesn't already have in
    memory and .sync_with_disk == True.

    Allow storage initialization
    ========================

    This one is for testing purposes.  Setting it to True allows the
    BugDir to search for an installed Storage backend and initialize
    it in the root directory.  This is a convenience option for
    supporting tests of versioning functionality
    (e.g. .duplicate_bugdir).

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

        if root == None:
            root = os.getcwd()
        if sink_to_existing_root == True:
            self.root = self._find_root(root)
        else:
            if not os.path.exists(root):
                self.root = None
                raise NoRootEntry(root)
            self.root = root
        # get a temporary storage until we've loaded settings
        self.sync_with_disk = False
        self.storage = self._guess_storage()

            if assert_new_BugDir == True:
                if os.path.exists(self.get_path()):
                    raise AlreadyInitialized, self.get_path()
            if storage == None:
                storage = self._guess_storage(allow_storage_init)
            self.storage = storage
            self._setup_user_id(self.user_id)


    # methods for getting the BugDir situated in the filesystem

    def _find_root(self, path):
        '''
        Search for an existing bug database dir and it's ancestors and
        return a BugDir rooted there.  Only called by __init__, and
        then only if sink_to_existing_root == True.
        '''
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

    def _guess_storage(self, allow_storage_init=False):
        '''
        Only called by __init__.
        '''
        deepdir = self.get_path()
        if not os.path.exists(deepdir):
            deepdir = os.path.dirname(deepdir)
        new_storage = storage.detect_storage(deepdir)
        install = False
        if new_storage.name == "None":
            if allow_storage_init == True:
                new_storage = storage.installed_storage()
                new_storage.init(self.root)
        return new_storage

os.listdir(self.get_path("bugs")):
    """
    name = 'None'
    client = 'false' # command-line tool for _u_invoke_client

    def __init__(self, *args, **kwargs):
        if 'encoding' not in kwargs:
            kwargs['encoding'] = libbe.util.encoding.get_filesystem_encoding()
        libbe.storage.base.VersionedStorage.__init__(self, *args, **kwargs)
        self.versioned = False
        self.interspersed_vcs_files = False
        self.verbose_invoke = False
        self._cached_path_id = CachedPathID()
        self._rooted = False

    def _vcs_version(self):
        """
        Return the VCS version string.
        """
        return '0'

    def _vcs_get_user_id(self):
        """
        Get the VCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the VCS has not been configured with a username, return None.
        """
        return None

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
        if os.path.isdir(path) == False:
            path = os.path.dirname(path)
            if path == '':
                path = os.path.abspath('.')
        return path

    def _vcs_init(self, path):
        """
        Begin versioning the tree based at path.
        """
        pass

    def _vcs_destroy(self):
        """
        Remove any files used in versioning (e.g. whatever _vcs_init()
        created).
        """
        pass

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

    def _vcs_is_versioned(self, path):
        """
        Return true if a path is under version control, False
        otherwise.  You only need to set this if the VCS goes about
        dumping VCS-specific files into the .be directory.

        If you do need to implement this method (e.g. Arch), set
          self.interspersed_vcs_files = True 
        """
        assert self.interspersed_vcs_files == False
        raise NotImplementedError

    def _vcs_get_file_contents(self, path, revision=None):
        """
        Get the file contents as they were in a given revision.
        Revision==None specifies the current revision.
        """
        if revision != None:
            raise libbe.storage.base.InvalidRevision(
                'The %s VCS does not support revision specifiers' % self.name)
        path = os.path.join(self.repo, path)
        if not os.path.exists(path):
            return libbe.util.InvalidObject
        if os.path.isdir(path):
            return libbe.storage.base.InvalidDirectory
        f = open(path, 'rb')
        contents = f.read()
        f.close()
        return contents

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

    def version(self):
        # Cache version string for efficiency.
        if not hasattr(self, '_version'):
            self._version = self._get_version()
        return self._version

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
        if self.version() != None:
            return True
        return False

    def get_user_id(self):
        """
        Get the VCS's suggested user id (e.g. "John Doe <jdoe@example.com>").
        If the VCS has not been configured with a username, return None.
        You can override the automatic lookup procedure by setting the
        VCS.user_id attribute to a string of your choice.
        """
        if not hasattr(self, 'user_id'):
            self.user_id = self._vcs_get_user_id()
        return self.user_id

    def _detect(self, path='.'):
        """
        Detect whether a directory is revision controlled with this VCS.
        """
        return self._vcs_detect(path)

    def root(self):
        """
        Set the root directory to the path's VCS root.  This is the
        default working directory for future invocations.
        """
        if self._detect(self.repo) == False:
            raise VCSUnableToRoot(self)
        root = self._vcs_root(self.repo)
        self.repo = os.path.abspath(root)
        if os.path.isdir(self.repo) == False:
            self.repo = os.path.dirname(self.repo)
        self.be_dir = os.path.join(
            self.repo, self._cached_path_id._spacer_dirs[0])
        self._cached_path_id.root(self.repo)
        self._rooted == True

    def _init(self):
        """
        Begin versioning the tree based at self.repo.
        Also roots the vcs at path.
        """
        if not os.path.exists(self.repo) or not os.path.isdir(self.repo):
            raise VCSUnableToRoot(self)
        if self._vcs_detect(self.repo) == False:
            self._vcs_init(self.repo)
        self.root()
        os.mkdir(self.be_dir)
        self._vcs_add(self._u_rel_path(self.be_dir))
        self._cached_path_id.init()

    def _destroy(self):
        self._vcs_destroy()
        self._cached_path_id.destroy()
        if os.path.exists(self.be_dir):
            shutil.rmtree(self.be_dir)

    def _connect(self):
        if self._rooted == False:
            self.root()
        if not os.path.isdir(self.be_dir):
            raise libbe.storage.base.ConnectionError(self)
        self._cached_path_id.connect()
        self.check_disk_version()

    def disconnect(self):
        self._cached_path_id.disconnect()

    def _add(self, id, parent=None, directory=False):
        path = self._cached_path_id.add_id(id, parent)
        relpath = self._u_rel_path(path)
        reldirs = relpath.split(os.path.sep)
        if directory == False:
            reldirs = reldirs[:-1]
        dir = self.repo
        for reldir in reldirs:
            dir = os.path.join(dir, reldir)
            if not os.path.exists(dir):
                os.mkdir(dir)
                self._vcs_add(self._u_rel_path(dir))
            elif not os.path.isdir(dir):
                raise libbe.storage.base.InvalidDirectory
        if directory == False:
            if not os.path.exists(path):
                open(path, 'w').close()
            self._vcs_add(self._u_rel_path(path))

    def _remove(self, id):
        path = self._cached_path_id.path(id)
        if os.path.exists(path):
            if os.path.isdir(path) and len(self.children(id)) > 0:
                raise libbe.storage.base.DirectoryNotEmpty(id)
            self._vcs_remove(self._u_rel_path(path))
            if os.path.exists(path):
                if os.path.isdir(path):
                    os.rmdir(path)
                else:
                    os.remove(path)
        self._cached_path_id.remove_id(id)

    def _recursive_remove(self, id):
        path = self._cached_path_id.path(id)
        for dirpath,dirnames,filenames in os.walk(path, topdown=False):
            filenames.extend(dirnames)
            for f in filenames:
                fullpath = os.path.join(dirpath, f)
                if os.path.exists(fullpath) == False:
                    continue
                self._vcs_remove(self._u_rel_path(fullpath))
        if os.path.exists(path):
            shutil.rmtree(path)
        path = self._cached_path_id.path(id, relpath=True)
        for id,p in self._cached_path_id._cache.items():
            if p.startswith(path):
                self._cached_path_id.remove_id(id)

    def _children(self, id=None, revision=None):
        if id==None:
            path = self.be_dir
        else:
            path = self._cached_path_id.path(id)
        if os.path.isdir(path) == False:
            return []
        children = os.listdir(path)
        for i,c in enumerate(children):
            if c in self._cached_path_id._spacer_dirs:
                children[i] = None
                children.extend([os.path.join(c, c2) for c2 in
                                 os.listdir(os.path.join(path, c))])
            elif c == 'id-cache':
                children[i] = None
        for i,c in enumerate(children):
            if c == None: continue
            cpath = os.path.join(path, c)
            if self.interspersed_vcs_files == True \
                    and self._vcs_is_versioned(cpath) == False:
                children[i] = None
            else:
                children[i] = self._cached_path_id.id(cpath)
        return [c for c in children if c != None]

    def _get(self, id, default=libbe.util.InvalidObject, revision=None):
        try:
            path = self._cached_path_id.path(id)
        except libbe.storage.base.InvalidID, e:
            if default == libbe.util.InvalidObject:
                raise e
            return default
        relpath = self._u_rel_path(path)
        contents = self._vcs_get_file_contents(relpath,revision)
        if contents in [libbe.storage.base.InvalidDirectory,
                        libbe.util.InvalidObject]:
            raise libbe.storage.base.InvalidID(id)
        elif len(contents) == 0:
            return None
        return contents

    def _set(self, id, value):
        try:
            path = self._cached_path_id.path(id)
        except libbe.storage.base.InvalidID, e:
            raise e
        if not os.path.exists(path):
            raise libbe.storage.base.InvalidID(id)
        if os.path.isdir(path):
            raise libbe.storage.base.InvalidDirectory(id)
        f = open(path, "wb")
        f.write(value)
        f.close()
        self._vcs_update(self._u_rel_path(path))

    def _commit(self, summary, body=None, allow_empty=False):
        summary = summary.strip()+'\n'
        if body is not None:
            summary += '\n' + body.strip() + '\n'
        descriptor, filename = tempfile.mkstemp()
        revision = None
        try:
            temp_file = os.fdopen(descriptor, 'wb')
            temp_file.write(summary)
            temp_file.flush()
            revision = self._vcs_commit(filename, allow_empty=allow_empty)
            temp_file.close()
        finally:
            os.remove(filename)
        return revision

    def revision_id(self, index=None):
        if index == None:
            return None
        try:
            if int(index) != index:
                raise InvalidRevision(index)
        except ValueError:
            raise InvalidRevision(index)
        revid = self._vcs_revision_id(index)
        if revid == None:
            raise libbe.storage.base.InvalidRevision(index)
        return revid

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
            kwargs['cwd'] = self.repo
        if 'verbose' not in kwargs:
            kwargs['verbose'] = self.verbose_invoke
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

    def _u_rel_path(self, path, root=None):
        """
        Return the relative path to path from root.
        >>> vcs = new()
        >>> vcs._u_rel_path("/a.b/c/.be", "/a.b/c")
        '.be'
        """
        if root == None:
            if self.repo == None:
                raise VCSNotRooted(self)
            root = self.repo
        path = os.path.abspath(path)
        absRoot = os.path.abspath(root)
        absRootSlashedDir = os.path.join(absRoot,"")
        if not path.startswith(absRootSlashedDir):
            raise InvalidPath(path, absRootSlashedDir)
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
            assert self.repo != None, "VCS not rooted"
            root = self.repo
        return os.path.abspath(os.path.join(root, path))

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

    def check_disk_version(self):
        version = self.version()
        #if version != upgrade.BUGDIR_DISK_VERSION:
        #    upgrade.upgrade(self.repo, version)

    def disk_version(self, path=None):
        """
        Requires disk access.
        """
        if path == None:
            path = self.get_path('version')
        return self.get(path).rstrip('\n')

    def set_disk_version(self):
        """
        Requires disk access.
        """
        if self.sync_with_disk == False:
            raise DiskAccessRequired('set version')
        self.vcs.mkdir(self.get_path())
        #self.vcs.set_file_contents(self.get_path("version"),
        #                           upgrade.BUGDIR_DISK_VERSION+"\n")



if libbe.TESTING == True:
    class VCSTestCase (unittest.TestCase):
        """
        Test cases for base VCS class (in addition to the Storage test
        cases).
        """

        Class = VCS

        def __init__(self, *args, **kwargs):
            super(VCSTestCase, self).__init__(*args, **kwargs)
            self.dirname = None

        def setUp(self):
            """Set up test fixtures for Storage test case."""
            super(VCSTestCase, self).setUp()
            self.dir = Dir()
            self.dirname = self.dir.path
            self.s = self.Class(repo=self.dirname)
            if self.s.installed() == True:
                self.s.init()
                self.s.connect()

        def tearDown(self):
            super(VCSTestCase, self).tearDown()
            if self.s.installed() == True:
                self.s.disconnect()
                self.s.destroy()
            self.dir.cleanup()

    class VCS_installed_TestCase (VCSTestCase):
        def test_installed(self):
            """
            See if the VCS is installed.
            """
            self.failUnless(self.s.installed() == True,
                            '%(name)s VCS not found' % vars(self.Class))


    class VCS_detection_TestCase (VCSTestCase):
        def test_detection(self):
            """
            See if the VCS detects its installed repository
            """
            if self.s.installed():
                self.s.disconnect()
                self.failUnless(self.s._detect(self.dirname) == True,
                    'Did not detected %(name)s VCS after initialising'
                    % vars(self.Class))
                self.s.connect()

        def test_no_detection(self):
            """
            See if the VCS detects its installed repository
            """
            if self.s.installed() and self.Class.name != 'None':
                self.s.disconnect()
                self.s.destroy()
                self.failUnless(self.s._detect(self.dirname) == False,
                    'Detected %(name)s VCS before initialising'
                    % vars(self.Class))
                self.s.init()
                self.s.connect()

        def test_vcs_repo_in_specified_root_path(self):
            """VCS root directory should be in specified root path."""
            rp = os.path.realpath(self.s.repo)
            dp = os.path.realpath(self.dirname)
            vcs_name = self.Class.name
            self.failUnless(
                dp == rp or rp == None,
                "%(vcs_name)s VCS root in wrong dir (%(dp)s %(rp)s)" % vars())

    class VCS_get_user_id_TestCase(VCSTestCase):
        """Test cases for VCS.get_user_id method."""

        def test_gets_existing_user_id(self):
            """Should get the existing user ID."""
            if self.s.installed():
                user_id = self.s.get_user_id()
                if user_id == None:
                    return
                name,email = libbe.ui.util.user.parse_user_id(user_id)
                if email != None:
                    self.failUnless('@' in email, email)

    def make_vcs_testcase_subclasses(vcs_class, namespace):
        c = vcs_class()
        if c.installed():
            if c.versioned == True:
                libbe.storage.base.make_versioned_storage_testcase_subclasses(
                    vcs_class, namespace)
            else:
                libbe.storage.base.make_storage_testcase_subclasses(
                    vcs_class, namespace)

        if namespace != sys.modules[__name__]:
            # Make VCSTestCase subclasses for vcs_class in the namespace.
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

    make_vcs_testcase_subclasses(VCS, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
