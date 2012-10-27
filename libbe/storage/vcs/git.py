# Copyright (C) 2008-2012 Ben Finney <benf@cybersource.com.au>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Robert Lehmann <mail@robertlehmann.de>
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

"""Git_ backend.

.. _Git: http://git-scm.com/
"""

import os
import os.path
import re
import shutil
import unittest

try:
    import pygit2 as _pygit2
except ImportError, error:
    _pygit2 = None
    _pygit2_import_error = error
else:
    if getattr(_pygit2, '__version__', '0.17.3') == '0.17.3':
        _pygit2 = None
        _pygit2_import_error = NotImplementedError(
            'pygit2 <= 0.17.3 not supported')

import libbe
from ...ui.util import user as _user
from ...util import encoding as _encoding
from ..base import EmptyCommit as _EmptyCommit
from . import base

if libbe.TESTING == True:
    import doctest
    import sys


def new():
    if _pygit2:
        return PygitGit()
    else:
        return ExecGit()


class PygitGit(base.VCS):
    """:py:class:`base.VCS` implementation for Git.

    Using :py:mod:`pygit2` for the Git activity.
    """
    name='pygit2'
    _null_hex = u'0' * 40
    _null_oid = '\00' * 20

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self._pygit_repository = None

    def __getstate__(self):
        """`pygit2.Repository`\s don't seem to pickle well.
        """
        attrs = dict(self.__dict__)
        if self._pygit_repository is not None:
            attrs['_pygit_repository'] = self._pygit_repository.path
        return attrs

    def __setstate__(self, state):
        """`pygit2.Repository`\s don't seem to pickle well.
        """
        self.__dict__.update(state)
        if self._pygit_repository is not None:
            gitdir = self._pygit_repository
            self._pygit_repository = _pygit2.Repository(gitdir)

    def _vcs_version(self):
        if _pygit2:
            return getattr(_pygit2, '__verison__', '?')
        return None

    def _vcs_get_user_id(self):
        try:
            name = self._pygit_repository.config['user.name']
        except KeyError:
            name = ''
        try:
            email = self._pygit_repository.config['user.email']
        except KeyError:
            email = ''
        if name != '' or email != '': # got something!
            # guess missing info, if necessary
            if name == '':
                name = _user.get_fallback_fullname()
            if email == '':
                email = _user.get_fallback_email()
            if '@' not in email:
                raise ValueError((name, email))
            return _user.create_user_id(name, email)
        return None # Git has no infomation

    def _vcs_detect(self, path):
        try:
            _pygit2.discover_repository(path)
        except KeyError:
            return False
        return True

    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        # Assume that nothing funny is going on; in particular, that we aren't
        # dealing with a bare repo.
        gitdir = _pygit2.discover_repository(path)
        self._pygit_repository = _pygit2.Repository(gitdir)
        dirname,tip = os.path.split(gitdir)
        if tip == '':  # split('x/y/z/.git/') == ('x/y/z/.git', '')
            dirname,tip = os.path.split(dirname)
        assert tip == '.git', tip
        return dirname

    def _vcs_init(self, path):
        bare = False
        self._pygit_repository = _pygit2.init_repository(path, bare)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '.git')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)

    def _vcs_add(self, path):
        abspath = self._u_abspath(path)
        if os.path.isdir(abspath):
            return
        self._pygit_repository.index.read()
        self._pygit_repository.index.add(path)
        self._pygit_repository.index.write()

    def _vcs_remove(self, path):
        abspath = self._u_abspath(path)
        if not os.path.isdir(self._u_abspath(abspath)):
            self._pygit_repository.index.read()
            del self._pygit_repository.index[path]
            self._pygit_repository.index.write()
            os.remove(os.path.join(self.repo, path))

    def _vcs_update(self, path):
        self._vcs_add(path)

    def _git_get_commit(self, revision):
        if isinstance(revision, str):
            revision = unicode(revision, 'ascii')
        commit = self._pygit_repository.revparse_single(revision)
        assert commit.type == _pygit2.GIT_OBJ_COMMIT, commit
        return commit

    def _git_get_object(self, path, revision):
        commit = self._git_get_commit(revision=revision)
        tree = commit.tree
        sections = path.split(os.path.sep)
        for section in sections[:-1]:  # traverse trees
            child_tree = None
            for entry in tree:
                if entry.name == section:
                    eobj = entry.to_object()
                    if eobj.type == _pygit2.GIT_OBJ_TREE:
                        child_tree = eobj
                        break
                    else:
                        raise ValueError(path)  # not a directory
            if child_tree is None:
                raise ValueError((path, sections, section, [e.name for e in tree]))
                raise ValueError(path)  # not found
            tree = child_tree
        eobj = None
        for entry in tree:
            if entry.name == sections[-1]:
                eobj = entry.to_object()
        return eobj

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        else:
            blob = self._git_get_object(path=path, revision=revision)
            if blob.type != _pygit2.GIT_OBJ_BLOB:
                raise ValueError(path)  # not a file
            return blob.read_raw()

    def _vcs_path(self, id, revision):
        return self._u_find_id(id, revision)

    def _vcs_isdir(self, path, revision):
        obj = self._git_get_object(path=path, revision=revision)
        return obj.type == _pygit2.GIT_OBJ_TREE

    def _vcs_listdir(self, path, revision):
        tree = self._git_get_object(path=path, revision=revision)
        assert tree.type == _pygit2.GIT_OBJ_TREE, tree
        return [e.name for e in tree]

    def _vcs_commit(self, commitfile, allow_empty=False):
        self._pygit_repository.index.read()
        tree_oid = self._pygit_repository.index.write_tree()
        try:
            self._pygit_repository.head
        except _pygit2.GitError:  # no head; this is the first commit
            parents = []
            tree = self._pygit_repository[tree_oid]
            if not allow_empty and len(tree) == 0:
                raise _EmptyCommit()
        else:
            parents = [self._pygit_repository.head.oid]
            if (not allow_empty and
                tree_oid == self._pygit_repository.head.tree.oid):
                raise _EmptyCommit()
        update_ref = 'HEAD'
        user_id = self.get_user_id()
        name,email = _user.parse_user_id(user_id)
        # using default times is recent, see
        #   https://github.com/libgit2/pygit2/pull/129
        author = _pygit2.Signature(name, email)
        committer = author
        message = _encoding.get_file_contents(commitfile, decode=False)
        encoding = _encoding.get_text_file_encoding()
        commit_oid = self._pygit_repository.create_commit(
            update_ref, author, committer, message, tree_oid, parents,
            encoding)
        commit = self._pygit_repository[commit_oid]
        return commit.hex

    def _vcs_revision_id(self, index):
        walker = self._pygit_repository.walk(
            self._pygit_repository.head.oid, _pygit2.GIT_SORT_TIME)
        if index < 0:
            target_i = -1 - index  # -1: 0, -2: 1, ...
            for i,commit in enumerate(walker):
                if i == target_i:
                    return commit.hex
        elif index > 0:
            revisions = [commit.hex for commit in walker]
            # revisions is [newest, older, ..., oldest]
            if index > len(revisions):
                return None
            return revisions[len(revisions) - index]
        else:
            raise NotImplementedError('initial revision')
        return None

    def _vcs_changed(self, revision):
        commit = self._git_get_commit(revision=revision)
        diff = commit.tree.diff(self._pygit_repository.head.tree)
        new = set()
        modified = set()
        removed = set()
        for hunk in diff.changes['hunks']:
            if hunk.old_oid == self._null_hex:  # pygit2 uses hex in hunk.*_oid
                new.add(hunk.new_file)
            elif hunk.new_oid == self._null_hex:
                removed.add(hunk.old_file)
            else:
                modified.add(hunk.new_file)
        return (list(new), list(modified), list(removed))


