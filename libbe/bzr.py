# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Ben Finney <ben+python@benfinney.id.au>
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

import os
import re
import sys
import unittest
import doctest

import vcs


def new():
    return Bzr()

class Bzr(vcs.VCS):
    name = "bzr"
    client = "bzr"
    versioned = True
    def _vcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output        
    def _vcs_detect(self, path):
        if self._u_search_parent_directories(path, ".bzr") != None :
            return True
        return False
    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        status,output,error = self._u_invoke_client("root", path)
        return output.rstrip('\n')
    def _vcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _vcs_get_user_id(self):
        status,output,error = self._u_invoke_client("whoami")
        return output.rstrip('\n')
    def _vcs_set_user_id(self, value):
        self._u_invoke_client("whoami", value)
    def _vcs_add(self, path):
        self._u_invoke_client("add", path)
    def _vcs_remove(self, path):
        # --force to also remove unversioned files.
        self._u_invoke_client("remove", "--force", path)
    def _vcs_update(self, path):
        pass
    def _vcs_get_file_contents(self, path, revision=None, binary=False):
        if revision == None:
            return vcs.VCS._vcs_get_file_contents(self, path, revision, binary=binary)
        else:
            status,output,error = \
                self._u_invoke_client("cat","-r",revision,path)
            return output
    def _vcs_duplicate_repo(self, directory, revision=None):
        if revision == None:
            vcs.VCS._vcs_duplicate_repo(self, directory, revision)
        else:
            self._u_invoke_client("branch", "--revision", revision,
                                  ".", directory)
    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ["commit", "--file", commitfile]
        if allow_empty == True:
            args.append("--unchanged")
            status,output,error = self._u_invoke_client(*args)
        else:
            kwargs = {"expect":(0,3)}
            status,output,error = self._u_invoke_client(*args, **kwargs)
            if status != 0:
                strings = ["ERROR: no changes to commit.", # bzr 1.3.1
                           "ERROR: No changes to commit."] # bzr 1.15.1
                if self._u_any_in_string(strings, error) == True:
                    raise vcs.EmptyCommit()
                else:
                    raise vcs.CommandError(args, status, error)
        revision = None
        revline = re.compile("Committed revision (.*)[.]")
        match = revline.search(error)
        assert match != None, output+error
        assert len(match.groups()) == 1
        revision = match.groups()[0]
        return revision
    def _vcs_revision_id(self, index):
        status,output,error = self._u_invoke_client("revno")
        current_revision = int(output)
        if index >= current_revision or index < -current_revision:
            return None
        if index >= 0:
            return str(index+1) # bzr commit 0 is the empty tree.
        return str(current_revision+index+1)

    
vcs.make_vcs_testcase_subclasses(Bzr, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
