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

try:
    # enable importing on demand to reduce startup time
    from mercurial import demandimport; demandimport.enable()
    import mercurial
    import mercurial.version
    import mercurial.dispatch
    import mercurial.ui
except ImportError:
    mercurial = None
import os
import os.path
import re
import shutil
import StringIO
import sys
import time # work around http://mercurial.selenic.com/bts/issue618

import libbe
import base

if libbe.TESTING == True:
    import doctest
    import unittest


def new():
    return Hg()

class Hg(base.VCS):
    name='hg'
    client=None # mercurial module

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self.__updated = [] # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_version(self):
        if mercurial == None:
            return None
        return mercurial.version.get_version()

    def _u_invoke_client(self, *args, **kwargs):
        if 'cwd' not in kwargs:
            kwargs['cwd'] = self.repo
        assert len(kwargs) == 1, kwargs
        fullargs = ['--cwd', kwargs['cwd']]
        fullargs.extend(args)
        stdout = sys.stdout
        tmp_stdout = StringIO.StringIO()
        sys.stdout = tmp_stdout
        mercurial.dispatch.dispatch(fullargs)
        sys.stdout = stdout
        return tmp_stdout.getvalue().rstrip('\n')

    def _vcs_get_user_id(self):
        return self._u_invoke_client('showconfig', 'ui.username')

    def _vcs_detect(self, path):
        """Detect whether a directory is revision-controlled using Mercurial"""
        if self._u_search_parent_directories(path, '.hg') != None:
            return True
        return False

    def _vcs_root(self, path):
        return self._u_invoke_client('root', cwd=path)

    def _vcs_init(self, path):
        self._u_invoke_client('init', cwd=path)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '.hg')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)

    def _vcs_add(self, path):
        self._u_invoke_client('add', path)

    def _vcs_remove(self, path):
        self._u_invoke_client('rm', '--force', path)

    def _vcs_update(self, path):
        self.__updated.append(path) # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        else:
            return self._u_invoke_client('cat', '-r', revision, path)

    def _vcs_path(self, id, revision):
        output = self._u_invoke_client('manifest', '--rev', revision)
        be_dir = self._cached_path_id._spacer_dirs[0]
        be_dir_sep = self._cached_path_id._spacer_dirs[0] + os.path.sep
        files = [f for f in output.splitlines() if f.startswith(be_dir_sep)]
        for file in files:
            if not file.startswith(be_dir+os.path.sep):
                continue
            parts = file.split(os.path.sep)
            dir = parts.pop(0) # don't add the first spacer dir
            for part in parts[:-1]:
                dir = os.path.join(dir, part)
                if not dir in files:
                    files.append(dir)
        for file in files:
            if self._u_path_to_id(file) == id:
                return file
        raise base.InvalidId(id, revision=revision)

    def _vcs_isdir(self, path, revision):
        output = self._u_invoke_client('manifest', '--rev', revision)
        files = output.splitlines()
        if path in files:
            return False
        return True

    def _vcs_listdir(self, path, revision):
        output = self._u_invoke_client('manifest', '--rev', revision)
        files = output.splitlines()
        path = path.rstrip(os.path.sep) + os.path.sep
        return [self._u_rel_path(f, path) for f in files if f.startswith(path)]

    def _vcs_commit(self, commitfile, allow_empty=False):
        args = ['commit', '--logfile', commitfile]
        output = self._u_invoke_client(*args)
        # work around http://mercurial.selenic.com/bts/issue618
        strings = ['nothing changed']
        if self._u_any_in_string(strings, output) == True \
                and len(self.__updated) > 0:
            time.sleep(1)
            for path in self.__updated:
                os.utime(os.path.join(self.repo, path), None)
            output = self._u_invoke_client(*args)
        self.__updated = []
        # end work around
        if allow_empty == False:
            strings = ['nothing changed']
            if self._u_any_in_string(strings, output) == True:
                raise base.EmptyCommit()
        return self._vcs_revision_id(-1)

    def _vcs_revision_id(self, index, style='id'):
        if index > 0:
            index -= 1
        args = ['identify', '--rev', str(int(index)), '--%s' % style]
        output = self._u_invoke_client(*args)
        id = output.strip()
        if id == '000000000000':
            return None # before initial commit.
        return id


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Hg, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
