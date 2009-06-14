# Copyright (C) 2007 Steve Borho <steve@borho.org>
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
    return Hg()

class Hg(RCS):
    name="hg"
    client="hg"
    versioned=True
    def _rcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output
    def _rcs_detect(self, path):
        """Detect whether a directory is revision-controlled using Mercurial"""
        if self._u_search_parent_directories(path, ".hg") != None:
            return True
        return False
    def _rcs_root(self, path):
        status,output,error = self._u_invoke_client("root", directory=path)
        return output.rstrip('\n')
    def _rcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _rcs_get_user_id(self):
        status,output,error = self._u_invoke_client("showconfig","ui.username")
        return output.rstrip('\n')
    def _rcs_set_user_id(self, value):
        """
        Supported by the Config Extension, but that is not part of
        standard Mercurial.
        http://www.selenic.com/mercurial/wiki/index.cgi/ConfigExtension
        """
        raise rcs.SettingIDnotSupported
    def _rcs_add(self, path):
        self._u_invoke_client("add", path)
    def _rcs_remove(self, path):
        self._u_invoke_client("rm", path)
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
            self._u_invoke_client("archive", "--rev", revision, directory)
    def _rcs_commit(self, commitfile):
        self._u_invoke_client('commit', '--logfile', commitfile)
        status,output,error = self._u_invoke_client('identify')
        revision = None
        revline = re.compile("(.*) tip")
        match = revline.search(output)
        assert match != None, output+error
        assert len(match.groups()) == 1
        revision = match.groups()[0]
        return revision

    
rcs.make_rcs_testcase_subclasses(Hg, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
