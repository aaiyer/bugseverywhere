# Copyright (C) 2008-2009 Ben Finney <benf@cybersource.com.au>
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
Git backend.
"""

import os
import os.path
import re
import shutil
import unittest

import libbe
import libbe.ui.util.user
import base

if libbe.TESTING == True:
    import doctest
    import sys


def new():
    return Git()

class Git(base.VCS):
    name='git'
    client='git'

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True

    def _vcs_version(self):
        status,output,error = self._u_invoke_client('--version')
        return output

    def _vcs_get_user_id(self):
        status,output,error = \
            self._u_invoke_client('config', 'user.name', expect=(0,1))
        if status == 0:
            name = output.rstrip('\n')
        else:
            name = ''
        status,output,error = \
            self._u_invoke_client('config', 'user.email', expect=(0,1))
        if status == 0:
            email = output.rstrip('\n')
        else:
            email = ''
        if name != '' or email != '': # got something!
            # guess missing info, if necessary
            if name == '':
                name = libbe.ui.util.user.get_fallback_username()
            if email == '':
                email = libe.ui.util.user.get_fallback_email()
            return libbe.ui.util.user.create_user_id(name, email)
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
        status,output,error = self._u_invoke_client(*args, expect=(0,128))
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
        args = ['commit', '--all', '--file', commitfile]
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


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Git, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
