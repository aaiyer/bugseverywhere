# Copyright (C) 2008-2009 Ben Finney <ben+python@benfinney.id.au>
#                         Chris Ball <cjb@laptop.org>
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
import re
import sys
import unittest
import doctest

import vcs


def new():
    return Git()

class Git(vcs.VCS):
    name="git"
    client="git"
    versioned=True
    def _vcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output
    def _vcs_detect(self, path):
        if self._u_search_parent_directories(path, ".git") != None :
            return True
        return False 
    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        # Assume that nothing funny is going on; in particular, that we aren't
        # dealing with a bare repo.
        if os.path.isdir(path) != True:
            path = os.path.dirname(path)
        status,output,error = self._u_invoke_client("rev-parse", "--git-dir",
                                                    directory=path)
        gitdir = os.path.join(path, output.rstrip('\n'))
        dirname = os.path.abspath(os.path.dirname(gitdir))
        return dirname
    def _vcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _vcs_get_user_id(self):
        status,output,error = \
            self._u_invoke_client("config", "user.name", expect=(0,1))
        if status == 0:
            name = output.rstrip('\n')
        else:
            name = ""
        status,output,error = \
            self._u_invoke_client("config", "user.email", expect=(0,1))
        if status == 0:
            email = output.rstrip('\n')
        else:
            email = ""
        if name != "" or email != "": # got something!
            # guess missing info, if necessary
            if name == "":
                name = self._u_get_fallback_username()
            if email == "":
                email = self._u_get_fallback_email()
            return self._u_create_id(name, email)
        return None # Git has no infomation
    def _vcs_set_user_id(self, value):
        name,email = self._u_parse_id(value)
        if email != None:
            self._u_invoke_client("config", "user.email", email)
        self._u_invoke_client("config", "user.name", name)
    def _vcs_add(self, path):
        if os.path.isdir(path):
            return
        self._u_invoke_client("add", path)
    def _vcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            self._u_invoke_client("rm", "-f", path)
    def _vcs_update(self, path):
        self._vcs_add(path)
    def _vcs_get_file_contents(self, path, revision=None, binary=False):
        if revision == None:
            return vcs.VCS._vcs_get_file_contents(self, path, revision, binary=binary)
        else:
            arg = "%s:%s" % (revision,path)
            status,output,error = self._u_invoke_client("show", arg)
            return output
    def _vcs_duplicate_repo(self, directory, revision=None):
        if revision==None:
            vcs.VCS._vcs_duplicate_repo(self, directory, revision)
        else:
            #self._u_invoke_client("archive", revision, directory) # makes tarball
            self._u_invoke_client("clone", "--no-checkout",".",directory)
            self._u_invoke_client("checkout", revision, directory=directory)
    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ['commit', '--all', '--file', commitfile]
        if allow_empty == True:
            args.append("--allow-empty")
            status,output,error = self._u_invoke_client(*args)
        else:
            kwargs = {"expect":(0,1)}
            status,output,error = self._u_invoke_client(*args, **kwargs)
            strings = ["nothing to commit",
                       "nothing added to commit"]
            if self._u_any_in_string(strings, output) == True:
                raise vcs.EmptyCommit()
        revision = None
        revline = re.compile("(.*) (.*)[:\]] (.*)")
        match = revline.search(output)
        assert match != None, output+error
        assert len(match.groups()) == 3
        revision = match.groups()[1]
        full_revision = self._vcs_revision_id(-1)
        assert full_revision.startswith(revision), \
            "Mismatched revisions:\n%s\n%s" % (revision, full_revision)
        return full_revision
    def _vcs_revision_id(self, index):
        args = ["rev-list", "--first-parent", "--reverse", "HEAD"]
        kwargs = {"expect":(0,128)}
        status,output,error = self._u_invoke_client(*args, **kwargs)
        if status == 128:
            if error.startswith("fatal: ambiguous argument 'HEAD': unknown "):
                return None
            raise vcs.CommandError(args, status, stdout="", stderr=error)
        commits = output.splitlines()
        try:
            return commits[index]
        except IndexError:
            return None

    
vcs.make_vcs_testcase_subclasses(Git, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
