# Copyright

"""
Abstract bug repository data storage to easily support multiple backends.
"""

import copy
import os
import pickle

from libbe.error import NotSupported
from libbe.util.tree import Tree
from libbe.util import InvalidObject
from libbe import TESTING

if TESTING == True:
    import doctest
    import os.path
    import sys
    import unittest

    from libbe.util.utility import Dir

class ConnectionError (Exception):
    pass

class InvalidID (KeyError):
    pass

class InvalidRevision (KeyError):
    pass

class EmptyCommit(Exception):
    def __init__(self):
        Exception.__init__(self, 'No changes to commit')

class Entry (Tree):
    def __init__(self, id, value=None, parent=None, children=None):
        if children == None:
            Tree.__init__(self)
        else:
            Tree.__init__(self, children)
        self.id = id
        self.value = value
        self.parent = parent
        if self.parent != None:
            parent.append(self)

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

    def __init__(self, repo, options=None):
        self.repo = repo
        self.options = options
        self.read_only = False
        self.versioned = False
        self.can_init = True

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, id(self))

    def __repr__(self):
        return str(self)

    def version(self):
        """Return a version string for this backend."""
        return '0'

    def init(self):
        """Create a new storage repository."""
        if self.can_init == False:
            raise NotSupported('init',
                               'Cannot initialize this repository format.')
        if self.read_only == True:
            raise NotSupported('init', 'Cannot initialize read only storage.')
        return self._init()

    def _init(self):
        f = open(self.repo, 'wb')
        root = Entry(id='__ROOT__')
        d = {root.id:root}
        pickle.dump(dict((k,v._objects_to_ids()) for k,v in d.items()), f, -1)
        f.close()

    def destroy(self):
        """Remove the storage repository."""
        if self.read_only == True:
            raise NotSupported('destroy', 'Cannot destroy read only storage.')
        return self._destroy()

    def _destroy(self):
        os.remove(self.repo)

    def connect(self):
        """Open a connection to the repository."""
        try:
            f = open(self.repo, 'rb')
        except IOError:
            raise ConnectionError(self)
        d = pickle.load(f)
        self._data = dict((k,v._ids_to_objects(d)) for k,v in d.items())
        f.close()

    def disconnect(self):
        """Close the connection to the repository."""
        if self.read_only == True:
            return
        f = open(self.repo, 'wb')
        pickle.dump(dict((k,v._objects_to_ids())
                         for k,v in self._data.items()), f, -1)
        f.close()
        self._data = None

    def add(self, *args, **kwargs):
        """Add an entry"""
        if self.read_only == True:
            raise NotSupported('add', 'Cannot add entry to read only storage.')
        self._add(*args, **kwargs)

    def _add(self, id, parent=None):
        if parent == None:
            parent = '__ROOT__'
        p = self._data[parent]
        self._data[id] = Entry(id, parent=p)

    def remove(self, *args, **kwargs):
        """Remove an entry."""
        if self.read_only == True:
            raise NotSupported('remove',
                               'Cannot remove entry from read only storage.')
        self._remove(*args, **kwargs)

    def _remove(self, id):
        e = self._data.pop(id)
        e.parent.remove(e)

    def recursive_remove(self, *args, **kwargs):
        """Remove an entry and all its decendents."""
        if self.read_only == True:
            raise NotSupported('recursive_remove',
                               'Cannot remove entries from read only storage.')
        self._recursive_remove(*args, **kwargs)

    def _recursive_remove(self, id):
        for entry in self._data[id].traverse():
            self._remove(entry.id)

    def children(self, id=None, revision=None):
        """Return a list of specified entry's children's ids."""
        if id == None:
            id = '__ROOT__'
        return [c.id for c in self._data[id] if not c.id.startswith('__')]

    def get(self, id, default=InvalidObject, revision=None):
        """
        Get contents of and entry as they were in a given revision.
        revision==None specifies the current revision.

        If there is no id, return default, unless default is not
        given, in which case raise InvalidID.
        """
        if id in self._data:
            return self._data[id].value
        elif default == InvalidObject:
            raise InvalidID(id)
        return default

    def set(self, *args, **kwargs):
        """
        Set the entry contents.
        """
        if self.read_only == True:
            raise NotSupported('set', 'Cannot set entry in read only storage.')
        self._set(*args, **kwargs)

    def _set(self, id, value):
        if id not in self._data:
            raise InvalidID(id)
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
        f = open(self.repo, 'wb')
        root = Entry(id='__ROOT__')
        summary = Entry(id='__COMMIT__SUMMARY__', value='Initial commit')
        body = Entry(id='__COMMIT__BODY__')
        initial_commit = {root.id:root, summary.id:summary, body.id:body}
        d = dict((k,v._objects_to_ids()) for k,v in initial_commit.items())
        pickle.dump([d, copy.deepcopy(d)], f, -1) # [inital tree, working tree]
        f.close()

    def connect(self):
        """Open a connection to the repository."""
        try:
            f = open(self.repo, 'rb')
        except IOError:
            raise ConnectionError(self)
        d = pickle.load(f)
        self._data = [dict((k,v._ids_to_objects(t)) for k,v in t.items())
                      for t in d]
        f.close()

    def disconnect(self):
        """Close the connection to the repository."""
        if self.read_only == True:
            return
        f = open(self.repo, 'wb')
        pickle.dump([dict((k,v._objects_to_ids())
                          for k,v in t.items()) for t in self._data], f, -1)
        f.close()
        self._data = None

    def _add(self, id, parent=None):
        if parent == None:
            parent = '__ROOT__'
        p = self._data[-1][parent]
        self._data[-1][id] = Entry(id, parent=p)

    def _remove(self, id):
        e = self._data[-1].pop(id)
        e.parent.remove(e)

    def _recursive_remove(self, id):
        for entry in self._data[-1][id].traverse():
            self._remove(entry.id)

    def children(self, id=None, revision=None):
        """Return a list of specified entry's children's ids."""
        if id == None:
            id = '__ROOT__'
        if revision == None:
            revision = -1
        return [c.id for c in self._data[revision][id]
                if not c.id.startswith('__')]

    def get(self, id, default=InvalidObject, revision=None):
        """
        Get contents of and entry as they were in a given revision.
        revision==None specifies the current revision.

        If there is no id, return default, unless default is not
        given, in which case raise InvalidID.
        """
        if revision == None:
            revision = -1
        if id in self._data[revision]:
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
        if self.read_only == True:
            raise NotSupported('commit', 'Cannot commit to read only storage.')
        return self._commit(*args, **kwargs)

    def _commit(self, summary, body=None, allow_empty=False):
        if self._data[-1] == self._data[-2] and allow_empty == False:
            raise EmptyCommit
        self._data[-1]["__COMMIT__SUMMARY__"].value = summary
        self._data[-1]["__COMMIT__BODY__"].value = body
        rev = len(self._data)-1
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
            return index % L
        raise InvalidRevision(i)

