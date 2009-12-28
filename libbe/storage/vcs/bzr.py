# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Ben Finney <benf@cybersource.com.au>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marienz@gentoo.org>
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
Bazaar (bzr) backend.
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

import libbe
import base

if libbe.TESTING == True:
    import doctest
    import sys
    import unittest


def new():
    return Bzr()

class Bzr(base.VCS):
    name = 'bzr'
    client = None # bzrlib

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
        return cmd.outf.getvalue().rstrip('\n')

    def _vcs_init(self, path):
        cmd = bzrlib.builtins.cmd_init()
        cmd.outf = StringIO.StringIO()
        cmd.run(location=path)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '.bzr')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)

    def _vcs_add(self, path):
        path = os.path.join(self.repo, path)
        cmd = bzrlib.builtins.cmd_add()
        cmd.outf = StringIO.StringIO()
        cmd.run(file_list=[path], file_ids_from=self.repo)

    def _vcs_remove(self, path):
        # --force to also remove unversioned files.
        path = os.path.join(self.repo, path)
        cmd = bzrlib.builtins.cmd_remove()
        cmd.outf = StringIO.StringIO()
        cmd.run(file_list=[path], file_deletion_strategy='force')

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
        try:
            cmd.run(filename=path, revision=revision)
        except bzrlib.errors.BzrCommandError, e:
            if 'not present in revision' in str(e):
                raise base.InvalidID(path)
            raise
        return cmd.outf.getvalue()        

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
        return self._vcs_revision_id(-1)

    def _vcs_revision_id(self, index):
        cmd = bzrlib.builtins.cmd_revno()
        cmd.outf = StringIO.StringIO()
        cmd.run(location=self.repo)
        current_revision = int(cmd.outf.getvalue())
        if index > current_revision or index < -current_revision:
            return None
        if index >= 0:
            return str(index) # bzr commit 0 is the empty tree.
        return str(current_revision+index+1)


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Bzr, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
