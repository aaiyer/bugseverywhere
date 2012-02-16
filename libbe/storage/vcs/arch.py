# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Ben Finney <benf@cybersource.com.au>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         James Rowe <jnrowe@ukfsn.org>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""GNU Arch_ (tla) backend.

.. _Arch: http://www.gnu.org/software/gnu-arch/
"""

import codecs
import os
import os.path
import re
import shutil
import sys
import time # work around http://mercurial.selenic.com/bts/issue618

import libbe
from ...ui.util import user as _user
from ...util.id import uuid_gen
from ...util.subproc import CommandError
from ..util import config as _config
from . import base

if libbe.TESTING == True:
    import unittest
    import doctest


class CantAddFile(Exception):
    def __init__(self, file):
        self.file = file
        Exception.__init__(self, "Can't automatically add file %s" % file)

DEFAULT_CLIENT = 'tla'

client = _config.get_val(
    'arch_client', default=DEFAULT_CLIENT)

def new():
    return Arch()

class Arch(base.VCS):
    """:class:`base.VCS` implementation for GNU Arch.
    """
    name = 'arch'
    client = client
    _archive_name = None
    _archive_dir = None
    _tmp_archive = False
    _project_name = None
    _tmp_project = False
    _arch_paramdir = os.path.expanduser('~/.arch-params')

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self.interspersed_vcs_files = True
        self.paranoid = False
        self.__updated = [] # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_version(self):
        try:
            status,output,error = self._u_invoke_client('--version')
        except CommandError:  # command not found?
            return None
        version = '\n'.join(output.splitlines()[:2])
        return version

    def _vcs_detect(self, path):
        """Detect whether a directory is revision-controlled using Arch"""
        if self._u_search_parent_directories(path, '{arch}') != None :
            _config.set_val('arch_client', client)
            return True
        return False

    def _vcs_init(self, path):
        self._create_archive(path)
        self._create_project(path)
        self._add_project_code(path)

    def _create_archive(self, path):
        """Create a temporary Arch archive in the directory PATH.  This
        archive will be removed by::

            destroy->_vcs_destroy->_remove_archive
        """
        # http://regexps.srparish.net/tutorial-tla/new-archive.html#Creating_a_New_Archive
        assert self._archive_name == None
        id = self.get_user_id()
        name, email = _user.parse_user_id(id)
        if email == None:
            email = '%s@example.com' % name
        trailer = '%s-%s' % ('bugs-everywhere-auto', uuid_gen()[0:8])
        self._archive_name = '%s--%s' % (email, trailer)
        self._archive_dir = '/tmp/%s' % trailer
        self._tmp_archive = True
        self._u_invoke_client('make-archive', self._archive_name,
                              self._archive_dir, cwd=path)

    def _invoke_client(self, *args, **kwargs):
        """Invoke the client on our archive.
        """
        assert self._archive_name != None
        command = args[0]
        if len(args) > 1:
            tailargs = args[1:]
        else:
            tailargs = []
        arglist = [command, '-A', self._archive_name]
        arglist.extend(tailargs)
        args = tuple(arglist)
        return self._u_invoke_client(*args, **kwargs)

    def _remove_archive(self):
        assert self._tmp_archive == True
        assert self._archive_dir != None
        assert self._archive_name != None
        os.remove(os.path.join(self._arch_paramdir,
                               '=locations', self._archive_name))
        shutil.rmtree(self._archive_dir)
        self._tmp_archive = False
        self._archive_dir = False
        self._archive_name = False

    def _create_project(self, path):
        """
        Create a temporary Arch project in the directory PATH.  This
        project will be removed by
          destroy->_vcs_destroy->_remove_project
        """
        # http://mwolson.org/projects/GettingStartedWithArch.html
        # http://regexps.srparish.net/tutorial-tla/new-project.html#Starting_a_New_Project
        category = 'bugs-everywhere'
        branch = 'mainline'
        version = '0.1'
        self._project_name = '%s--%s--%s' % (category, branch, version)
        self._invoke_client('archive-setup', self._project_name,
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
        return '%s/%s' % (self._archive_name, self._project_name)

    def _adjust_naming_conventions(self, path):
        """Adjust `Arch naming conventions`_ so ``.be`` is considered source
        code.

        By default, Arch restricts source code filenames to::

            ^[_=a-zA-Z0-9].*$

        Since our bug directory ``.be`` doesn't satisfy these conventions,
        we need to adjust them.  The conventions are specified in::

            project-root/{arch}/=tagging-method

        .. _Arch naming conventions:
          http://regexps.srparish.net/tutorial-tla/naming-conventions.html
        """
        tagpath = os.path.join(path, '{arch}', '=tagging-method')
        lines_out = []
        f = codecs.open(tagpath, 'r', self.encoding)
        for line in f:
            if line.startswith('source '):
                lines_out.append('source ^[._=a-zA-X0-9].*$\n')
            else:
                lines_out.append(line)
        f.close()
        f = codecs.open(tagpath, 'w', self.encoding)
        f.write(''.join(lines_out))
        f.close()

    def _add_project_code(self, path):
        # http://mwolson.org/projects/GettingStartedWithArch.html
        # http://regexps.srparish.net/tutorial-tla/new-source.html
        # http://regexps.srparish.net/tutorial-tla/importing-first.html
        self._invoke_client('init-tree', self._project_name,
                            cwd=path)
        self._adjust_naming_conventions(path)
        self._invoke_client('import', '--summary', 'Began versioning',
                            cwd=path)

    def _vcs_destroy(self):
        if self._tmp_project == True:
            self._remove_project()
        if self._tmp_archive == True:
            self._remove_archive()
        vcs_dir = os.path.join(self.repo, '{arch}')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)
        self._archive_name = None

    def _vcs_root(self, path):
        if not os.path.isdir(path):
            dirname = os.path.dirname(path)
        else:
            dirname = path
        status,output,error = self._u_invoke_client('tree-root', dirname)
        root = output.rstrip('\n')

        self._get_archive_project_name(root)

        return root

    def _get_archive_name(self, root):
        status,output,error = self._u_invoke_client('archives')
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
        status,output,error = self._u_invoke_client('tree-version', cwd=root)
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

    def _vcs_add(self, path):
        self._u_invoke_client('add-id', path)
        realpath = os.path.realpath(self._u_abspath(path))
        pathAdded = realpath in self._list_added(self.repo)
        if self.paranoid and not pathAdded:
            self._force_source(path)

    def _list_added(self, root):
        assert os.path.exists(root)
        assert os.access(root, os.X_OK)
        root = os.path.realpath(root)
        status,output,error = self._u_invoke_client('inventory', '--source',
                                                    '--both', '--all', root)
        inv_str = output.rstrip('\n')
        return [os.path.join(root, p) for p in inv_str.split('\n')]

    def _add_dir_rule(self, rule, dirname, root):
        inv_path = os.path.join(dirname, '.arch-inventory')
        f = codecs.open(inv_path, 'a', self.encoding)
        f.write(rule)
        f.close()
        if os.path.realpath(inv_path) not in self._list_added(root):
            paranoid = self.paranoid
            self.paranoid = False
            self.add(inv_path)
            self.paranoid = paranoid

    def _force_source(self, path):
        rule = 'source %s\n' % self._u_rel_path(path)
        self._add_dir_rule(rule, os.path.dirname(path), self.repo)
        if os.path.realpath(path) not in self._list_added(self.repo):
            raise CantAddFile(path)

    def _vcs_remove(self, path):
        if self._vcs_is_versioned(path):
            self._u_invoke_client('delete-id', path)
        arch_ids = os.path.join(self.repo, path, '.arch-ids')
        if os.path.exists(arch_ids):
            shutil.rmtree(arch_ids)

    def _vcs_update(self, path):
        self.__updated.append(path) # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_is_versioned(self, path):
        if '.arch-ids' in path:
            return False
        return True

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        else:
            relpath = self._file_find(path, revision, relpath=True)
            return base.VCS._vcs_get_file_contents(self, relpath)

    def _file_find(self, path, revision, relpath=False):
        try:
            status,output,error = \
                self._invoke_client(
                'file-find', '--unescaped', path, revision)
            path = output.rstrip('\n').splitlines()[-1]
        except CommandError, e:
            if e.status == 2 \
                    and 'illegally formed changeset index' in e.stderr:
                raise NotImplementedError(
"""Outstanding tla bug, see
  https://bugs.launchpad.net/ubuntu/+source/tla/+bug/513472
