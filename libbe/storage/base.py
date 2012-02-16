# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
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
Abstract bug repository data storage to easily support multiple backends.
"""

import copy
import os
import pickle
import types

from libbe.error import NotSupported
import libbe.storage
from libbe.util.tree import Tree
from libbe.util import InvalidObject
import libbe.version
from libbe import TESTING

if TESTING == True:
    import doctest
    import os.path
    import sys
    import unittest

    from libbe.util.utility import Dir

class ConnectionError (Exception):
    pass

class InvalidStorageVersion(ConnectionError):
    def __init__(self, active_version, expected_version=None):
        if expected_version == None:
            expected_version = libbe.storage.STORAGE_VERSION
        msg = 'Storage in "%s" not the expected "%s"' \
            % (active_version, expected_version)
        Exception.__init__(self, msg)
        self.active_version = active_version
        self.expected_version = expected_version

class InvalidID (KeyError):
    def __init__(self, id=None, revision=None, msg=None):
        KeyError.__init__(self, id)
        self.msg = msg
        self.id = id
        self.revision = revision
    def __str__(self):
        if self.msg == None:
            return '%s in revision %s' % (self.id, self.revision)
        return self.msg


class InvalidRevision (KeyError):
    pass

class InvalidDirectory (Exception):
    pass

class DirectoryNotEmpty (InvalidDirectory):
    pass

class NotWriteable (NotSupported):
    def __init__(self, msg):
        NotSupported.__init__(self, 'write', msg)

class NotReadable (NotSupported):
    def __init__(self, msg):
        NotSupported.__init__(self, 'read', msg)

class EmptyCommit(Exception):
    def __init__(self):
        Exception.__init__(self, 'No changes to commit')

class _EMPTY (object):
    """Entry has been added but has no user-set value."""
    pass

class Entry (Tree):
    def __init__(self, id, value=_EMPTY, parent=None, directory=False,
                 children=None):
        if children == None:
            Tree.__init__(self)
        else:
            Tree.__init__(self, children)
        self.id = id
        self.value = value
        self.parent = parent
        if self.parent != None:
            if self.parent.directory == False:
                raise InvalidDirectory(
                    'Non-directory %s cannot have children' % self.parent)
            parent.append(self)
        self.directory = directory

    def __str__(self):
        return '<Entry %s: %s>' % (self.id, self.value)

    def __repr__(self):
        return str(self)

    def __cmp__(self, other, local=False):
        if other == None:
            return cmp(1, None)
        if cmp(self.id, other.id) != 0:
            return cmp(self.id, other.id)
        if cmp(self.value, other.value) != 0:
            return cmp(self.value, other.value)
        if local == False:
            if self.parent == None:
                if cmp(self.parent, other.parent) != 0:
                    return cmp(self.parent, other.parent)
            elif self.parent.__cmp__(other.parent, local=True) != 0:
                return self.parent.__cmp__(other.parent, local=True)
            for sc,oc in zip(self, other):
                if sc.__cmp__(oc, local=True) != 0:
                    return sc.__cmp__(oc, local=True)
        return 0

    def _objects_to_ids(self):
        if self.parent != None:
            self.parent = self.parent.id
        for i,c in enumerate(self):
            self[i] = c.id
        return self

    def _ids_to_objects(self, dict):
        if self.parent != None:
            self.parent = dict[self.parent]
        for i,c in enumerate(self):
            self[i] = dict[c]
        return self

class Storage (object):
    """
    This class declares all the methods required by a Storage
    interface.  This implementation just keeps the data in a
    dictionary and uses pickle for persistent storage.
    """
    name = 'Storage'

    def __init__(self, repo='/', encoding='utf-8', options=None):
        self.repo = repo
        self.encoding = encoding
        self.options = options
        self.readable = True  # soft limit (user choice)
        self._readable = True # hard limit (backend choice)
        self.writeable = True  # soft limit (user choice)
        self._writeable = True # hard limit (backend choice)
        self.versioned = False
        self.can_init = True
        self.connected = False

    def __str__(self):
        return '<%s %s %s>' % (self.__class__.__name__, id(self), self.repo)

    def __repr__(self):
        return str(self)

    def version(self):
        """Return a version string for this backend."""
        return libbe.version.version()

    def storage_version(self, revision=None):
        """Return the storage format for this backend."""
        return libbe.storage.STORAGE_VERSION

    def is_readable(self):
        return self.readable and self._readable

    def is_writeable(self):
        return self.writeable and self._writeable

    def init(self):
        """Create a new storage repository."""
        if self.can_init == False:
            raise NotSupported('init',
                               'Cannot initialize this repository format.')
        if self.is_writeable() == False:
            raise NotWriteable('Cannot initialize unwriteable storage.')
        return self._init()

    def _init(self):
        f = open(os.path.join(self.repo, 'repo.pkl'), 'wb')
        root = Entry(id='__ROOT__', directory=True)
        d = {root.id:root}
        pickle.dump(dict((k,v._objects_to_ids()) for k,v in d.items()), f, -1)
        f.close()

    def destroy(self):
        """Remove the storage repository."""
        if self.is_writeable() == False:
            raise NotWriteable('Cannot destroy unwriteable storage.')
        return self._destroy()

    def _destroy(self):
        os.remove(os.path.join(self.repo, 'repo.pkl'))

    def connect(self):
        """Open a connection to the repository."""
        if self.is_readable() == False:
            raise NotReadable('Cannot connect to unreadable storage.')
        self._connect()
        self.connected = True

    def _connect(self):
        try:
            f = open(os.path.join(self.repo, 'repo.pkl'), 'rb')
        except IOError:
            raise ConnectionError(self)
        d = pickle.load(f)
        self._data = dict((k,v._ids_to_objects(d)) for k,v in d.items())
        f.close()

    def disconnect(self):
        """Close the connection to the repository."""
        if self.is_writeable() == False:
            return
        if self.connected == False:
            return
        self._disconnect()
        self.connected = False

    def _disconnect(self):
        f = open(os.path.join(self.repo, 'repo.pkl'), 'wb')
        pickle.dump(dict((k,v._objects_to_ids())
                         for k,v in self._data.items()), f, -1)
        f.close()
        self._data = None

    def add(self, id, *args, **kwargs):
        """Add an entry"""
        if self.is_writeable() == False:
            raise NotWriteable('Cannot add entry to unwriteable storage.')
        if not self.exists(id):
            self._add(id, *args, **kwargs)

    def _add(self, id, parent=None, directory=False):
        if parent == None:
            parent = '__ROOT__'
        p = self._data[parent]
        self._data[id] = Entry(id, parent=p, directory=directory)

    def exists(self, *args, **kwargs):
        """Check an entry's existence"""
        if self.is_readable() == False:
            raise NotReadable('Cannot check entry existence in unreadable storage.')
        return self._exists(*args, **kwargs)

    def _exists(self, id, revision=None):
        return id in self._data

    def remove(self, *args, **kwargs):
        """Remove an entry."""
        if self.is_writeable() == False:
            raise NotSupported('write',
                               'Cannot remove entry from unwriteable storage.')
        self._remove(*args, **kwargs)

    def _remove(self, id):
        if self._data[id].directory == True \
                and len(self.children(id)) > 0:
            raise DirectoryNotEmpty(id)
        e = self._data.pop(id)
        e.parent.remove(e)

    def recursive_remove(self, *args, **kwargs):
        """Remove an entry and all its decendents."""
        if self.is_writeable() == False:
            raise NotSupported('write',
                               'Cannot remove entries from unwriteable storage.')
        self._recursive_remove(*args, **kwargs)

    def _recursive_remove(self, id):
        for entry in reversed(list(self._data[id].traverse())):
            self._remove(entry.id)

    def ancestors(self, *args, **kwargs):
        """Return a list of the specified entry's ancestors' ids."""
        if self.is_readable() == False:
            raise NotReadable('Cannot list parents with unreadable storage.')
        return self._ancestors(*args, **kwargs)

    def _ancestors(self, id=None, revision=None):
        if id == None:
            return []
        ancestors = []
        stack = [id]
        while len(stack) > 0:
            id = stack.pop(0)
            parent = self._data[id].parent
            if parent != None and not parent.id.startswith('__'):
                ancestor = parent.id
                ancestors.append(ancestor)
                stack.append(ancestor)
        return ancestors

    def children(self, *args, **kwargs):
        """Return a list of specified entry's children's ids."""
        if self.is_readable() == False:
            raise NotReadable('Cannot list children with unreadable storage.')
        return self._children(*args, **kwargs)

    def _children(self, id=None, revision=None):
        if id == None:
            id = '__ROOT__'
        return [c.id for c in self._data[id] if not c.id.startswith('__')]

    def get(self, *args, **kwargs):
        """
        Get contents of and entry as they were in a given revision.
        revision==None specifies the current revision.

        If there is no id, return default, unless default is not
        given, in which case raise InvalidID.
        """
        if self.is_readable() == False:
            raise NotReadable('Cannot get entry with unreadable storage.')
        if 'decode' in kwargs:
            decode = kwargs.pop('decode')
        else:
            decode = False
        value = self._get(*args, **kwargs)
        if value != None:
            if decode == True and type(value) != types.UnicodeType:
                return unicode(value, self.encoding)
            elif decode == False and type(value) != types.StringType:
                return value.encode(self.encoding)
        return value

    def _get(self, id, default=InvalidObject, revision=None):
        if id in self._data and self._data[id].value != _EMPTY:
            return self._data[id].value
        elif default == InvalidObject:
            raise InvalidID(id)
        return default

    def set(self, id, value, *args, **kwargs):
        """
        Set the entry contents.
        """
        if self.is_writeable() == False:
            raise NotWriteable('Cannot set entry in unwriteable storage.')
        if type(value) == types.UnicodeType:
            value = value.encode(self.encoding)
        self._set(id, value, *args, **kwargs)

    def _set(self, id, value):
        if id not in self._data:
            raise InvalidID(id)
        if self._data[id].directory == True:
            raise InvalidDirectory(
                'Directory %s cannot have data' % self.parent)
        self._data[id].value = value

