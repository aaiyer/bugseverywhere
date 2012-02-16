# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Ben Finney <benf@cybersource.com.au>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Michel Alexandre Salim <salimma@fedoraproject.org>
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

"""Bazaar_ (bzr) backend.

.. _Bazaar: http://bazaar.canonical.com/
"""

try:
    import bzrlib
    import bzrlib.branch
    import bzrlib.builtins
    import bzrlib.config
    import bzrlib.errors
    import bzrlib.option
except ImportError:
    bzrlib = None
import os
import os.path
import re
import shutil
import StringIO
import sys

import libbe
import base

if libbe.TESTING == True:
    import doctest
    import unittest


def new():
    return Bzr()

class Bzr(base.VCS):
    """:class:`base.VCS` implementation for Bazaar.
    """
    name = 'bzr'
    client = None # bzrlib module

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True

    def _vcs_version(self):
        if bzrlib == None:
            return None
        return bzrlib.__version__

    def _vcs_get_user_id(self):
        # excerpted from bzrlib.builtins.cmd_whoami.run()
        try:
            c = bzrlib.branch.Branch.open_containing(self.repo)[0].get_config()
        except errors.NotBranchError:
            c = bzrlib.config.GlobalConfig()
        return c.username()

    def _vcs_detect(self, path):
        if self._u_search_parent_directories(path, '.bzr') != None :
            return True
        return False

    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        cmd = bzrlib.builtins.cmd_root()
        cmd.outf = StringIO.StringIO()
        cmd.run(filename=path)
        if self.version_cmp(2,2,0) < 0:
            cmd.cleanup_now()
        return cmd.outf.getvalue().rstrip('\n')

    def _vcs_init(self, path):
        cmd = bzrlib.builtins.cmd_init()
        cmd.outf = StringIO.StringIO()
        cmd.run(location=path)
        if self.version_cmp(2,2,0) < 0:
            cmd.cleanup_now()

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '.bzr')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)

    def _vcs_add(self, path):
        path = os.path.join(self.repo, path)
        cmd = bzrlib.builtins.cmd_add()
        cmd.outf = StringIO.StringIO()
        kwargs = {'file_ids_from': self.repo}
        if self.repo == os.path.realpath(os.getcwd()):
            # Work around bzr file locking on Windows.
            # See: https://lists.ubuntu.com/archives/bazaar/2011q1/071705.html
            kwargs.pop('file_ids_from')
        cmd.run(file_list=[path], **kwargs)
        if self.version_cmp(2,2,0) < 0:
            cmd.cleanup_now()

    def _vcs_exists(self, path, revision=None):
        manifest = self._vcs_listdir(
            self.repo, revision=revision, recursive=True)
        if path in manifest:
            return True
        return False

    def _vcs_remove(self, path):
        # --force to also remove unversioned files.
        path = os.path.join(self.repo, path)
        cmd = bzrlib.builtins.cmd_remove()
        cmd.outf = StringIO.StringIO()
        cmd.run(file_list=[path], file_deletion_strategy='force')
        if self.version_cmp(2,2,0) < 0:
            cmd.cleanup_now()

    def _vcs_update(self, path):
        pass

    def _parse_revision_string(self, revision=None):
        if revision == None:
            return revision
        rev_opt = bzrlib.option.Option.OPTIONS['revision']
        try:
            rev_spec = rev_opt.type(revision)
        except bzrlib.errors.NoSuchRevisionSpec:
            raise base.InvalidRevision(revision)
        return rev_spec

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        path = os.path.join(self.repo, path)
        revision = self._parse_revision_string(revision)
        cmd = bzrlib.builtins.cmd_cat()
        cmd.outf = StringIO.StringIO()
        if self.version_cmp(1,6,0) < 0:
            # old bzrlib cmd_cat uses sys.stdout not self.outf for output.
            stdout = sys.stdout
            sys.stdout = cmd.outf
        try:
            cmd.run(filename=path, revision=revision)
        except bzrlib.errors.BzrCommandError, e:
            if 'not present in revision' in str(e):
                raise base.InvalidPath(path, root=self.repo, revision=revision)
            raise
        finally:
            if self.version_cmp(2,0,0) < 0:
                cmd.outf = sys.stdout
                sys.stdout = stdout
            if self.version_cmp(2,2,0) < 0:
                cmd.cleanup_now()
        return cmd.outf.getvalue()

    def _vcs_path(self, id, revision):
        manifest = self._vcs_listdir(
            self.repo, revision=revision, recursive=True)
        return self._u_find_id_from_manifest(id, manifest, revision=revision)

    def _vcs_isdir(self, path, revision):
        try:
            self._vcs_listdir(path, revision)
        except AttributeError, e:
            if 'children' in str(e):
                return False
            raise
        return True

    def _vcs_listdir(self, path, revision, recursive=False):
        path = os.path.join(self.repo, path)
        revision = self._parse_revision_string(revision)
        cmd = bzrlib.builtins.cmd_ls()
        cmd.outf = StringIO.StringIO()
        try:
            if self.version_cmp(2,0,0) >= 0:
                cmd.run(revision=revision, path=path, recursive=recursive)
            else:
                # Pre-2.0 Bazaar (non_recursive)
                # + working around broken non_recursive+path implementation
                #   (https://bugs.launchpad.net/bzr/+bug/158690)
                cmd.run(revision=revision, path=path,
                        non_recursive=False)
        except bzrlib.errors.BzrCommandError, e:
            if 'not present in revision' in str(e):
                raise base.InvalidPath(path, root=self.repo, revision=revision)
            raise
        finally:
            if self.version_cmp(2,2,0) < 0:
                cmd.cleanup_now()
        children = cmd.outf.getvalue().rstrip('\n').splitlines()
        children = [self._u_rel_path(c, path) for c in children]
        if self.version_cmp(2,0,0) < 0 and recursive == False:
            children = [c for c in children if os.path.sep not in c]
        return children

    def _vcs_commit(self, commitfile, allow_empty=False):
        cmd = bzrlib.builtins.cmd_commit()
        cmd.outf = StringIO.StringIO()
        cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            cmd.run(file=commitfile, unchanged=allow_empty)
        except bzrlib.errors.BzrCommandError, e:
            strings = ['no changes to commit.', # bzr 1.3.1
                       'No changes to commit.'] # bzr 1.15.1
            if self._u_any_in_string(strings, str(e)) == True:
                raise base.EmptyCommit()
            raise
        finally:
            os.chdir(cwd)
            if self.version_cmp(2,2,0) < 0:
                cmd.cleanup_now()
        return self._vcs_revision_id(-1)

    def _vcs_revision_id(self, index):
        cmd = bzrlib.builtins.cmd_revno()
        cmd.outf = StringIO.StringIO()
        cmd.run(location=self.repo)
        if self.version_cmp(2,2,0) < 0:
            cmd.cleanup_now()
        current_revision = int(cmd.outf.getvalue())
        if index > current_revision or index < -current_revision:
            return None
        if index >= 0:
            return str(index) # bzr commit 0 is the empty tree.
        return str(current_revision+index+1)

    def _diff(self, revision):
        revision = self._parse_revision_string(revision)
        cmd = bzrlib.builtins.cmd_diff()
        cmd.outf = StringIO.StringIO()
        # for some reason, cmd_diff uses sys.stdout not self.outf for output.
        stdout = sys.stdout
        sys.stdout = cmd.outf
        try:
            status = cmd.run(revision=revision, file_list=[self.repo])
        finally:
            sys.stdout = stdout
            if self.version_cmp(2,2,0) < 0:
                cmd.cleanup_now()
        assert status in [0,1], "Invalid status %d" % status
        return cmd.outf.getvalue()

    def _parse_diff(self, diff_text):
        """_parse_diff(diff_text) -> (new,modified,removed)

        `new`, `modified`, and `removed` are lists of files.

        Example diff text::

          === modified file 'dir/changed'
          --- dir/changed	2010-01-16 01:54:53 +0000
          +++ dir/changed	2010-01-16 01:54:54 +0000
          @@ -1,3 +1,3 @@
           hi
          -there
          +everyone and
           joe
          
          === removed file 'dir/deleted'
          --- dir/deleted	2010-01-16 01:54:53 +0000
          +++ dir/deleted	1970-01-01 00:00:00 +0000
          @@ -1,3 +0,0 @@
          -in
          -the
          -beginning
          
          === removed file 'dir/moved'
          --- dir/moved	2010-01-16 01:54:53 +0000
          +++ dir/moved	1970-01-01 00:00:00 +0000
          @@ -1,4 +0,0 @@
          -the
          -ants
          -go
          -marching
          
          === added file 'dir/moved2'
          --- dir/moved2	1970-01-01 00:00:00 +0000
          +++ dir/moved2	2010-01-16 01:54:34 +0000
          @@ -0,0 +1,4 @@
          +the
          +ants
          +go
          +marching
          
          === added file 'dir/new'
          --- dir/new	1970-01-01 00:00:00 +0000
          +++ dir/new	2010-01-16 01:54:54 +0000
          @@ -0,0 +1,2 @@
          +hello
          +world
          
        """
        new = []
        modified = []
        removed = []
        for line in diff_text.splitlines():
            if not line.startswith('=== '):
                continue
            fields = line.split()
            action = fields[1]
            file = fields[-1].strip("'")
            if action == 'added':
                new.append(file)
            elif action == 'modified':
                modified.append(file)
            elif action == 'removed':
                removed.append(file)
        return (new,modified,removed)

    def _vcs_changed(self, revision):
        return self._parse_diff(self._diff(revision))


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Bzr, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