class ExecGit (PygitGit):
    """:py:class:`base.VCS` implementation for Git.
    """
    name='git'
    client='git'

    def _vcs_version(self):
        try:
            status,output,error = self._u_invoke_client('--version')
        except CommandError:  # command not found?
            return None
        return output.strip()

    def _vcs_get_user_id(self):
        status,output,error = self._u_invoke_client(
            'config', 'user.name', expect=(0,1))
        if status == 0:
            name = output.rstrip('\n')
        else:
            name = ''
        status,output,error = self._u_invoke_client(
            'config', 'user.email', expect=(0,1))
        if status == 0:
            email = output.rstrip('\n')
        else:
            email = ''
        if name != '' or email != '': # got something!
            # guess missing info, if necessary
            if name == '':
                name = _user.get_fallback_fullname()
            if email == '':
                email = _user.get_fallback_email()
            return _user.create_user_id(name, email)
        return None # Git has no infomation

    def _vcs_detect(self, path):
        if self._u_search_parent_directories(path, '.git') != None :
            return True
        return False

    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        # Assume that nothing funny is going on; in particular, that we aren't
        # dealing with a bare repo.
        if os.path.isdir(path) != True:
            path = os.path.dirname(path)
        status,output,error = self._u_invoke_client('rev-parse', '--git-dir',
                                                    cwd=path)
        gitdir = os.path.join(path, output.rstrip('\n'))
        dirname = os.path.abspath(os.path.dirname(gitdir))
        return dirname

    def _vcs_init(self, path):
        self._u_invoke_client('init', cwd=path)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '.git')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)

    def _vcs_add(self, path):
        if os.path.isdir(path):
            return
        self._u_invoke_client('add', path)

    def _vcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            self._u_invoke_client('rm', '-f', path)

    def _vcs_update(self, path):
        self._vcs_add(path)

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        else:
            arg = '%s:%s' % (revision,path)
            status,output,error = self._u_invoke_client('show', arg)
            return output

    def _vcs_path(self, id, revision):
        return self._u_find_id(id, revision)

    def _vcs_isdir(self, path, revision):
        arg = '%s:%s' % (revision,path)
        args = ['ls-tree', arg]
        kwargs = {'expect':(0,128)}
        status,output,error = self._u_invoke_client(*args, **kwargs)
        if status != 0:
            if 'not a tree object' in error:
                return False
            raise base.CommandError(args, status, stderr=error)
        return True

    def _vcs_listdir(self, path, revision):
        arg = '%s:%s' % (revision,path)
        status,output,error = self._u_invoke_client(
            'ls-tree', '--name-only', arg)
        return output.rstrip('\n').splitlines()

    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ['commit', '--file', commitfile]
        if allow_empty == True:
            args.append('--allow-empty')
            status,output,error = self._u_invoke_client(*args)
        else:
            kwargs = {'expect':(0,1)}
            status,output,error = self._u_invoke_client(*args, **kwargs)
            strings = ['nothing to commit',
                       'nothing added to commit']
            if self._u_any_in_string(strings, output) == True:
                raise base.EmptyCommit()
        full_revision = self._vcs_revision_id(-1)
        assert full_revision[:7] in output, \
            'Mismatched revisions:\n%s\n%s' % (full_revision, output)
        return full_revision

    def _vcs_revision_id(self, index):
        args = ['rev-list', '--first-parent', '--reverse', 'HEAD']
        kwargs = {'expect':(0,128)}
        status,output,error = self._u_invoke_client(*args, **kwargs)
        if status == 128:
            if error.startswith("fatal: ambiguous argument 'HEAD': unknown "):
                return None
            raise base.CommandError(args, status, stderr=error)
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
        status,output,error = self._u_invoke_client('diff', revision)
        return output

    def _parse_diff(self, diff_text):
        """_parse_diff(diff_text) -> (new,modified,removed)

        `new`, `modified`, and `removed` are lists of files.

        Example diff text::

          diff --git a/dir/changed b/dir/changed
          index 6c3ea8c..2f2f7c7 100644
          --- a/dir/changed
          +++ b/dir/changed
          @@ -1,3 +1,3 @@
           hi
          -there
          +everyone and
           joe
          diff --git a/dir/deleted b/dir/deleted
          deleted file mode 100644
          index 225ec04..0000000
          --- a/dir/deleted
          +++ /dev/null
          @@ -1,3 +0,0 @@
          -in
          -the
          -beginning
          diff --git a/dir/moved b/dir/moved
          deleted file mode 100644
          index 5ef102f..0000000
          --- a/dir/moved
          +++ /dev/null
          @@ -1,4 +0,0 @@
          -the
          -ants
          -go
          -marching
          diff --git a/dir/moved2 b/dir/moved2
          new file mode 100644
          index 0000000..5ef102f
          --- /dev/null
          +++ b/dir/moved2
          @@ -0,0 +1,4 @@
          +the
          +ants
          +go
          +marching
          diff --git a/dir/new b/dir/new
          new file mode 100644
          index 0000000..94954ab
          --- /dev/null
          +++ b/dir/new
          @@ -0,0 +1,2 @@
          +hello
          +world
        """
        new = []
        modified = []
        removed = []
        lines = diff_text.splitlines()
        for i,line in enumerate(lines):
            if not line.startswith('diff '):
                continue
            file_a,file_b = line.split()[-2:]
            assert file_a.startswith('a/'), \
                'missformed file_a %s' % file_a
            assert file_b.startswith('b/'), \
                'missformed file_b %s' % file_b
            file = file_a[2:]
            assert file_b[2:] == file, \
                'diff file missmatch %s != %s' % (file_a, file_b)
            if lines[i+1].startswith('new '):
                new.append(file)
            elif lines[i+1].startswith('index '):
                modified.append(file)
            elif lines[i+1].startswith('deleted '):
                removed.append(file)
        return (new,modified,removed)

    def _vcs_changed(self, revision):
        return self._parse_diff(self._diff(revision))


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(PygitGit, sys.modules[__name__])
    base.make_vcs_testcase_subclasses(ExecGit, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