""")
            raise
        if relpath == True:
            return path
        return os.path.abspath(os.path.join(self.repo, path))

    def _vcs_path(self, id, revision):
        return self._u_find_id(id, revision)

    def _vcs_isdir(self, path, revision):
        abspath = self._file_find(path, revision)
        return os.path.isdir(abspath)

    def _vcs_listdir(self, path, revision):
        abspath = self._file_find(path, revision)
        return [p for p in os.listdir(abspath) if self._vcs_is_versioned(p)]

    def _vcs_commit(self, commitfile, allow_empty=False):
        if allow_empty == False:
            # arch applies empty commits without complaining, so check first
            status,output,error = self._u_invoke_client('changes',expect=(0,1))
            if status == 0:
                # work around http://mercurial.selenic.com/bts/issue618
                time.sleep(1)
                for path in self.__updated:
                    os.utime(os.path.join(self.repo, path), None)
                self.__updated = []
                status,output,error = self._u_invoke_client('changes',expect=(0,1))
                if status == 0:
                # end work around
                    raise base.EmptyCommit()
        summary,body = self._u_parse_commitfile(commitfile)
        args = ['commit', '--summary', summary]
        if body != None:
            args.extend(['--log-message',body])
        status,output,error = self._u_invoke_client(*args)
        revision = None
        revline = re.compile('[*] committed (.*)')
        match = revline.search(output)
        assert match != None, output+error
        assert len(match.groups()) == 1
        revpath = match.groups()[0]
        assert not " " in revpath, revpath
        assert revpath.startswith(self._archive_project_name()+'--')
        revision = revpath[len(self._archive_project_name()+'--'):]
        return revpath

    def _vcs_revision_id(self, index):
        status,output,error = self._u_invoke_client('logs')
        logs = output.splitlines()
        first_log = logs.pop(0)
        assert first_log == 'base-0', first_log
        try:
            if index > 0:
                log = logs[index-1]
            elif index < 0:
                log = logs[index]
            else:
                return None
        except IndexError:
            return None
        return '%s--%s' % (self._archive_project_name(), log)

    def _diff(self, revision):
        status,output,error = self._u_invoke_client(
            'diff', '--summary', '--unescaped', revision, expect=(0,1))
        return output
    
    def _parse_diff(self, diff_text):
        """
        Example diff text:
        
        * local directory is at ...
        * build pristine tree for ...
        * from import revision: ...
        * patching for revision: ...
        * comparing to ...
        D  .be/dir/bugs/.arch-ids/moved.id
        D  .be/dir/bugs/.arch-ids/removed.id
        D  .be/dir/bugs/moved
        D  .be/dir/bugs/removed
        A  .be/dir/bugs/.arch-ids/moved2.id
        A  .be/dir/bugs/.arch-ids/new.id
        A  .be/dir/bugs/moved2
        A  .be/dir/bugs/new
        A  {arch}/bugs-everywhere/bugs-everywhere--mainline/...
        M  .be/dir/bugs/modified
        """
        new = []
        modified = []
        removed = []
        lines = diff_text.splitlines()
        for i,line in enumerate(lines):
            if line.startswith('* ') or '/.arch-ids/' in line:
                continue
            change,file = line.split('  ',1)
            if  file.startswith('{arch}/'):
                continue
            if change == 'A':
                new.append(file)
            elif change == 'M':
                modified.append(file)
            elif change == 'D':
                removed.append(file)
        return (new,modified,removed)

    def _vcs_changed(self, revision):
        return self._parse_diff(self._diff(revision))


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Arch, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
