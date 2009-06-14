# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
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

import sys
import os
import re
import unittest
import doctest

import rcs
from rcs import RCS

def new():
    return Bzr()

class Bzr(RCS):
    name = "bzr"
    client = "bzr"
    versioned = True
    def _rcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output        
    def _rcs_detect(self, path):
        if self._u_search_parent_directories(path, ".bzr") != None :
            return True
        return False
    def _rcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        status,output,error = self._u_invoke_client("root", path)
        return output.rstrip('\n')
    def _rcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _rcs_get_user_id(self):
        status,output,error = self._u_invoke_client("whoami")
        return output.rstrip('\n')
    def _rcs_set_user_id(self, value):
        self._u_invoke_client("whoami", value)
    def _rcs_add(self, path):
        self._u_invoke_client("add", path)
    def _rcs_remove(self, path):
        # --force to also remove unversioned files.
        self._u_invoke_client("remove", "--force", path)
    def _rcs_update(self, path):
        pass
    def _rcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return file(os.path.join(self.rootdir, path), "rb").read()
        else:
            status,output,error = \
                self._u_invoke_client("cat","-r",revision,path)
            return output
    def _rcs_duplicate_repo(self, directory, revision=None):
        if revision == None:
            RCS._rcs_duplicate_repo(self, directory, revision)
        else:
            self._u_invoke_client("branch", "--revision", revision,
                                  ".", directory)
    def _rcs_commit(self, commitfile):
        status,output,error = self._u_invoke_client("commit", "--unchanged",
                                                    "--file", commitfile)
        revision = None
        revline = re.compile("Committed revision (.*)[.]")
        match = revline.search(error)
        assert match != None, output+error
        assert len(match.groups()) == 1
        revision = match.groups()[0]
        return revision
    def postcommit(self):
        try:
            self._u_invoke_client('merge')
        except rcs.CommandError, e:
            if ('No merge branch known or specified' in e.err_str or
                'No merge location known or specified' in e.err_str):
                pass
            else:
                self._u_invoke_client('revert',  '--no-backup', 
                                   directory=directory)
                self._u_invoke_client('resolve', '--all', directory=directory)
                raise
        if len(self._u_invoke_client('status', directory=directory)[1]) > 0:
            self.commit('Merge from upstream')

    
rcs.make_rcs_testcase_subclasses(Bzr, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