if TESTING == True:
    class StorageTestCase (unittest.TestCase):
        """Test cases for base Storage class."""

        Class = Storage

        def __init__(self, *args, **kwargs):
            super(StorageTestCase, self).__init__(*args, **kwargs)
            self.dirname = None

        def setUp(self):
            """Set up test fixtures for Storage test case."""
            super(StorageTestCase, self).setUp()
            self.dir = Dir()
            self.dirname = self.dir.path
            self.s = self.Class(repo=os.path.join(self.dirname, 'repo.pkl'))
            self.assert_failed_connect()
            self.s.init()
            self.s.connect()

        def tearDown(self):
            super(StorageTestCase, self).tearDown()
            self.s.disconnect()
            self.s.destroy()
            self.assert_failed_connect()

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

    class Storage_add_remove_TestCase (StorageTestCase):
        """Test cases for Storage.add, .remove, and .recursive_remove methods."""

        def test_initially_empty(self):
            """New repository should be empty."""
            self.failUnless(len(self.s.children()) == 0, self.s.children())

        def test_add_rooted(self):
            """
            Adding entries should increase the number of children (rooted).
            """
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1])
                s = sorted(self.s.children())
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))

        def test_add_nonrooted(self):
            """
            Adding entries should increase the number of children (nonrooted).
            """
            self.s.add('parent')
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent')
                s = sorted(self.s.children('parent'))
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))
                s = self.s.children()
                self.failUnless(s == ['parent'], s)
                
        def test_remove_rooted(self):
            """
            Removing entries should decrease the number of children (rooted).
            """
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1])
            for i in range(10):
                self.s.remove(ids.pop())
                s = sorted(self.s.children())
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))

        def test_remove_nonrooted(self):
            """
            Removing entries should decrease the number of children (nonrooted).
            """
            self.s.add('parent')
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent')
            for i in range(10):
                self.s.remove(ids.pop())
                s = sorted(self.s.children('parent'))
                self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))
                s = self.s.children()
                self.failUnless(s == ['parent'], s)

        def test_recursive_remove(self):
            """
            Recursive remove should empty the tree.
            """
            self.s.add('parent')
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent')
                for j in range(10): # add some grandkids
                    self.s.add(str(20*i+j), ids[-i])
            self.s.recursive_remove('parent')
            s = sorted(self.s.children())
            self.failUnless(s == [], s)

    class Storage_get_set_TestCase (StorageTestCase):
        """Test cases for Storage.get and .set methods."""

        id = 'unlikely id'
        val = 'unlikely value'

        def test_get_default(self):
            """
            Get should return specified default if id not in Storage.
            """
            ret = self.s.get(self.id, default=self.val)
            self.failUnless(ret == self.val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))

        def test_get_default_exception(self):
            """
            Get should raise exception if id not in Storage and no default.
            """
            try:
                ret = self.s.get(self.id)
                self.fail(
                    "%s.get() returned %s instead of raising InvalidID"
                    % (vars(self.Class)['name'], ret))
            except InvalidID:
                pass

        def test_get_initial_value(self):
            """
            Data value should be None before any value has been set.
            """
            self.s.add(self.id)
            ret = self.s.get(self.id)
            self.failUnless(ret == None,
                    "%s.get() returned %s not None"
                    % (vars(self.Class)['name'], ret))

        def test_set_exception(self):
            """
            Set should raise exception if id not in Storage.
            """
            try:
                self.s.set(self.id, self.val)
                self.fail(
                    "%(name)s.set() did not raise InvalidID"
                    % vars(self.Class))
            except InvalidID:
                pass

        def test_set(self):
            """
            Set should define the value returned by get.
            """
            self.s.add(self.id)
            self.s.set(self.id, self.val)
            ret = self.s.get(self.id)
            self.failUnless(ret == self.val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))

    class Storage_persistence_TestCase (StorageTestCase):
        """Test cases for Storage.disconnect and .connect methods."""

        id = 'unlikely id'
        val = 'unlikely value'

        def test_get_set_persistence(self):
            """
            Set should define the value returned by get after reconnect.
            """
            self.s.add(self.id)
            self.s.set(self.id, self.val)
            self.s.disconnect()
            self.s.connect()
            ret = self.s.get(self.id)
            self.failUnless(ret == self.val,
                    "%s.get() returned %s not %s"
                    % (vars(self.Class)['name'], ret, self.val))

        def test_add_nonrooted_persistence(self):
            """
            Adding entries should increase the number of children after reconnect.
            """
            self.s.add('parent')
            ids = []
            for i in range(10):
                ids.append(str(i))
                self.s.add(ids[-1], 'parent')
            self.s.disconnect()
            self.s.connect()
            s = sorted(self.s.children('parent'))
            self.failUnless(s == ids, '\n  %s\n  !=\n  %s' % (s, ids))
            s = self.s.children()
            self.failUnless(s == ['parent'], s)

    class VersionedStorageTestCase (StorageTestCase):
        """Test cases for base VersionedStorage class."""

        Class = VersionedStorage

    class VersionedStorage_commit_TestCase (VersionedStorageTestCase):
        """Test cases for VersionedStorage methods."""

        id = 'I' #unlikely id'
        val = 'X'
        commit_msg = 'C' #ommitting something interesting'
        commit_body = 'B' #ome\nlonger\ndescription\n'

        def test_revision_id_exception(self):
            """
            Invalid revision id should raise InvalidRevision.
            """
            try:
                rev = self.s.revision_id('highly unlikely revision id')
                self.fail(
                    "%s.revision_id() didn't raise InvalidRevision, returned %s."
                    % (vars(self.Class)['name'], rev))
            except InvalidRevision:
                pass

        def test_empty_commit_raises_exception(self):
            """
            Empty commit should raise exception.
            """
            try:
                self.s.commit(self.commit_msg, self.commit_body)
                self.fail(
                    "Empty %(name)s.commit() didn't raise EmptyCommit."
                    % vars(self.Class))
            except EmptyCommit:
                pass

        def test_empty_commit_allowed(self):
            """
            Empty commit should _not_ raise exception if allow_empty=True.
            """
            self.s.commit(self.commit_msg, self.commit_body,
                          allow_empty=True)

        def test_commit_revision_ids(self):
            """
            Commit / revision_id should agree on revision ids.
            """
            revs = []
            for s in range(10):
                revs.append(self.s.commit(self.commit_msg,
                                          self.commit_body,
                                          allow_empty=True))
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
            """
            Get should be able to return the previous version.
            """
            def val(i):
                return '%s:%d' % (self.val, i+1)
            self.s.add(self.id)
            revs = []
            for i in range(10):
                self.s.set(self.id, val(i))
                revs.append(self.s.commit('%s: %d' % (self.commit_msg, i),
                                          self.commit_body))
            for i in range(10):
                ret = self.s.get(self.id, revision=revs[i])
                self.failUnless(ret == val(i),
                                "%s.get() returned %s not %s for revision %d"
                                % (vars(self.Class)['name'], ret, val(i), revs[i]))
        
    def make_storage_testcase_subclasses(storage_class, namespace):
        """Make StorageTestCase subclasses for storage_class in namespace."""
        storage_testcase_classes = [
            c for c in (
                ob for ob in globals().values() if isinstance(ob, type))
            if issubclass(c, StorageTestCase) \
                and not issubclass(c, VersionedStorageTestCase)]

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
            if issubclass(c, StorageTestCase)]

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
