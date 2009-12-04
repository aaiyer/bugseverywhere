# Copyright (C) 2007-2009 Aaron Bentley and Panometrics, Inc.
#                         Ben Finney <benf@cybersource.com.au>
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
Mercurial (hg) backend.
"""

import os
import re
import sys

import libbe
import vcs

if libbe.TESTING == True:
    import unittest
    import doctest


def new():
    return Hg()

class Hg(vcs.VCS):
    name="hg"
    client="hg"
    versioned=True
    def _vcs_version(self):
        status,output,error = self._u_invoke_client("--version")
        return output
    def _vcs_detect(self, path):
        """Detect whether a directory is revision-controlled using Mercurial"""
        if self._u_search_parent_directories(path, ".hg") != None:
            return True
        return False
    def _vcs_root(self, path):
        status,output,error = self._u_invoke_client("root", cwd=path)
        return output.rstrip('\n')
    def _vcs_init(self, path):
        self._u_invoke_client("init", cwd=path)
    def _vcs_get_user_id(self):
        status,output,error = self._u_invoke_client("showconfig","ui.username")
        return output.rstrip('\n')
    def _vcs_set_user_id(self, value):
        """
        Supported by the Config Extension, but that is not part of
        standard Mercurial.
        http://www.selenic.com/mercurial/wiki/index.cgi/ConfigExtension
        """
        raise vcs.SettingIDnotSupported
    def _vcs_add(self, path):
        self._u_invoke_client("add", path)
    def _vcs_remove(self, path):
        self._u_invoke_client("rm", "--force", path)
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
            return vcs.VCS._vcs_duplicate_repo(self, directory, revision)
        else:
            self._u_invoke_client("archive", "--rev", revision, directory)
    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ['commit', '--logfile', commitfile]
        status,output,error = self._u_invoke_client(*args)
        if allow_empty == False:
            strings = ["nothing changed"]
            if self._u_any_in_string(strings, output) == True:
                raise vcs.EmptyCommit()
        return self._vcs_revision_id(-1)
    def _vcs_revision_id(self, index, style="id"):
        args = ["identify", "--rev", str(int(index)), "--%s" % style]
        kwargs = {"expect": (0,255)}
        status,output,error = self._u_invoke_client(*args, **kwargs)
        if status == 0:
            id = output.strip()
            if id == '000000000000':
                return None # before initial commit.
            return id
        return None

    
if libbe.TESTING == True:
    vcs.make_vcs_testcase_subclasses(Hg, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