class VersionedStorage (Storage):
    """
    This class declares all the methods required by a Storage
    interface that supports versioning.  This implementation just
    keeps the data in a list and uses pickle for persistent
    storage.
    """
    name = 'VersionedStorage'

    def __init__(self, *args, **kwargs):
        Storage.__init__(self, *args, **kwargs)
        self.versioned = True

    def _init(self):
        f = open(os.path.join(self.repo, 'repo.pkl'), 'wb')
        root = Entry(id='__ROOT__', directory=True)
        summary = Entry(id='__COMMIT__SUMMARY__', value='Initial commit')
        body = Entry(id='__COMMIT__BODY__')
        initial_commit = {root.id:root, summary.id:summary, body.id:body}
        d = dict((k,v._objects_to_ids()) for k,v in initial_commit.items())
        pickle.dump([d, copy.deepcopy(d)], f, -1) # [inital tree, working tree]
        f.close()

    def _connect(self):
        try:
            f = open(os.path.join(self.repo, 'repo.pkl'), 'rb')
        except IOError:
            raise ConnectionError(self)
        d = pickle.load(f)
        self._data = [dict((k,v._ids_to_objects(t)) for k,v in t.items())
                      for t in d]
        f.close()

    def _disconnect(self):
        f = open(os.path.join(self.repo, 'repo.pkl'), 'wb')
        pickle.dump([dict((k,v._objects_to_ids())
                          for k,v in t.items()) for t in self._data], f, -1)
        f.close()
        self._data = None

    def _add(self, id, parent=None, directory=False):
        if parent == None:
            parent = '__ROOT__'
        p = self._data[-1][parent]
        self._data[-1][id] = Entry(id, parent=p, directory=directory)

    def _exists(self, id, revision=None):
        if revision == None:
            revision = -1
        else:
            revision = int(revision)
        return id in self._data[revision]

    def _remove(self, id):
        if self._data[-1][id].directory == True \
                and len(self.children(id)) > 0:
            raise DirectoryNotEmpty(id)
        e = self._data[-1].pop(id)
        e.parent.remove(e)

    def _recursive_remove(self, id):
        for entry in reversed(list(self._data[-1][id].traverse())):
            self._remove(entry.id)

    def _ancestors(self, id=None, revision=None):
        if id == None:
            return []
        if revision == None:
            revision = -1
        else:
            revision = int(revision)
        ancestors = []
        stack = [id]
        while len(stack) > 0:
            id = stack.pop(0)
            parent = self._data[revision][id].parent
            if parent != None and not parent.id.startswith('__'):
                ancestor = parent.id
                ancestors.append(ancestor)
                stack.append(ancestor)
        return ancestors

    def _children(self, id=None, revision=None):
        if id == None:
            id = '__ROOT__'
        if revision == None:
            revision = -1
        else:
            revision = int(revision)
        return [c.id for c in self._data[revision][id]
                if not c.id.startswith('__')]

    def _get(self, id, default=InvalidObject, revision=None):
        if revision == None:
            revision = -1
        else:
            revision = int(revision)
        if id in self._data[revision] \
                and self._data[revision][id].value != _EMPTY:
            return self._data[revision][id].value
        elif default == InvalidObject:
            raise InvalidID(id)
        return default

    def _set(self, id, value):
        if id not in self._data[-1]:
            raise InvalidID(id)
        self._data[-1][id].value = value

    def commit(self, *args, **kwargs):
        """
        Commit the current repository, with a commit message string
        summary and body.  Return the name of the new revision.

        If allow_empty == False (the default), raise EmptyCommit if
        there are no changes to commit.
        """
        if self.is_writeable() == False:
            raise NotWriteable('Cannot commit to unwriteable storage.')
        return self._commit(*args, **kwargs)

    def _commit(self, summary, body=None, allow_empty=False):
        if self._data[-1] == self._data[-2] and allow_empty == False:
            raise EmptyCommit
        self._data[-1]["__COMMIT__SUMMARY__"].value = summary
        self._data[-1]["__COMMIT__BODY__"].value = body
        rev = str(len(self._data)-1)
        self._data.append(copy.deepcopy(self._data[-1]))
        return rev

    def revision_id(self, index=None):
        """
        Return the name of the <index>th revision.  The choice of
        which branch to follow when crossing branches/merges is not
        defined.  Revision indices start at 1; ID 0 is the blank
        repository.

        Return None if index==None.

        If the specified revision does not exist, raise InvalidRevision.
        """
        if index == None:
            return None
        try:
            if int(index) != index:
                raise InvalidRevision(index)
        except ValueError:
            raise InvalidRevision(index)
        L = len(self._data) - 1  # -1 b/c of initial commit
        if index >= -L and index <= L:
            return str(index % L)
        raise InvalidRevision(i)

    def changed(self, revision):
        """Return a tuple of lists of ids `(new, modified, removed)` from the
        specified revision to the current situation.
        """
        new = []
        modified = []
        removed = []
        for id,value in self._data[int(revision)].items():
            if id.startswith('__'):
                continue
            if not id in self._data[-1]:
                removed.append(id)
            elif value.value != self._data[-1][id].value:
                modified.append(id)
        for id in self._data[-1]:
            if not id in self._data[int(revision)]:
                new.append(id)
        return (new, modified, removed)


