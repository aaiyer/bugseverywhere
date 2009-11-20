# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Ben Finney <benf@cybersource.com.au>
#                         Gianluca Montecchi <gian@grys.it>
#                         James Rowe <jnrowe@ukfsn.org>
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
GNU Arch (tla) backend.
"""

import codecs
import os
import re
import shutil
import sys
import time
import unittest
import doctest

from beuuid import uuid_gen
import config
import vcs



DEFAULT_CLIENT = "tla"

client = config.get_val("arch_client", default=DEFAULT_CLIENT)

def new():
    return Arch()

class Arch(vcs.VCS):
    name = "arch"
    client = client
    versioned = True
    _archive_name = None
    _archive_dir = None
    _tmp_archive = False
    _project_name = None
    _tmp_project = False
    _arch_paramdir = os.path.expanduser("~/.arch-params")
    def _vcs_version(self):
        status,output,error = self._u_invoke_client("--version")
        return output
    def _vcs_detect(self, path):
        """Detect whether a directory is revision-controlled using Arch"""
        if self._u_search_parent_directories(path, "{arch}") != None :
            config.set_val("arch_client", client)
            return True
        return False
    def _vcs_init(self, path):
        self._create_archive(path)
        self._create_project(path)
        self._add_project_code(path)
    def _create_archive(self, path):
        """
        Create a temporary Arch archive in the directory PATH.  This
        archive will be removed by
          cleanup->_vcs_cleanup->_remove_archive
        """
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
                              self._archive_dir, cwd=path)
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
          cleanup->_vcs_cleanup->_remove_project
        """
        # http://mwolson.org/projects/GettingStartedWithArch.html
        # http://regexps.srparish.net/tutorial-tla/new-project.html#Starting_a_New_Project
        category = "bugs-everywhere"
        branch = "mainline"
        version = "0.1"
        self._project_name = "%s--%s--%s" % (category, branch, version)
        self._invoke_client("archive-setup", self._project_name,
                            cwd=path)
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
        f = codecs.open(tagpath, "r", self.encoding)
        for line in f:
            if line.startswith("source "):
                lines_out.append("source ^[._=a-zA-X0-9].*$\n")
            else:
                lines_out.append(line)
        f.close()
        f = codecs.open(tagpath, "w", self.encoding)
        f.write("".join(lines_out))
        f.close()

    def _add_project_code(self, path):
        # http://mwolson.org/projects/GettingStartedWithArch.html
        # http://regexps.srparish.net/tutorial-tla/new-source.html
        # http://regexps.srparish.net/tutorial-tla/importing-first.html
        self._invoke_client("init-tree", self._project_name,
                            cwd=path)
        self._adjust_naming_conventions(path)
        self._invoke_client("import", "--summary", "Began versioning",
                            cwd=path)
    def _vcs_cleanup(self):
        if self._tmp_project == True:
            self._remove_project()
        if self._tmp_archive == True:
            self._remove_archive()

    def _vcs_root(self, path):
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
        status,output,error = self._u_invoke_client("tree-version", cwd=root)
        # e.g output
        # jdoe@example.com--bugs-everywhere-auto-2008.22.24.52/be--mainline--0.1
        archive_name,project_name = output.rstrip('\n').split('/')
        self._archive_name = archive_name
        self._project_name = project_name
    def _vcs_get_user_id(self):
        try:
            status,output,error = self._u_invoke_client('my-id')
            return output.rstrip('\n')
        except Exception, e:
            if 'no arch user id set' in e.args[0]:
                return None
            else:
                raise
    def _vcs_set_user_id(self, value):
        self._u_invoke_client('my-id', value)
    def _vcs_add(self, path):
        self._u_invoke_client("add-id", path)
        realpath = os.path.realpath(self._u_abspath(path))
        pathAdded = realpath in self._list_added(self.rootdir)
        if self.paranoid and not pathAdded:
            self._force_source(path)
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
        f = codecs.open(inv_path, "a", self.encoding)
        f.write(rule)
        f.close()
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
    def _vcs_remove(self, path):
        if not '.arch-ids' in path:
            self._u_invoke_client("delete-id", path)
    def _vcs_update(self, path):
        pass
    def _vcs_get_file_contents(self, path, revision=None, binary=False):
        if revision == None:
            return vcs.VCS._vcs_get_file_contents(self, path, revision, binary=binary)
        else:
            status,output,error = \
                self._invoke_client("file-find", path, revision)
            relpath = output.rstrip('\n')
            abspath = os.path.join(self.rootdir, relpath)
            f = codecs.open(abspath, "r", self.encoding)
            contents = f.read()
            f.close()
            return contents
    def _vcs_duplicate_repo(self, directory, revision=None):
        if revision == None:
            vcs.VCS._vcs_duplicate_repo(self, directory, revision)
        else:
            status,output,error = \
                self._u_invoke_client("get", revision, directory)
    def _vcs_commit(self, commitfile, allow_empty=False):
        if allow_empty == False:
            # arch applies empty commits without complaining, so check first
            status,output,error = self._u_invoke_client("changes",expect=(0,1))
            if status == 0:
                raise vcs.EmptyCommit()
        summary,body = self._u_parse_commitfile(commitfile)
        args = ["commit", "--summary", summary]
        if body != None:
            args.extend(["--log-message",body])
        status,output,error = self._u_invoke_client(*args)
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
    def _vcs_revision_id(self, index):
        status,output,error = self._u_invoke_client("logs")
        logs = output.splitlines()
        first_log = logs.pop(0)
        assert first_log == "base-0", first_log
        try:
            log = logs[index]
        except IndexError:
            return None
        return "%s--%s" % (self._archive_project_name(), log)

class CantAddFile(Exception):
    def __init__(self, file):
        self.file = file
        Exception.__init__(self, "Can't automatically add file %s" % file)



vcs.make_vcs_testcase_subclasses(Arch, sys.modules[__name__])

unitsuite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
