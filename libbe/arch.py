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
import os
import shutil
import time
import re
import unittest
import doctest

import config
from beuuid import uuid_gen
from rcs import RCS, RCStestCase, CommandError

client = config.get_val("arch_client")
if client is None:
    client = "tla"
    config.set_val("arch_client", client)

def new():
    return Arch()

class Arch(RCS):
    name = "Arch"
    client = client
    versioned = True
    _archive_name = None
    _archive_dir = None
    _tmp_archive = False
    _project_name = None
    _tmp_project = False
    _arch_paramdir = os.path.expanduser("~/.arch-params")
    def _rcs_help(self):
        status,output,error = self._u_invoke_client("--help")
        return output
    def _rcs_detect(self, path):
        """Detect whether a directory is revision-controlled using Arch"""
        if self._u_search_parent_directories(path, "{arch}") != None :
            return True
        return False
    def _rcs_init(self, path):
        self._create_archive(path)
        self._create_project(path)
        self._add_project_code(path)
    def _create_archive(self, path):
        # Create a new archive
        # http://regexps.srparish.net/tutorial-tla/new-archive.html#Creating_a_New_Archive
        assert self._archive_name == None
        id = self.get_user_id()
        name, email = self._u_parse_id(id)
        if email == None:
            email = "%s@example.com" % name
        trailer = "%s-%s" % ("bugs-everywhere-auto", uuid_gen()[0:8])
        self._archive_name = "%s--%s" % (email, trailer)
        self._archive_dir = "/tmp/%s" % trailer
        self._tmp_archive = True
        self._u_invoke_client("make-archive", self._archive_name,
                              self._archive_dir, directory=path)
        self._u_invoke_client("archives")
    def _invoke_client(self, *args, **kwargs):
        """
        Invoke the client on our archive.
        """
        assert self._archive_name != None
        command = args[0]
        if len(args) > 1:
            tailargs = args[1:]
        else:
            tailargs = []
        arglist = [command, "-A", self._archive_name]
        arglist.extend(tailargs)
        args = tuple(arglist)
        return self._u_invoke_client(*args, **kwargs)
    def _remove_archive(self):
        assert self._tmp_archive == True
        assert self._archive_dir != None
        assert self._archive_name != None
        os.remove(os.path.join(self._arch_paramdir,
                               "=locations", self._archive_name))
        shutil.rmtree(self._archive_dir)
        self._tmp_archive = False
        self._archive_dir = False
        self._archive_name = False
    def _create_project(self, path):
        """
        Create a temporary Arch project in the directory PATH.  This
        project will be removed by
          __del__->cleanup->_rcs_cleanup->_remove_project
        """
        # http://mwolson.org/projects/GettingStartedWithArch.html
        # http://regexps.srparish.net/tutorial-tla/new-project.html#Starting_a_New_Project
        category = "bugs-everywhere"
        branch = "mainline"
        version = "0.1"
        self._project_name = "%s--%s--%s" % (category, branch, version)
        self._invoke_client("archive-setup", self._project_name,
                            directory=path)
        self._tmp_project = True
    def _remove_project(self):
        assert self._tmp_project == True
        assert self._project_name != None
        assert self._archive_dir != None
        shutil.rmtree(os.path.join(self._archive_dir, self._project_name))
        self._tmp_project = False
        self._project_name = False
    def _archive_project_name(self):
        assert self._archive_name != None
        assert self._project_name != None
        return "%s/%s" % (self._archive_name, self._project_name)
    def _adjust_naming_conventions(self, path):
        """
        By default, Arch restricts source code filenames to
          ^[_=a-zA-Z0-9].*$
        See
          http://regexps.srparish.net/tutorial-tla/naming-conventions.html
        Since our bug directory '.be' doesn't satisfy these conventions,
        we need to adjust them.
        
        The conventions are specified in
          project-root/{arch}/=tagging-method
        """
        tagpath = os.path.join(path, "{arch}", "=tagging-method")
        lines_out = []
        for line in file(tagpath, "rb"):
            line.decode("utf-8")
            if line.startswith("source "):
                lines_out.append("source ^[._=a-zA-X0-9].*$\n")
            else:
                lines_out.append(line)
        file(tagpath, "wb").write("".join(lines_out).encode("utf-8"))

    def _add_project_code(self, path):
        # http://mwolson.org/projects/GettingStartedWithArch.html
        # http://regexps.srparish.net/tutorial-tla/new-source.html
        # http://regexps.srparish.net/tutorial-tla/importing-first.html
        self._invoke_client("init-tree", self._project_name,
                              directory=path)
        self._adjust_naming_conventions(path)
        self._invoke_client("import", "--summary", "Began versioning",
                            directory=path)
    def _rcs_cleanup(self):
        if self._tmp_project == True:
            self._remove_project()
        if self._tmp_archive == True:
            self._remove_archive()

    def _rcs_root(self, path):
        if not os.path.isdir(path):
            dirname = os.path.dirname(path)
        else:
            dirname = path
        status,output,error = self._u_invoke_client("tree-root", dirname)
        root = output.rstrip('\n')
        
        self._get_archive_project_name(root)

        return root

    def _get_archive_name(self, root):
        status,output,error = self._u_invoke_client("archives")
        lines = output.split('\n')
        # e.g. output:
        # jdoe@example.com--bugs-everywhere-auto-2008.22.24.52
        #     /tmp/BEtestXXXXXX/rootdir
        # (+ repeats)
        for archive,location in zip(lines[::2], lines[1::2]):
            if os.path.realpath(location) == os.path.realpath(root):
                self._archive_name = archive
        assert self._archive_name != None

    def _get_archive_project_name(self, root):
        # get project names
        status,output,error = self._u_invoke_client("tree-version", directory=root)
        # e.g output
        # jdoe@example.com--bugs-everywhere-auto-2008.22.24.52/be--mainline--0.1
        archive_name,project_name = output.rstrip('\n').split('/')
        self._archive_name = archive_name
        self._project_name = project_name
    def _rcs_get_user_id(self):
        try:
            self._u_invoke_client("archives")
            status,output,error = self._u_invoke_client('my-id')
            return output.rstrip('\n')
        except Exception, e:
            if 'no arch user id set' in e.args[0]:
                return None
            else:
                raise
    def _rcs_set_user_id(self, value):
        self._u_invoke_client('my-id', value)
    def _rcs_add(self, path):
        self._u_invoke_client("archives")
        self._u_invoke_client("add-id", path)
        realpath = os.path.realpath(self._u_abspath(path))
        pathAdded = realpath in self._list_added(self.rootdir)
        if self.paranoid and not pathAdded:
            self._force_source(path)
        self._u_invoke_client("archives")
    def _list_added(self, root):
        assert os.path.exists(root)
        assert os.access(root, os.X_OK)
        root = os.path.realpath(root)
        status,output,error = self._u_invoke_client("inventory", "--source",
                                                    "--both", "--all", root)
        inv_str = output.rstrip('\n')
        return [os.path.join(root, p) for p in inv_str.split('\n')]
    def _add_dir_rule(self, rule, dirname, root):
        inv_path = os.path.join(dirname, '.arch-inventory')
        file(inv_path, "ab").write(rule)
        if os.path.realpath(inv_path) not in self._list_added(root):
            paranoid = self.paranoid
            self.paranoid = False
            self.add(inv_path)
            self.paranoid = paranoid
    def _force_source(self, path):
        rule = "source %s\n" % self._u_rel_path(path)
        self._add_dir_rule(rule, os.path.dirname(path), self.rootdir)
        if os.path.realpath(path) not in self._list_added(self.rootdir):
            raise CantAddFile(path)
    def _rcs_remove(self, path):
        if not '.arch-ids' in path:
            self._u_invoke_client("delete-id", path)
    def _rcs_update(self, path):
        pass
    def _rcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return file(self._u_abspath(path), "rb").read()
        else:
            status,output,error = \
                self._invoke_client("file-find", path, revision)
            path = output.rstrip('\n')
            return file(self._u_abspath(path), "rb").read()
    def _rcs_duplicate_repo(self, directory, revision=None):
        if revision == None:
            RCS._rcs_duplicate_repo(self, directory, revision)
        else:
            status,output,error = \
                self._u_invoke_client("get", revision,directory)
    def _rcs_commit(self, commitfile):
        summary,body = self._u_parse_commitfile(commitfile)
        #status,output,error = self._invoke_client("make-log")
        self._u_invoke_client("tree-root")
        self._u_invoke_client("tree-version")
        self._u_invoke_client("archives")
        if body == None:
            status,output,error \
                = self._u_invoke_client("commit","--summary",summary)
        else:
            status,output,error \
                = self._u_invoke_client("commit","--summary",summary,
                                        "--log-message",body)
        revision = None
        revline = re.compile("[*] committed (.*)")
        match = revline.search(output)
        assert match != None, output+error
        assert len(match.groups()) == 1
        revpath = match.groups()[0]
        assert not " " in revpath, revpath
        assert revpath.startswith(self._archive_project_name()+'--')
        revision = revpath[len(self._archive_project_name()+'--'):]
        return revpath

class CantAddFile(Exception):
    def __init__(self, file):
        self.file = file
        Exception.__init__(self, "Can't automatically add file %s" % file)
    
class ArchTestCase(RCStestCase):
    Class = Arch

unitsuite = unittest.TestLoader().loadTestsFromTestCase(ArchTestCase)
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
