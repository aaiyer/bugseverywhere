# Copyright (C) 2008-2010 Gianluca Montecchi <gian@grys.it>
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
Handle ID creation and parsing.
"""

import os.path
import re

import libbe

if libbe.TESTING == True:
    import doctest
    import sys
    import unittest

try:
    from uuid import uuid4 # Python >= 2.5
    def uuid_gen():
        id = uuid4()
        idstr = id.urn
        start = "urn:uuid:"
        assert idstr.startswith(start)
        return idstr[len(start):]
except ImportError:
    import os
    import sys
    from subprocess import Popen, PIPE

    def uuid_gen():
        # Shell-out to system uuidgen
        args = ['uuidgen', 'r']
        try:
            if sys.platform != "win32":
                q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            else:
                # win32 don't have os.execvp() so have to run command in a shell
                q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                          shell=True, cwd=cwd)
        except OSError, e :
            strerror = "%s\nwhile executing %s" % (e.args[1], args)
            raise OSError, strerror
        output, error = q.communicate()
        status = q.wait()
        if status != 0:
            strerror = "%s\nwhile executing %s" % (status, args)
            raise Exception, strerror
        return output.rstrip('\n')


HIERARCHY = ['bugdir', 'bug', 'comment']


class MultipleIDMatches (ValueError):
    def __init__(self, id, common, matches):
        msg = ('More than one id matches %s.  '
               'Please be more specific (%s/*).\n%s' % (id, common, matches))
        ValueError.__init__(self, msg)
        self.id = id
        self.common = common
        self.matches = matches

class NoIDMatches (KeyError):
    def __init__(self, id, possible_ids, msg=None):
        KeyError.__init__(self, id)
        self.id = id
        self.possible_ids = possible_ids
        self.msg = msg
    def __str__(self):
        if self.msg == None:
            return 'No id matches %s.\n%s' % (self.id, self.possible_ids)
        return self.msg

class InvalidIDStructure (KeyError):
    def __init__(self, id, msg=None):
        KeyError.__init__(self, id)
        self.id = id
        self.msg = msg
    def __str__(self):
        if self.msg == None:
            return 'Invalid id structure "%s"' % self.id
        return self.msg

def _assemble(args, check_length=False):
    args = list(args)
    for i,arg in enumerate(args):
        if arg == None:
            args[i] = ''
    id = '/'.join(args)
    if check_length == True:
        assert len(args) > 0, args
        if len(args) > 3:
            raise InvalidIDStructure(id, '%d > 3 levels in "%s"' % (len(args), id))
    return id

def _split(id, check_length=False):
    args = id.split('/')
    for i,arg in enumerate(args):
        if arg == '':
            args[i] = None
    if check_length == True:
        assert len(args) > 0, args
        if len(args) > 3:
            raise InvalidIDStructure(id, '%d > 3 levels in "%s"' % (len(args), id))
    return args

def _truncate(uuid, other_uuids, min_length=3):
    chars = min_length
    for id in other_uuids:
        if id == uuid:
            continue
        while (id[:chars] == uuid[:chars]):
            chars+=1
    return uuid[:chars]

def _expand(truncated_id, common, other_ids):
    other_ids = list(other_ids)
    if len(other_ids) == 0:
        raise NoIDMatches(truncated_id, other_ids)
    if truncated_id == None:
        if len(other_ids) == 1:
            return other_ids[0]
        raise MultipleIDMatches(truncated_id, common, other_ids)
    matches = []
    other_ids = list(other_ids)
    for id in other_ids:
        if id.startswith(truncated_id):
            matches.append(id)
    if len(matches) > 1:
        raise MultipleIDMatches(truncated_id, common, matches)
    if len(matches) == 0:
        raise NoIDMatches(truncated_id, other_ids)
    return matches[0]


class ID (object):
    """
    IDs have several formats specialized for different uses.

    In storage, all objects are represented by their uuid alone,
    because that is the simplest globally unique identifier.  You can
    generate ids of this sort with the .storage() method.  Because an
    object's storage may be distributed across several chunks, and the
    chunks may not have their own uuid, we generate chunk ids by
    prepending the objects uuid to the chunk name.  The user id types
    do not support this chunk extension feature.

    For users, the full uuids are a bit overwhelming, so we truncate
    them while retaining local uniqueness (with regards to the other
    objects currently in storage).  We also prepend truncated parent
    ids for two reasons:
      (1) so that a user can locate the repository containing the
          referenced object.  It would be hard to find bug 'XYZ' if
          that's all you knew.  Much easier with 'ABC/XYZ', where ABC
          is the bugdir.  Each project can publish a list of bugdir-id
          - to - location mappings, e.g.
            ABC...(full uuid)...DEF   https://server.com/projectX/be/
          which is easier than publishing all-object-ids-to-location
          mappings.
      (2) because it's easier to generate and parse truncated ids if
          you don't have to fetch all the ids in the storage
          repository, but can restrict yourself to a specific branch.
    You can generate ids of this sort with the .user() method,
    although in order to preform the truncation, your object (and its
    parents must define a .sibling_uuids() method.


    While users can use the convenient short user ids in the short
    term, the truncation will inevitably lead to name collision.  To
    avoid that, we provide a non-truncated form of the short user ids
    via the .long_user() method.  These long user ids should be
    converted to short user ids by intelligent user interfaces.

    Related tools:
      * get uuids back out of the user ids:
        parse_user()
      * scan text for user ids & convert to long user ids:
        short_to_long_user()
      * scan text for long user ids & convert to short user ids:
        long_to_short_user()

    Supported types: 'bugdir', 'bug', 'comment'
    """
    def __init__(self, object, type):
        self._object = object
        self._type = type
        assert self._type in HIERARCHY, self._type

    def storage(self, *args):
        return _assemble([self._object.uuid]+list(args))

    def _ancestors(self):
        ret = [self._object]
        index = HIERARCHY.index(self._type)
        if index == 0:
            return ret
        o = self._object
        for i in range(index, 0, -1):
            parent_name = HIERARCHY[i-1]
            o = getattr(o, parent_name, None)
            ret.insert(0, o)
        return ret

    def long_user(self):
        return _assemble([o.uuid for o in self._ancestors()],
                         check_length=True)

    def user(self):
        ids = []
        for o in self._ancestors():
            if o == None:
                ids.append(None)
            else:
                ids.append(_truncate(o.uuid, o.sibling_uuids()))
        return _assemble(ids, check_length=True)

def child_uuids(child_storage_ids):
    """
    Extract uuid children from other children generated by the
    ID.storage() method.
    >>> list(child_uuids(['abc123/values', '123abc', '123def']))
    ['123abc', '123def']
    """
    for id in child_storage_ids:
        fields = _split(id)
        if len(fields) == 1:
            yield fields[0]

def long_to_short_user(bugdirs, id):
    ids = _split(id, check_length=True)
    bugdir = [bd for bd in bugdirs if bd.uuid == ids[0]][0]
    objects = [bugdir]
    if len(ids) >= 2:
        bug = bugdir.bug_from_uuid(ids[1])
        objects.append(bug)
    if len(ids) >= 3:
        comment = bug.comment_from_uuid(ids[2])
        objects.append(comment)
    for i,obj in enumerate(objects):
        ids[i] = _truncate(ids[i], obj.sibling_uuids())
    return _assemble(ids)

def short_to_long_user(bugdirs, id):
    ids = _split(id, check_length=True)
    ids[0] = _expand(ids[0], common=None,
                     other_ids=[bd.uuid for bd in bugdirs])
    if len(ids) == 1:
        return _assemble(ids)
    bugdir = [bd for bd in bugdirs if bd.uuid == ids[0]][0]
    ids[1] = _expand(ids[1], common=bugdir.id.user(),
                     other_ids=bugdir.uuids())
    if len(ids) == 2:
        return _assemble(ids)
    bug = bugdir.bug_from_uuid(ids[1])
    ids[2] = _expand(ids[2], common=bug.id.user(),
                     other_ids=bug.uuids())
    return _assemble(ids)


REGEXP = '#([-a-f0-9]*)(/[-a-g0-9]*)?(/[-a-g0-9]*)?#'

class IDreplacer (object):
    def __init__(self, bugdirs, replace_fn):
        self.bugdirs = bugdirs
        self.replace_fn = replace_fn
    def __call__(self, match):
        ids = []
        for m in match.groups():
            if m == None:
                m = ''
            ids.append(m)
        return '#' + self.replace_fn(self.bugdirs, ''.join(ids)) + '#'

def short_to_long_text(bugdirs, text):
    return re.sub(REGEXP, IDreplacer(bugdirs, short_to_long_user), text)

def long_to_short_text(bugdirs, text):
    return re.sub(REGEXP, IDreplacer(bugdirs, long_to_short_user), text)

def residual(base, fragment):
    """
    >>> residual('ABC/DEF/', '//GHI')
    ('//', 'GHI')
    >>> residual('ABC/DEF/', '/D/GHI')
    ('/D/', 'GHI')
    >>> residual('ABC/DEF', 'A/D/GHI')
    ('A/D/', 'GHI')
    >>> residual('ABC/DEF', 'A/D/GHI/JKL')
    ('A/D/', 'GHI/JKL')
    """
    base = base.rstrip('/') + '/'
    ids = fragment.split('/')
    base_count = base.count('/')
    root_ids = ids[:base_count] + ['']
    residual_ids = ids[base_count:]
    return ('/'.join(root_ids), '/'.join(residual_ids))

def _parse_user(id):
    """
    >>> _parse_user('ABC/DEF/GHI') == \\
    ...     {'bugdir':'ABC', 'bug':'DEF', 'comment':'GHI', 'type':'comment'}
    True
    >>> _parse_user('ABC/DEF') == \\
    ...     {'bugdir':'ABC', 'bug':'DEF', 'type':'bug'}
    True
    >>> _parse_user('ABC') == \\
    ...     {'bugdir':'ABC', 'type':'bugdir'}
    True
    >>> _parse_user('') == \\
    ...     {'bugdir':None, 'type':'bugdir'}
    True
    >>> _parse_user('/') == \\
    ...     {'bugdir':None, 'bug':None, 'type':'bug'}
    True
    >>> _parse_user('/DEF/') == \\
    ...     {'bugdir':None, 'bug':'DEF', 'comment':None, 'type':'comment'}
    True
    >>> _parse_user('a/b/c/d')
    Traceback (most recent call last): 
      ...
    InvalidIDStructure: 4 > 3 levels in "a/b/c/d"
    """
    ret = {}
    args = _split(id, check_length=True)
    for i,(type,arg) in enumerate(zip(HIERARCHY, args)):
        if arg != None and len(arg) == 0:
            raise InvalidIDStructure(
                id, 'Invalid %s part %d "%s" of id "%s"' % (type, i, arg, id))
        ret['type'] = type
        ret[type] = arg
    return ret

def parse_user(bugdir, id):
    long_id = short_to_long_user([bugdir], id)
    return _parse_user(long_id)

if libbe.TESTING == True:
    class UUIDtestCase(unittest.TestCase):
        def testUUID_gen(self):
            id = uuid_gen()
            self.failUnless(len(id) == 36, 'invalid UUID "%s"' % id)

    class DummyObject (object):
        def __init__(self, uuid, parent=None, siblings=[]):
            self.uuid = uuid
            self._siblings = siblings
            if parent == None:
                type_i = 0
            else:
                assert parent.type in HIERARCHY, parent
                setattr(self, parent.type, parent)
                type_i = HIERARCHY.index(parent.type) + 1
            self.type = HIERARCHY[type_i]
            self.id = ID(self, self.type)
        def sibling_uuids(self):
            return self._siblings

    class IDtestCase(unittest.TestCase):
        def setUp(self):
            self.bugdir = DummyObject('1234abcd')
            self.bug = DummyObject('abcdef', self.bugdir, ['a1234', 'ab9876'])
            self.comment = DummyObject('12345678', self.bug, ['1234abcd', '1234cdef'])
            self.bd_id = self.bugdir.id
            self.b_id = self.bug.id
            self.c_id = self.comment.id
        def test_storage(self):
            self.failUnless(self.bd_id.storage() == self.bugdir.uuid,
                            self.bd_id.storage())
            self.failUnless(self.b_id.storage() == self.bug.uuid,
                            self.b_id.storage())
            self.failUnless(self.c_id.storage() == self.comment.uuid,
                            self.c_id.storage())
            self.failUnless(self.bd_id.storage('x', 'y', 'z') == \
                                '1234abcd/x/y/z',
                            self.bd_id.storage('x', 'y', 'z'))
        def test_long_user(self):
            self.failUnless(self.bd_id.long_user() == self.bugdir.uuid,
                            self.bd_id.long_user())
            self.failUnless(self.b_id.long_user() == \
                                '/'.join([self.bugdir.uuid, self.bug.uuid]),
                            self.b_id.long_user())
            self.failUnless(self.c_id.long_user() ==
                                '/'.join([self.bugdir.uuid, self.bug.uuid,
                                          self.comment.uuid]),
                            self.c_id.long_user)
        def test_user(self):
            self.failUnless(self.bd_id.user() == '123',
                            self.bd_id.user())
            self.failUnless(self.b_id.user() == '123/abc',
                            self.b_id.user())
            self.failUnless(self.c_id.user() == '123/abc/12345',
                            self.c_id.user())

    class ShortLongParseTestCase(unittest.TestCase):
        def setUp(self):
            self.bugdir = DummyObject('1234abcd')
            self.bug = DummyObject('abcdef', self.bugdir, ['a1234', 'ab9876'])
            self.comment = DummyObject('12345678', self.bug, ['1234abcd', '1234cdef'])
            self.bd_id = self.bugdir.id
            self.b_id = self.bug.id
            self.c_id = self.comment.id
            self.bugdir.bug_from_uuid = lambda uuid: self.bug
            self.bugdir.uuids = lambda : self.bug.sibling_uuids() + [self.bug.uuid]
            self.bug.comment_from_uuid = lambda uuid: self.comment
            self.bug.uuids = lambda : self.comment.sibling_uuids() + [self.comment.uuid]
            self.short = 'bla bla #123/abc# bla bla #123/abc/12345# bla bla'
            self.long = 'bla bla #1234abcd/abcdef# bla bla #1234abcd/abcdef/12345678# bla bla'
            self.short_id_parse_pairs = [
                ('', {'bugdir':'1234abcd', 'type':'bugdir'}),
                ('123/abc', {'bugdir':'1234abcd', 'bug':'abcdef',
                             'type':'bug'}),
                ('123/abc/12345', {'bugdir':'1234abcd', 'bug':'abcdef',
                                   'comment':'12345678', 'type':'comment'}),
                ]
            self.short_id_exception_pairs = [
                ('z', NoIDMatches('z', ['1234abcd'])),
                ('///', InvalidIDStructure(
                        '///', msg='4 > 3 levels in "///"')),
                ('/', MultipleIDMatches(
                        None, '123', ['a1234', 'ab9876', 'abcdef'])),
                ('123/', MultipleIDMatches(
                        None, '123', ['a1234', 'ab9876', 'abcdef'])),
                ('123/abc/', MultipleIDMatches(
                        None, '123/abc', ['1234abcd','1234cdef','12345678'])),
                ]
        def test_short_to_long_text(self):
            self.failUnless(short_to_long_text([self.bugdir], self.short) == self.long,
                            '\n' + self.short + '\n' + short_to_long_text([self.bugdir], self.short) + '\n' + self.long)
        def test_long_to_short_text(self):
            self.failUnless(long_to_short_text([self.bugdir], self.long) == self.short,
                            '\n' + long_to_short_text([self.bugdir], self.long) + '\n' + self.short)
        def test_parse_user(self):
            for short_id,parsed in self.short_id_parse_pairs:
                ret = parse_user(self.bugdir, short_id)
                self.failUnless(ret == parsed,
                                'got %s\nexpected %s' % (ret, parsed))
        def test_parse_user_exceptions(self):
            for short_id,exception in self.short_id_exception_pairs:
                try:
                    ret = parse_user(self.bugdir, short_id)
                    self.fail('Expected parse_user(bugdir, "%s") to raise %s,'
                              '\n  but it returned %s'
                              % (short_id, exception.__class__.__name__, ret))
                except exception.__class__, e:
                    for attr in dir(e):
                        if attr.startswith('_') or attr == 'args':
                            continue
                        value = getattr(e, attr)
                        expected = getattr(exception, attr)
                        self.failUnless(
                            value == expected,
                            'Expected parse_user(bugdir, "%s") %s.%s'
                            '\n  to be %s, but it is %s\n\n%s'
                              % (short_id, exception.__class__.__name__,
                                 attr, expected, value, e))

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