if TESTING == True:
    class StorageTestCase (unittest.TestCase):
        """Test cases for Storage class."""

        Class = Storage

        def __init__(self, *args, **kwargs):
            super(StorageTestCase, self).__init__(*args, **kwargs)
            self.dirname = None

        # this class will be the basis of tests for several classes,
        # so make sure we print the name of the class we're dealing with.
        def _classname(self):
            version = '?'
            try:
                if hasattr(self, 's'):
                    version = self.s.version()
            except:
                pass
            return '%s:%s' % (self.Class.__name__, version)

        def fail(self, msg=None):
            """Fail immediately, with the given message."""
            raise self.failureException, \
                '(%s) %s' % (self._classname(), msg)

        def failIf(self, expr, msg=None):
            "Fail the test if the expression is true."
            if expr: raise self.failureException, \
                '(%s) %s' % (self._classname(), msg)

        def failUnless(self, expr, msg=None):
            """Fail the test unless the expression is true."""
            if not expr: raise self.failureException, \
                '(%s) %s' % (self._classname(), msg)

        def setUp(self):
            """Set up test fixtures for Storage test case."""
            super(StorageTestCase, self).setUp()
            self.dir = Dir()
            self.dirname = self.dir.path
            self.s = self.Class(repo=self.dirname)
            self.assert_failed_connect()
            self.s.init()
            self.s.connect()

        def tearDown(self):
            super(StorageTestCase, self).tearDown()
            self.s.disconnect()
            self.s.destroy()
            self.assert_failed_connect()
            self.dir.cleanup()

        def assert_failed_connect(self):
            try:
                self.s.connect()
                self.fail(
                    "Connected to %(name)s repository before initialising"
                    % vars(self.Class))
            except ConnectionError:
                pass

    class Storage_init_TestCase (StorageTestCase):
        """Test cases for Storage.init method."""

        def test_connect_should_succeed_after_init(self):
            """Should connect after initialization."""
            self.s.connect()

    class Storage_connect_disconnect_TestCase (StorageTestCase):
        """Test cases for Storage.connect and .disconnect methods."""

        def test_multiple_disconnects(self):
            """Should be able to call .disconnect multiple times."""
            self.s.disconnect()
            self.s.disconnect()

    class Storage_add_remove_TestCase (StorageTestCase):
        """Test cases for Storage.add, .remove, and .recursive_remove methods."""

        def test_initially_empty(self):
            """New repository should be empty."""
            self.failUnless(len(self.s.children()) == 0, self.s.children())

        def test_add_identical_rooted(self):
            """Adding entries with the same ID should not increase the number of children.
            """
            for i in range(10):
                self.s.add('some id', directory=False)
                s = sorted(self.s.children())
                self.failUnless(s == ['some id'], s)

        def test_add_rooted(self):
            """Adding entries should increase the number of children (rooted).
            """
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], directory=(i % 2 == 0))
                s = sorted(self.s.children())
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))

        def test_add_nonrooted(self):
            """Adding entries should increase the number of children (nonrooted).
            """
            self.s.add('parent', directory=True)
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent', directory=(i % 2 == 0))
                s = sorted(self.s.children('parent'))
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))
                s = self.s.children()
                self.failUnless(s == ['parent'], s)

        def test_ancestors(self):
            """Check ancestors lists.
            """
            self.s.add('parent', directory=True)
            for i in range(10):
                i_id = str(i)
                self.s.add(i_id, 'parent', directory=True)
                for j in range(10): # add some grandkids
                    j_id = str(20*(i+1)+j)
                    self.s.add(j_id, i_id, directory=(i%2 == 0))
                    ancestors = sorted(self.s.ancestors(j_id))
                    self.failUnless(ancestors == [i_id, 'parent'],
                        'Unexpected ancestors for %s/%s, "%s"'
                        % (i_id, j_id, ancestors))

        def test_children(self):
            """Non-UUID ids should be returned as such.
            """
            self.s.add('parent', directory=True)
            ids = []
            for i in range(10):
                ids.append('parent/%s' % str(i))
                self.s.add(ids[-1], 'parent', directory=(i % 2 == 0))
                s = sorted(self.s.children('parent'))
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))

        def test_add_invalid_directory(self):
            """Should not be able to add children to non-directories.
            """
            self.s.add('parent', directory=False)
            try:
                self.s.add('child', 'parent', directory=False)
                self.fail(
                    '%s.add() succeeded instead of raising InvalidDirectory'
                    % (vars(self.Class)['name']))
            except InvalidDirectory:
                pass
            try:
                self.s.add('child', 'parent', directory=True)
                self.fail(
                    '%s.add() succeeded instead of raising InvalidDirectory'
                    % (vars(self.Class)['name']))
            except InvalidDirectory:
                pass
            self.failUnless(len(self.s.children('parent')) == 0,
                            self.s.children('parent'))

        def test_remove_rooted(self):
            """Removing entries should decrease the number of children (rooted).
            """
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], directory=(i % 2 == 0))
            for i in range(10):
                self.s.remove(ids.pop())
                s = sorted(self.s.children())
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))

        def test_remove_nonrooted(self):
            """Removing entries should decrease the number of children (nonrooted).
            """
            self.s.add('parent', directory=True)
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent', directory=False)#(i % 2 == 0))
            for i in range(10):
                self.s.remove(ids.pop())
                s = sorted(self.s.children('parent'))
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))
                if len(s) > 0:
                    s = self.s.children()
                    self.failUnless(s == ['parent'], s)

        def test_remove_directory_not_empty(self):
            """Removing a non-empty directory entry should raise exception.
            """
            self.s.add('parent', directory=True)
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent', directory=(i % 2 == 0))
            self.s.remove(ids.pop()) # empty directory removal succeeds
            try:
                self.s.remove('parent') # empty directory removal succeeds
                self.fail(
                    "%s.remove() didn't raise DirectoryNotEmpty"
                    % (vars(self.Class)['name']))
            except DirectoryNotEmpty:
                pass

        def test_recursive_remove(self):
            """Recursive remove should empty the tree."""
            self.s.add('parent', directory=True)
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent', directory=True)
                for j in range(10): # add some grandkids
                    self.s.add(str(20*(i+1)+j), ids[-1], directory=(i%2 == 0))
            self.s.recursive_remove('parent')
            s = sorted(self.s.children())
            self.failUnless(s == [], s)

    class Storage_get_set_TestCase (StorageTestCase):
        """Test cases for Storage.get and .set methods."""

        id = 'unlikely id'
        val = 'unlikely value'

        def test_get_default(self):
            """Get should return specified default if id not in Storage.
            """
            ret = self.s.get(self.id, default=self.val)
            self.failUnless(ret == self.val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))

        def test_get_default_exception(self):
            """Get should raise exception if id not in Storage and no default.
            """
            try:
                ret = self.s.get(self.id)
                self.fail(
                    "%s.get() returned %s instead of raising InvalidID"
                    % (vars(self.Class)['name'], ret))
            except InvalidID:
                pass

        def test_get_initial_value(self):
            """Data value should be default before any value has been set.
            """
            self.s.add(self.id, directory=False)
            val = 'UNLIKELY DEFAULT'
            ret = self.s.get(self.id, default=val)
            self.failUnless(ret == val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, val))

        def test_set_exception(self):
            """Set should raise exception if id not in Storage.
            """
            try:
                self.s.set(self.id, self.val)
                self.fail(
                    "%(name)s.set() did not raise InvalidID"
                    % vars(self.Class))
            except InvalidID:
                pass

        def test_set(self):
            """Set should define the value returned by get.
            """
            self.s.add(self.id, directory=False)
            self.s.set(self.id, self.val)
            ret = self.s.get(self.id)
            self.failUnless(ret == self.val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))

        def test_unicode_set(self):
            """Set should define the value returned by get.
            """
            val = u'Fran\xe7ois'
            self.s.add(self.id, directory=False)
            self.s.set(self.id, val)
            ret = self.s.get(self.id, decode=True)
            self.failUnless(type(ret) == types.UnicodeType,
                    "%s.get() returned %s not UnicodeType"
                    % (vars(self.Class)['name'], type(ret)))
            self.failUnless(ret == val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))
            ret = self.s.get(self.id)
            self.failUnless(type(ret) == types.StringType,
                    "%s.get() returned %s not StringType"
                    % (vars(self.Class)['name'], type(ret)))
            s = unicode(ret, self.s.encoding)
            self.failUnless(s == val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], s, self.val))


    class Storage_persistence_TestCase (StorageTestCase):
        """Test cases for Storage.disconnect and .connect methods."""

        id = 'unlikely id'
        val = 'unlikely value'

        def test_get_set_persistence(self):
            """Set should define the value returned by get after reconnect.
            """
            self.s.add(self.id, directory=False)
            self.s.set(self.id, self.val)
            self.s.disconnect()
            self.s.connect()
            ret = self.s.get(self.id)
            self.failUnless(ret == self.val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))

        def test_empty_get_set_persistence(self):
            """After empty set, get may return either an empty string or default.
            """
            self.s.add(self.id, directory=False)
            self.s.set(self.id, '')
            self.s.disconnect()
            self.s.connect()
            default = 'UNLIKELY DEFAULT'
            ret = self.s.get(self.id, default=default)
            self.failUnless(ret in ['', default],
                    "%s.get() returned %s not in %s"
                    % (vars(self.Class)['name'], ret, ['', default]))

        def test_add_nonrooted_persistence(self):
            """Adding entries should increase the number of children after reconnect.
            """
            self.s.add('parent', directory=True)
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent', directory=(i % 2 == 0))
            self.s.disconnect()
            self.s.connect()
            s = sorted(self.s.children('parent'))
            self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))
            s = self.s.children()
            self.failUnless(s == ['parent'], s)

    class VersionedStorageTestCase (StorageTestCase):
        """Test cases for VersionedStorage methods."""

        Class = VersionedStorage

    class VersionedStorage_commit_TestCase (VersionedStorageTestCase):
        """Test cases for VersionedStorage.commit and revision_ids methods."""

        id = 'unlikely id'
        val = 'Some value'
        commit_msg = 'Committing something interesting'
        commit_body = 'Some\nlonger\ndescription\n'

        def _setup_for_empty_commit(self):
            """
            Initialization might add some files to version control, so
            commit those first, before testing the empty commit
            functionality.
            """
            try:
                self.s.commit('Added initialization files')
            except EmptyCommit:
                pass
                
        def test_revision_id_exception(self):
            """Invalid revision id should raise InvalidRevision.
            """
            try:
                rev = self.s.revision_id('highly unlikely revision id')
                self.fail(
                    "%s.revision_id() didn't raise InvalidRevision, returned %s."
                    % (vars(self.Class)['name'], rev))
            except InvalidRevision:
                pass

        def test_empty_commit_raises_exception(self):
            """Empty commit should raise exception.
            """
            self._setup_for_empty_commit()
            try:
                self.s.commit(self.commit_msg, self.commit_body)
                self.fail(
                    "Empty %(name)s.commit() didn't raise EmptyCommit."
                    % vars(self.Class))
            except EmptyCommit:
                pass

        def test_empty_commit_allowed(self):
            """Empty commit should _not_ raise exception if allow_empty=True.
            """
            self._setup_for_empty_commit()
            self.s.commit(self.commit_msg, self.commit_body,
                          allow_empty=True)

        def test_commit_revision_ids(self):
            """Commit / revision_id should agree on revision ids.
            """
            def val(i):
                return '%s:%d' % (self.val, i+1)
            self.s.add(self.id, directory=False)
            revs = []
            for i in range(10):
                self.s.set(self.id, val(i))
                revs.append(self.s.commit('%s: %d' % (self.commit_msg, i),
                                          self.commit_body))
            for i in range(10):
                rev = self.s.revision_id(i+1)
                self.failUnless(rev == revs[i],
                                "%s.revision_id(%d) returned %s not %s"
                                % (vars(self.Class)['name'], i+1, rev, revs[i]))
            for i in range(-1, -9, -1):
                rev = self.s.revision_id(i)
                self.failUnless(rev == revs[i],
                                "%s.revision_id(%d) returned %s not %s"
                                % (vars(self.Class)['name'], i, rev, revs[i]))

        def test_get_previous_version(self):
            """Get should be able to return the previous version.
            """
            def val(i):
                return '%s:%d' % (self.val, i+1)
            self.s.add(self.id, directory=False)
            revs = []
            for i in range(10):
                self.s.set(self.id, val(i))
                revs.append(self.s.commit('%s: %d' % (self.commit_msg, i),
                                          self.commit_body))
            for i in range(10):
                ret = self.s.get(self.id, revision=revs[i])
                self.failUnless(ret == val(i),
                                "%s.get() returned %s not %s for revision %s"
                                % (vars(self.Class)['name'], ret, val(i), revs[i]))

        def test_get_previous_children(self):
            """Children list should be revision dependent.
            """
            self.s.add('parent', directory=True)
            revs = []
            cur_children = []
            children = []
            for i in range(10):
                new_child = str(i)
                self.s.add(new_child, 'parent')
                self.s.set(new_child, self.val)
                revs.append(self.s.commit('%s: %d' % (self.commit_msg, i),
                                          self.commit_body))
                cur_children.append(new_child)
                children.append(list(cur_children))
            for i in range(10):
                ret = sorted(self.s.children('parent', revision=revs[i]))
                self.failUnless(ret == children[i],
                                "%s.children() returned %s not %s for revision %s"
                                % (vars(self.Class)['name'], ret,
                                   children[i], revs[i]))

    class VersionedStorage_changed_TestCase (VersionedStorageTestCase):
        """Test cases for VersionedStorage.changed() method."""

        def test_changed(self):
            """Changed lists should reflect past activity"""
            self.s.add('dir', directory=True)
            self.s.add('modified', parent='dir')
            self.s.set('modified', 'some value to be modified')
            self.s.add('moved', parent='dir')
            self.s.set('moved', 'this entry will be moved')
            self.s.add('removed', parent='dir')
            self.s.set('removed', 'this entry will be deleted')
            revA = self.s.commit('Initial state')
            self.s.add('new', parent='dir')
            self.s.set('new', 'this entry is new')
            self.s.set('modified', 'a new value')
            self.s.remove('moved')
            self.s.add('moved2', parent='dir')
            self.s.set('moved2', 'this entry will be moved')
            self.s.remove('removed')
            revB = self.s.commit('Final state')
            new,mod,rem = self.s.changed(revA)
            self.failUnless(sorted(new) == ['moved2', 'new'],
                            'Unexpected new: %s' % new)
            self.failUnless(mod == ['modified'],
                            'Unexpected modified: %s' % mod)
            self.failUnless(sorted(rem) == ['moved', 'removed'],
                            'Unexpected removed: %s' % rem)

    def make_storage_testcase_subclasses(storage_class, namespace):
        """Make StorageTestCase subclasses for storage_class in namespace."""
        storage_testcase_classes = [
            c for c in (
                ob for ob in globals().values() if isinstance(ob, type))
            if issubclass(c, StorageTestCase) \
                and c.Class == Storage]

        for base_class in storage_testcase_classes:
            testcase_class_name = storage_class.__name__ + base_class.__name__
            testcase_class_bases = (base_class,)
            testcase_class_dict = dict(base_class.__dict__)
            testcase_class_dict['Class'] = storage_class
            testcase_class = type(
                testcase_class_name, testcase_class_bases, testcase_class_dict)
            setattr(namespace, testcase_class_name, testcase_class)

    def make_versioned_storage_testcase_subclasses(storage_class, namespace):
        """Make VersionedStorageTestCase subclasses for storage_class in namespace."""
        storage_testcase_classes = [
            c for c in (
                ob for ob in globals().values() if isinstance(ob, type))
            if ((issubclass(c, StorageTestCase) \
                     and c.Class == Storage)
                or
                (issubclass(c, VersionedStorageTestCase) \
                     and c.Class == VersionedStorage))]

        for base_class in storage_testcase_classes:
            testcase_class_name = storage_class.__name__ + base_class.__name__
            testcase_class_bases = (base_class,)
            testcase_class_dict = dict(base_class.__dict__)
            testcase_class_dict['Class'] = storage_class
            testcase_class = type(
                testcase_class_name, testcase_class_bases, testcase_class_dict)
            setattr(namespace, testcase_class_name, testcase_class)

    make_storage_testcase_subclasses(VersionedStorage, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
