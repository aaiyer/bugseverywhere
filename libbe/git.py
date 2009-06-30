# Copyright (C) 2007 Chris Ball <chris@printf.net>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import re
import sys
import unittest
import doctest

import rcs
from rcs import RCS

def new():
    return Git()

class Git(RCS):
    name="git"
    client="git"
    versioned=True
    def _rcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output
    def _rcs_detect(self, path):
        if self._u_search_parent_directories(path, ".git") != None :
            return True
        return False 
    def _rcs_root(self, path):
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
    def _rcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _rcs_get_user_id(self):
        status,output,error = self._u_invoke_client("config", "user.name")
        name = output.rstrip('\n')
        status,output,error = self._u_invoke_client("config", "user.email")
        email = output.rstrip('\n')
        if name != "" or email != "": # got something!
            # guess missing info, if necessary
            if name == "":
                name = self._u_get_fallback_username()
            if email == "":
                email = self._u_get_fallback_email()
            return self._u_create_id(name, email)
        return None # Git has no infomation
    def _rcs_set_user_id(self, value):
        name,email = self._u_parse_id(value)
        if email != None:
            self._u_invoke_client("config", "user.email", email)
        self._u_invoke_client("config", "user.name", name)
    def _rcs_add(self, path):
        if os.path.isdir(path):
            return
        self._u_invoke_client("add", path)
    def _rcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            self._u_invoke_client("rm", "-f", path)
    def _rcs_update(self, path):
        self._rcs_add(path)
    def _rcs_get_file_contents(self, path, revision=None, binary=False):
        if revision == None:
            return RCS._rcs_get_file_contents(self, path, revision, binary=binary)
        else:
            arg = "%s:%s" % (revision,path)
            status,output,error = self._u_invoke_client("show", arg)
            return output
    def _rcs_duplicate_repo(self, directory, revision=None):
        if revision==None:
            RCS._rcs_duplicate_repo(self, directory, revision)
        else:
            #self._u_invoke_client("archive", revision, directory) # makes tarball
            self._u_invoke_client("clone", "--no-checkout",".",directory)
            self._u_invoke_client("checkout", revision, directory=directory)
    def _rcs_commit(self, commitfile):
        status,output,error = self._u_invoke_client('commit', '-a',
                                                    '-F', commitfile)
        revision = None
        revline = re.compile("(.*) (.*)[:\]] (.*)")
        match = revline.search(output)
        assert match != None, output+error
        assert len(match.groups()) == 3
        revision = match.groups()[1]
        return revision

    
rcs.make_rcs_testcase_subclasses(Git, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
