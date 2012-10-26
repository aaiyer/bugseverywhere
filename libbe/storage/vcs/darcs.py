# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@tremily.us>
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

"""Darcs_ backend.

.. _Darcs: http://darcs.net/
"""

import codecs
import os
import re
import shutil
import sys
import time # work around http://mercurial.selenic.com/bts/issue618
import types
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
from xml.sax.saxutils import unescape

import libbe
from ...util.subproc import CommandError
from . import base

if libbe.TESTING == True:
    import doctest
    import unittest


def new():
    return Darcs()

class Darcs(base.VCS):
    """:py:class:`base.VCS` implementation for Darcs.
    """
    name='darcs'
    client='darcs'

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self.__updated = [] # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_version(self):
        try:
            status,output,error = self._u_invoke_client('--version')
        except CommandError:  # command not found?
            return None
        return output.strip()

    def version_cmp(self, *args):
        """Compare the installed Darcs version `V_i` with another version
        `V_o` (given in `*args`).  Returns

           === ===============
            1  if `V_i > V_o`
            0  if `V_i == V_o`
           -1  if `V_i < V_o`
           === ===============

        Examples
        --------

        >>> d = Darcs(repo='.')
        >>> d._version = '2.3.1 (release)'
        >>> d.version_cmp(2,3,1)
        0
        >>> d.version_cmp(2,3,2)
        -1
        >>> d.version_cmp(2,3,0)
        1
        >>> d.version_cmp(3)
        -1
        >>> d._version = '2.0.0pre2'
        >>> d._parsed_version = None
        >>> d.version_cmp(3)
        -1
        >>> d.version_cmp(2,0,1)
        Traceback (most recent call last):
          ...
        NotImplementedError: Cannot parse non-integer portion "0pre2" of Darcs version "2.0.0pre2"
        """
        if not hasattr(self, '_parsed_version') \
                or self._parsed_version == None:
            num_part = self.version().split(' ')[0]
            self._parsed_version = []
            for num in num_part.split('.'):
                try:
                    self._parsed_version.append(int(num))
                except ValueError, e:
                    self._parsed_version.append(num)
        for current,other in zip(self._parsed_version, args):
            if type(current) != types.IntType:
                raise NotImplementedError(
                    'Cannot parse non-integer portion "%s" of Darcs version "%s"'
                    % (current, self.version()))
            c = cmp(current,other)
            if c != 0:
                return c
        return 0

    def _vcs_get_user_id(self):
        # following http://darcs.net/manual/node4.html#SECTION00410030000000000000
        # as of June 22th, 2010
        if self.repo == None:
            return None
        for pref_file in ['author', 'email']:
            for prefs_dir in [os.path.join(self.repo, '_darcs', 'prefs'),
                              os.path.expanduser(os.path.join('~', '.darcs'))]:
                if prefs_dir == None:
                    continue
                pref_path = os.path.join(prefs_dir, pref_file)
                if os.path.exists(pref_path):
                    return self._vcs_get_file_contents(pref_path).strip()
        for env_variable in ['DARCS_EMAIL', 'EMAIL']:
            if env_variable in os.environ:
                return os.environ[env_variable]
        return None

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
        darcs_dir = self._u_search_parent_directories(path, '_darcs')
        if darcs_dir == None:
            return None
        return os.path.dirname(darcs_dir)

    def _vcs_init(self, path):
        self._u_invoke_client('init', cwd=path)

    def _vcs_destroy(self):
        vcs_dir = os.path.join(self.repo, '_darcs')
        if os.path.exists(vcs_dir):
            shutil.rmtree(vcs_dir)

    def _vcs_add(self, path):
        if os.path.isdir(path):
            return
        if self.version_cmp(0, 9, 10) == 1:
            self._u_invoke_client('add', '--boring', path)
        else:  # really old versions <= 0.9.10 lack --boring
            self._u_invoke_client('add', path)

    def _vcs_remove(self, path):
        if not os.path.isdir(self._u_abspath(path)):
            os.remove(os.path.join(self.repo, path)) # darcs notices removal

    def _vcs_update(self, path):
        self.__updated.append(path) # work around http://mercurial.selenic.com/bts/issue618
        pass # darcs notices changes

    def _vcs_get_file_contents(self, path, revision=None):
        if revision == None:
            return base.VCS._vcs_get_file_contents(self, path, revision)
        if self.version_cmp(2, 0, 0) == 1:
            status,output,error = self._u_invoke_client( \
                'show', 'contents', '--patch', revision, path)
            return output
        # Darcs versions < 2.0.0pre2 lack the 'show contents' command

        patch = self._diff(revision, path=path, unicode_output=False)

        # '--output -' to be supported in GNU patch > 2.5.9
        # but that hasn't been released as of June 30th, 2009.

        # Rewrite path to status before the patch we want
        args=['patch', '--reverse', path]
        status,output,error = self._u_invoke(args, stdin=patch)

        if os.path.exists(os.path.join(self.repo, path)) == True:
            contents = base.VCS._vcs_get_file_contents(self, path)
        else:
            contents = ''

        # Now restore path to it's current incarnation
        args=['patch', path]
        status,output,error = self._u_invoke(args, stdin=patch)
        return contents

    def _vcs_path(self, id, revision):
        return self._u_find_id(id, revision)

    def _vcs_isdir(self, path, revision):
        if self.version_cmp(2, 3, 1) == 1:
            # Sun Nov 15 20:32:06 EST 2009  thomashartman1@gmail.com
            #   * add versioned show files functionality (darcs show files -p 'some patch')
            status,output,error = self._u_invoke_client( \
                'show', 'files', '--no-files', '--patch', revision)
            children = output.rstrip('\n').splitlines()
            rpath = '.'
            children = [self._u_rel_path(c, rpath) for c in children]
            if path in children:
                return True
            return False
        raise NotImplementedError(
            'Darcs versions <= 2.3.1 lack the --patch option for "show files"')

    def _vcs_listdir(self, path, revision):
        if self.version_cmp(2, 3, 1) == 1:
            # Sun Nov 15 20:32:06 EST 2009  thomashartman1@gmail.com
            #   * add versioned show files functionality (darcs show files -p 'some patch')
            # Wed Dec  9 05:42:21 EST 2009  Luca Molteni <volothamp@gmail.com>
            #   * resolve issue835 show file with file directory arguments
            path = path.rstrip(os.path.sep)
            status,output,error = self._u_invoke_client( \
                'show', 'files', '--patch', revision, path)
            files = output.rstrip('\n').splitlines()
            if path == '.':
                descendents = [self._u_rel_path(f, path) for f in files
                               if f != '.']
            else:
                rel_files = [self._u_rel_path(f, path) for f in files]
                descendents = [f for f in rel_files
                               if f != '.' and not f.startswith('..')]
            return [f for f in descendents if f.count(os.path.sep) == 0]
        # Darcs versions <= 2.3.1 lack the --patch option for 'show files'
        raise NotImplementedError

    def _vcs_commit(self, commitfile, allow_empty=False):
        id = self.get_user_id()
        if id == None or '@' not in id:
            id = '%s <%s@invalid.com>' % (id, id)
        args = ['record', '--all', '--author', id, '--logfile', commitfile]
        status,output,error = self._u_invoke_client(*args)
        empty_strings = ['No changes!']
        # work around http://mercurial.selenic.com/bts/issue618
        if self._u_any_in_string(empty_strings, output) == True \
                and len(self.__updated) > 0:
            time.sleep(1)
            for path in self.__updated:
                os.utime(os.path.join(self.repo, path), None)
            status,output,error = self._u_invoke_client(*args)
        self.__updated = []
        # end work around
        if self._u_any_in_string(empty_strings, output) == True:
            if allow_empty == False:
                raise base.EmptyCommit()
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

    def _revisions(self):
        """
        Return a list of revisions in the repository.
        """
        status,output,error = self._u_invoke_client('changes', '--xml')
        revisions = []
        xml_str = output.encode('unicode_escape').replace(r'\n', '\n')
        element = ElementTree.XML(xml_str)
        assert element.tag == 'changelog', element.tag
        for patch in element.getchildren():
            assert patch.tag == 'patch', patch.tag
            for child in patch.getchildren():
                if child.tag == 'name':
                    text = unescape(unicode(child.text).decode('unicode_escape').strip())
                    revisions.append(text)
        revisions.reverse()
        return revisions

    def _vcs_revision_id(self, index):
        revisions = self._revisions()
        try:
            if index > 0:
                return revisions[index-1]
            elif index < 0:
                return revisions[index]
            else:
                return None
        except IndexError:
            return None

    def _diff(self, revision, path=None, unicode_output=True):
        revisions = self._revisions()
        i = revisions.index(revision)
        args = ['diff', '--unified']
        if i+1 < len(revisions):
            next_rev = revisions[i+1]
            args.extend(['--from-patch', next_rev])
        if path != None:
            args.append(path)
        kwargs = {'unicode_output':unicode_output}
        status,output,error = self._u_invoke_client(
            *args, **kwargs)
        return output

    def _parse_diff(self, diff_text):
        """_parse_diff(diff_text) -> (new,modified,removed)

        `new`, `modified`, and `removed` are lists of files.

        Example diff text::

          Mon Jan 18 15:19:30 EST 2010  None <None@invalid.com>
            * Final state
          diff -rN --unified old-BEtestgQtDuD/.be/dir/bugs/modified new-BEtestgQtDuD/.be/dir/bugs/modified
          --- old-BEtestgQtDuD/.be/dir/bugs/modified      2010-01-18 15:19:30.000000000 -0500
          +++ new-BEtestgQtDuD/.be/dir/bugs/modified      2010-01-18 15:19:30.000000000 -0500
          @@ -1 +1 @@
          -some value to be modified
          \ No newline at end of file
          +a new value
          \ No newline at end of file
          diff -rN --unified old-BEtestgQtDuD/.be/dir/bugs/moved new-BEtestgQtDuD/.be/dir/bugs/moved
          --- old-BEtestgQtDuD/.be/dir/bugs/moved 2010-01-18 15:19:30.000000000 -0500
          +++ new-BEtestgQtDuD/.be/dir/bugs/moved 1969-12-31 19:00:00.000000000 -0500
          @@ -1 +0,0 @@
          -this entry will be moved
          \ No newline at end of file
          diff -rN --unified old-BEtestgQtDuD/.be/dir/bugs/moved2 new-BEtestgQtDuD/.be/dir/bugs/moved2
          --- old-BEtestgQtDuD/.be/dir/bugs/moved2        1969-12-31 19:00:00.000000000 -0500
          +++ new-BEtestgQtDuD/.be/dir/bugs/moved2        2010-01-18 15:19:30.000000000 -0500
          @@ -0,0 +1 @@
          +this entry will be moved
          \ No newline at end of file
          diff -rN --unified old-BEtestgQtDuD/.be/dir/bugs/new new-BEtestgQtDuD/.be/dir/bugs/new
          --- old-BEtestgQtDuD/.be/dir/bugs/new   1969-12-31 19:00:00.000000000 -0500
          +++ new-BEtestgQtDuD/.be/dir/bugs/new   2010-01-18 15:19:30.000000000 -0500
          @@ -0,0 +1 @@
          +this entry is new
          \ No newline at end of file
          diff -rN --unified old-BEtestgQtDuD/.be/dir/bugs/removed new-BEtestgQtDuD/.be/dir/bugs/removed
          --- old-BEtestgQtDuD/.be/dir/bugs/removed       2010-01-18 15:19:30.000000000 -0500
          +++ new-BEtestgQtDuD/.be/dir/bugs/removed       1969-12-31 19:00:00.000000000 -0500
          @@ -1 +0,0 @@
          -this entry will be deleted
          \ No newline at end of file
          
        """
        new = []
        modified = []
        removed = []
        lines = diff_text.splitlines()
        repodir = os.path.basename(self.repo) + os.path.sep
        i = 0
        while i < len(lines):
            line = lines[i]; i += 1
            if not line.startswith('diff '):
                continue
            file_a,file_b = line.split()[-2:]
            assert file_a.startswith('old-'), \
                'missformed file_a %s' % file_a
            assert file_b.startswith('new-'), \
                'missformed file_a %s' % file_b
            file = file_a[4:]
            assert file_b[4:] == file, \
                'diff file missmatch %s != %s' % (file_a, file_b)
            assert file.startswith(repodir), \
                'missformed file_a %s' % file_a
            file = file[len(repodir):]
            lines_added = 0
            lines_removed = 0
            line = lines[i]; i += 1
            assert line.startswith('--- old-'), \
                'missformed "---" line %s' % line
            time_a = line.split('\t')[1]
            line = lines[i]; i += 1
            assert line.startswith('+++ new-'), \
                'missformed "+++" line %s' % line
            time_b = line.split('\t')[1]
            zero_time = time.strftime('%Y-%m-%d %H:%M:%S.000000000 ',
                                      time.localtime(0))
            # note that zero_time is missing the trailing timezone offset
            if time_a.startswith(zero_time):
                new.append(file)
            elif time_b.startswith(zero_time):
                removed.append(file)
            else:
                modified.append(file)
        return (new,modified,removed)

    def _vcs_changed(self, revision):
        return self._parse_diff(self._diff(revision))


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Darcs, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
