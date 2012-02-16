# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Ben Finney <benf@cybersource.com.au>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Phil Schumm <philschumm@gmail.com>
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

"""Mercurial_ (hg) backend.

.. _Mercurial: http://mercurial.selenic.com/
"""

try:
    import mercurial
    import mercurial.dispatch
    import mercurial.ui
except ImportError:
    mercurial = None

try:
    # mercurial >= 1.2
    from mercurial.util import version
except ImportError:
    try:
        # mercurial <= 1.1.2
        from mercurial.version import get_version as version
    except ImportError:
        version = None

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
    """:class:`base.VCS` implementation for Mercurial.
    """
    name='hg'
    client=None # mercurial module

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self.__updated = [] # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_version(self):
        if version == None:
            return None
        return version()

    def _u_invoke_client(self, *args, **kwargs):
        if 'cwd' not in kwargs:
            kwargs['cwd'] = self.repo
        assert len(kwargs) == 1, kwargs
        fullargs = ['--cwd', kwargs['cwd']]
        fullargs.extend(args)
        cwd = os.getcwd()
        output = StringIO.StringIO()
        if self.version_cmp(1,9) >= 0:
            req = mercurial.dispatch.request(fullargs, fout=output)
            mercurial.dispatch.dispatch(req)
        else:
            stdout = sys.stdout
            sys.stdout = output
            mercurial.dispatch.dispatch(fullargs)
            sys.stdout = stdout
        os.chdir(cwd)
        return output.getvalue().rstrip('\n')

    def _vcs_get_user_id(self):
        output = self._u_invoke_client(
            'showconfig', 'ui.username').rstrip('\n')
        if output != '':
            return output
        return None

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
        manifest = self._u_invoke_client(
            'manifest', '--rev', revision).splitlines()
        return self._u_find_id_from_manifest(id, manifest, revision=revision)

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

    def _diff(self, revision):
        return self._u_invoke_client(
            'diff', '-r', revision, '--git')

    def _parse_diff(self, diff_text):
        """_parse_diff(diff_text) -> (new,modified,removed)

        `new`, `modified`, and `removed` are lists of files.

        Example diff text::
                
          diff --git a/.be/dir/bugs/modified b/.be/dir/bugs/modified
          --- a/.be/dir/bugs/modified
          +++ b/.be/dir/bugs/modified
          @@ -1,1 +1,1 @@ some value to be modified
          -some value to be modified
          \ No newline at end of file
          +a new value
          \ No newline at end of file
          diff --git a/.be/dir/bugs/moved b/.be/dir/bugs/moved
          deleted file mode 100644
          --- a/.be/dir/bugs/moved
          +++ /dev/null
          @@ -1,1 +0,0 @@
          -this entry will be moved
          \ No newline at end of file
          diff --git a/.be/dir/bugs/moved2 b/.be/dir/bugs/moved2
          new file mode 100644
          --- /dev/null
          +++ b/.be/dir/bugs/moved2
          @@ -0,0 +1,1 @@
          +this entry will be moved
          \ No newline at end of file
          diff --git a/.be/dir/bugs/new b/.be/dir/bugs/new
          new file mode 100644
          --- /dev/null
          +++ b/.be/dir/bugs/new
          @@ -0,0 +1,1 @@
          +this entry is new
          \ No newline at end of file
          diff --git a/.be/dir/bugs/removed b/.be/dir/bugs/removed
          deleted file mode 100644
          --- a/.be/dir/bugs/removed
          +++ /dev/null
          @@ -1,1 +0,0 @@
          -this entry will be deleted
          \ No newline at end of file
        """
        new = []
        modified = []
        removed = []
        lines = diff_text.splitlines()
        for i,line in enumerate(lines):
            if not line.startswith('diff '):
                continue
            file_a,file_b = line.split()[-2:]
            assert file_a.startswith('a/'), \
                'missformed file_a %s' % file_a
            assert file_b.startswith('b/'), \
                'missformed file_a %s' % file_b
            file = file_a[2:]
            assert file_b[2:] == file, \
                'diff file missmatch %s != %s' % (file_a, file_b)
            if lines[i+1].startswith('new '):
                new.append(file)
            elif lines[i+1].startswith('deleted '):
                removed.append(file)
            else:
                modified.append(file)
        return (new,modified,removed)

    def _vcs_changed(self, revision):
        return self._parse_diff(self._diff(revision))


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Hg, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
