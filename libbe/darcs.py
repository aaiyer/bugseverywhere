# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
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

import codecs
import os
import re
import sys
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
from xml.sax.saxutils import unescape
import doctest
import unittest

import vcs
from vcs import VCS

def new():
    return Darcs()

class Darcs(VCS):
    name="darcs"
    client="darcs"
    versioned=True
    def _vcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output
    def _vcs_detect(self, path):
        if self._u_search_parent_directories(path, "_darcs") != None :
            return True
        return False 
    def _vcs_root(self, path):
        """Find the root of the deepest repository containing path."""
        # Assume that nothing funny is going on; in particular, that we aren't
        # dealing with a bare repo.
        if os.path.isdir(path) != True:
            path = os.path.dirname(path)
        darcs_dir = self._u_search_parent_directories(path, "_darcs")
        if darcs_dir == None:
            return None
        return os.path.dirname(darcs_dir)
    def _vcs_init(self, path):
        self._u_invoke_client("init", directory=path)
    def _vcs_get_user_id(self):
        # following http://darcs.net/manual/node4.html#SECTION00410030000000000000
        # as of June 29th, 2009
        if self.rootdir == None:
            return None
        darcs_dir = os.path.join(self.rootdir, "_darcs")
        if darcs_dir != None:
            for pref_file in ["author", "email"]:
                pref_path = os.path.join(darcs_dir, "prefs", pref_file)
                if os.path.exists(pref_path):
                    return self.get_file_contents(pref_path)
        for env_variable in ["DARCS_EMAIL", "EMAIL"]:
            if env_variable in os.environ:
                return os.environ[env_variable]
        return None
    def _vcs_set_user_id(self, value):
        if self.rootdir == None:
            self.root(".")
            if self.rootdir == None:
                raise vcs.SettingIDnotSupported
        author_path = os.path.join(self.rootdir, "_darcs", "prefs", "author")
        f = codecs.open(author_path, "w", self.encoding)
        f.write(value)
        f.close()
    def _vcs_add(self, path):
        if os.path.isdir(path):
            return
        self._u_invoke_client("add", path)
    def _vcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            os.remove(os.path.join(self.rootdir, path)) # darcs notices removal
    def _vcs_update(self, path):
        pass # darcs notices changes
    def _vcs_get_file_contents(self, path, revision=None, binary=False):
        if revision == None:
            return VCS._vcs_get_file_contents(self, path, revision,
                                              binary=binary)
        else:
            try:
                return self._u_invoke_client("show", "contents", "--patch", revision, path)
            except vcs.CommandError:
                # Darcs versions < 2.0.0pre2 lack the "show contents" command

                status,output,error = self._u_invoke_client("diff", "--unified",
                                                            "--from-patch",
                                                            revision, path)
                major_patch = output
                status,output,error = self._u_invoke_client("diff", "--unified",
                                                            "--patch",
                                                            revision, path)
                target_patch = output
                
                # "--output -" to be supported in GNU patch > 2.5.9
                # but that hasn't been released as of June 30th, 2009.

                # Rewrite path to status before the patch we want
                args=["patch", "--reverse", path]
                status,output,error = self._u_invoke(args, stdin=major_patch)
                # Now apply the patch we want
                args=["patch", path]
                status,output,error = self._u_invoke(args, stdin=target_patch)

                if os.path.exists(os.path.join(self.rootdir, path)) == True:
                    contents = VCS._vcs_get_file_contents(self, path,
                                                          binary=binary)
                else:
                    contents = ""

                # Now restore path to it's current incarnation
                args=["patch", "--reverse", path]
                status,output,error = self._u_invoke(args, stdin=target_patch)
                args=["patch", path]
                status,output,error = self._u_invoke(args, stdin=major_patch)
                current_contents = VCS._vcs_get_file_contents(self, path,
                                                              binary=binary)
                return contents
    def _vcs_duplicate_repo(self, directory, revision=None):
        if revision==None:
            VCS._vcs_duplicate_repo(self, directory, revision)
        else:
            self._u_invoke_client("put", "--to-patch", revision, directory)
    def _vcs_commit(self, commitfile, allow_empty=False):
        id = self.get_user_id()
        if '@' not in id:
            id = "%s <%s@invalid.com>" % (id, id)
        args = ['record', '--all', '--author', id, '--logfile', commitfile]
        status,output,error = self._u_invoke_client(*args)
        empty_strings = ["No changes!"]
        if self._u_any_in_string(empty_strings, output) == True:
            if allow_empty == False:
                raise vcs.EmptyCommit()
            # note that darcs does _not_ make an empty revision.
            # this returns the last non-empty revision id...
            revision = self._vcs_revision_id(-1)
        else:
            revline = re.compile("Finished recording patch '(.*)'")
            match = revline.search(output)
            assert match != None, output+error
            assert len(match.groups()) == 1
            revision = match.groups()[0]
        return revision
    def _vcs_revision_id(self, index):
        status,output,error = self._u_invoke_client("changes", "--xml")
        revisions = []
        xml_str = output.encode("unicode_escape").replace(r"\n", "\n")
        element = ElementTree.XML(xml_str)
        assert element.tag == "changelog", element.tag
        for patch in element.getchildren():
            assert patch.tag == "patch", patch.tag
            for child in patch.getchildren():
                if child.tag == "name":
                    text = unescape(unicode(child.text).decode("unicode_escape").strip())
                    revisions.append(text)
        revisions.reverse()
        try:
            return revisions[index]
        except IndexError:
            return None
    
vcs.make_vcs_testcase_subclasses(Darcs, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
