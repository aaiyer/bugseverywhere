# Copyright (C) 2010-2012 Chris Ball <cjb@laptop.org>
#                         W. Trevor King <wking@tremily.us>
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

"""Monotone_ backend.

.. _Monotone: http://www.monotone.ca/
"""

import os
import os.path
import random
import re
import shutil
import unittest

import libbe
import libbe.ui.util.user
from ...util.subproc import CommandError
from . import base

if libbe.TESTING == True:
    import doctest
    import sys


def new():
    return Monotone()

class Monotone (base.VCS):
    """:py:class:`base.VCS` implementation for Monotone.
    """
    name='monotone'
    client='mtn'

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self._db_path = None
        self._key_dir = None
        self._key = None

    def _vcs_version(self):
        try:
            status,output,error = self._u_invoke_client('automate', 'interface_version')
        except CommandError:  # command not found?
            return None
        return output.strip()

    def version_cmp(self, *args):
        """Compare the installed Monotone version `V_i` with another
        version `V_o` (given in `*args`).  Returns

           === ===============
            1  if `V_i > V_o`
            0  if `V_i == V_o`
           -1  if `V_i < V_o`
           === ===============

        Examples
        --------

        >>> m = Monotone(repo='.')
        >>> m._version = '7.1'
        >>> m.version_cmp(7, 1)
        0
        >>> m.version_cmp(7, 2)
        -1
        >>> m.version_cmp(7, 0)
        1
        >>> m.version_cmp(8, 0)
        -1
        """
        if not hasattr(self, '_parsed_version') \
                or self._parsed_version == None:
            self._parsed_version = [int(x) for x in self.version().split('.')]
        for current,other in zip(self._parsed_version, args):
            c = cmp(current,other)
            if c != 0:
                return c
        return 0

    def _require_version_ge(self, *args):
        """Require installed interface version >= `*args`.

        >>> m = Monotone(repo='.')
        >>> m._version = '7.1'
        >>> m._require_version_ge(6, 0)
        >>> m._require_version_ge(7, 1)
        >>> m._require_version_ge(7, 2)
        Traceback (most recent call last):
          ...
        NotImplementedError: Operation not supported for monotone automation interface version 7.1.  Requires 7.2
        """
        if self.version_cmp(*args) < 0:
            raise NotImplementedError(
                'Operation not supported for %s automation interface version'
                ' %s.  Requires %s' % (self.name, self.version(),
                                      '.'.join([str(x) for x in args])))

    def _vcs_get_user_id(self):
        status,output,error = self._u_invoke_client('list', 'keys')
        # output ~=
        # ...
        # [private keys]
        # f7791378b49dfb47a740e9588848b510de58f64f john@doe.com
        if '[private keys]' in output:
            private = False
            for line in output.splitlines():
                line = line.strip()
                if private == True:  # HACK.  Just pick the first key.
                    return line.split(' ', 1)[1]
                if line == '[private keys]':
                    private = True
        return None  # Monotone has no infomation

    def _vcs_detect(self, path):
        if self._u_search_parent_directories(path, '_MTN') != None :
            return True
        return False

    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        if self.version_cmp(8, 0) >= 0:
            if not os.path.isdir(path):
                dirname = os.path.dirname(path)
            else:
                dirname = path
            status,output,error = self._invoke_client(
                'automate', 'get_workspace_root', cwd=dirname)
        else:
            mtn_dir = self._u_search_parent_directories(path, '_MTN')
            if mtn_dir == None:
                return None
            return os.path.dirname(mtn_dir)
        return output.strip()

    def _invoke_client(self, *args, **kwargs):
        """Invoke the client on our branch.
        """
        arglist = []
        if self._db_path != None:
            arglist.extend(['--db', self._db_path])
        if self._key != None:
            arglist.extend(['--key', self._key])
        if self._key_dir != None:
            arglist.extend(['--keydir', self._key_dir])
        arglist.extend(args)
        args = tuple(arglist)
        return self._u_invoke_client(*args, **kwargs)

    def _vcs_init(self, path):
        self._require_version_ge(4, 0)
        self._db_path = os.path.abspath(os.path.join(path, 'bugseverywhere.db'))
        self._key_dir = os.path.abspath(os.path.join(path, '_monotone_keys'))
        self._branch_name = 'bugs-everywhere-test'
        self._key = 'bugseverywhere-%d@test.com' % random.randint(0,1e6)
        self._passphrase = ''
        self._u_invoke_client('db', 'init', '--db', self._db_path, cwd=path)
        os.mkdir(self._key_dir)
        self._u_invoke_client(
            '--db', self._db_path,
            '--keydir', self._key_dir,
            'automate', 'genkey', self._key, self._passphrase)
        self._invoke_client(
            'setup', '--db', self._db_path,
            '--branch', self._branch_name, cwd=path)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '_MTN')
        for dir in [vcs_dir, self._key_dir]:
            if os.path.exists(dir):
                shutil.rmtree(dir)
        if os.path.exists(self._db_path):
            os.remove(self._db_path)

    def _vcs_add(self, path):
        if os.path.isdir(path):
            return
        self._invoke_client('add', path)

    def _vcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            self._invoke_client('rm', path)

    def _vcs_update(self, path):
        pass

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        else:
            self._require_version_ge(4, 0)
            status,output,error = self._invoke_client(
                'automate', 'get_file_of', path, '--revision', revision)
            return output

    def _dirs_and_files(self, revision):
        self._require_version_ge(2, 0)
        status,output,error = self._invoke_client(
            'automate', 'get_manifest_of', revision)
        dirs = []
        files = []
        children_by_dir = {}
        for line in output.splitlines():
            fields = line.strip().split(' ', 1)
            if len(fields) != 2 or len(fields[1]) < 2:
                continue
            value = fields[1][1:-1]  # [1:-1] for '"XYZ"' -> 'XYZ'
            if value == '':
                value = '.'
            if fields[0] == 'dir':
                dirs.append(value)
                children_by_dir[value] = []
            elif fields[0] == 'file':
                files.append(value)
        for child in (dirs+files):
            if child == '.':
                continue
            parent = '.'
            for p in dirs:
                # Does Monotone use native path separators?
                start = p+os.path.sep
                if p != child and child.startswith(start):
                    rel = child[len(start):]
                    if rel.count(os.path.sep) == 0:
                        parent = p
                        break
            children_by_dir[parent].append(child)
        return (dirs, files, children_by_dir)

    def _vcs_path(self, id, revision):
        dirs,files,children_by_dir = self._dirs_and_files(revision)
        return self._u_find_id_from_manifest(id, dirs+files, revision=revision)

    def _vcs_isdir(self, path, revision):
        dirs,files,children_by_dir = self._dirs_and_files(revision)
        return path in dirs

    def _vcs_listdir(self, path, revision):
        dirs,files,children_by_dir = self._dirs_and_files(revision)
        children = [self._u_rel_path(c, path) for c in children_by_dir[path]]
        return children

    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ['commit', '--key', self._key, '--message-file', commitfile]
        kwargs = {'expect': (0,1)}
        status,output,error = self._invoke_client(*args, **kwargs)
        strings = ['no changes to commit']
        current_rev = self._current_revision()
        if status == 1:
            if self._u_any_in_string(strings, error) == True:
                if allow_empty == False:
                    raise base.EmptyCommit()
                # note that Monotone does _not_ make an empty revision.
                # this returns the last non-empty revision id...
            else:
                raise CommandError(
                    [self.client] + args, status, output, error)
        else:  # successful commit
            assert current_rev in error, \
                'Mismatched revisions:\n%s\n%s' % (current_rev, error)
        return current_rev

    def _current_revision(self):
        self._require_version_ge(2, 0)
        status,output,error = self._invoke_client(
            'automate', 'get_base_revision_id')  # since 2.0
        return output.strip()

    def _vcs_revision_id(self, index):
        current_rev = self._current_revision()
        status,output,error = self._invoke_client(
            'automate', 'ancestors', current_rev)  # since 0.2, but output is alphebetized
        revs = output.splitlines() + [current_rev]
        status,output,error = self._invoke_client(
            'automate', 'toposort', *revs)
        revisions = output.splitlines()
        try:
            if index > 0:
                return revisions[index-1]
            elif index < 0:
                return revisions[index]
            else:
                return None
        except IndexError:
            return None

    def _diff(self, revision):
        status,output,error = self._invoke_client('-r', revision, 'diff')
        return output

    def _parse_diff(self, diff_text):
        """_parse_diff(diff_text) -> (new,modified,removed)

        `new`, `modified`, and `removed` are lists of files.

        Example diff text::

          #
          # old_revision [1ce9ac2cfe3166b8ad23a60555f8a70f37686c25]
          #
          # delete ".be/dir/bugs/moved"
          # 
          # delete ".be/dir/bugs/removed"
          # 
          # add_file ".be/dir/bugs/moved2"
          #  content [33e4510df9abef16dad7c65c0775e74602cc5005]
          # 
          # add_file ".be/dir/bugs/new"
          #  content [45c45b5630f7446f83b0e14ee1525e449a06131c]
          # 
          # patch ".be/dir/bugs/modified"
          #  from [809bf3b80423c361849386008a0ce01199d30929]
          #    to [f13d3ec08972e2b41afecd9a90d4bc71cdcea338]
          #
          ============================================================
          --- .be/dir/bugs/moved2 33e4510df9abef16dad7c65c0775e74602cc5005
          +++ .be/dir/bugs/moved2 33e4510df9abef16dad7c65c0775e74602cc5005
          @@ -0,0 +1 @@
          +this entry will be moved
          \ No newline at end of file
          ============================================================
          --- .be/dir/bugs/new    45c45b5630f7446f83b0e14ee1525e449a06131c
          +++ .be/dir/bugs/new    45c45b5630f7446f83b0e14ee1525e449a06131c
          @@ -0,0 +1 @@
          +this entry is new
          \ No newline at end of file
          ============================================================
          --- .be/dir/bugs/modified       809bf3b80423c361849386008a0ce01199d30929
          +++ .be/dir/bugs/modified       f13d3ec08972e2b41afecd9a90d4bc71cdcea338
          @@ -1 +1 @@
          -some value to be modified
          \ No newline at end of file
          +a new value
          \ No newline at end of file
        """
        new = []
        modified = []
        removed = []
        lines = diff_text.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('# add_file "'):
                new.append(line[len('# add_file "'):-1])
            elif line.startswith('# patch "'):
                modified.append(line[len('# patch "'):-1])
            elif line.startswith('# delete "'):
                removed.append(line[len('# delete "'):-1])
            elif not line.startswith('#'):
                break
        return (new,modified,removed)

    def _vcs_changed(self, revision):
        return self._parse_diff(self._diff(revision))


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Monotone, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
