# Copyright (C) 2009 Gianluca Montecchi <gian@grys.it>
#                    W. Trevor King <wking@drexel.edu>
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
Darcs backend.
"""

import codecs
import os
import re
import shutil
import sys
import time # work around http://mercurial.selenic.com/bts/issue618
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
from xml.sax.saxutils import unescape

import libbe
import base

if libbe.TESTING == True:
    import doctest
    import unittest


def new():
    return Darcs()

class Darcs(base.VCS):
    name='darcs'
    client='darcs'

    def __init__(self, *args, **kwargs):
        base.VCS.__init__(self, *args, **kwargs)
        self.versioned = True
        self.__updated = [] # work around http://mercurial.selenic.com/bts/issue618

    def _vcs_version(self):
        status,output,error = self._u_invoke_client('--version')
        return output.rstrip('\n')

    def version_cmp(self, *args):
        """
        Compare the installed darcs version V_i with another version
        V_o (given in *args).  Returns
           1 if V_i > V_o,
           0 if V_i == V_o, and
          -1 if V_i < V_o
        >>> d = Darcs(repo='.')
        >>> d._vcs_version = lambda : "2.3.1 (release)"
        >>> d.version_cmp(2,3,1)
        0
        >>> d.version_cmp(2,3,2)
        -1
        >>> d.version_cmp(2,3,0)
        1
        >>> d.version_cmp(3)
        -1
        >>> d._vcs_version = lambda : "2.0.0pre2"
        >>> d._parsed_version = None
        >>> d.version_cmp(3)
        Traceback (most recent call last):
          ...
        NotImplementedError: Cannot parse "2.0.0pre2" portion of Darcs version "2.0.0pre2"
          invalid literal for int() with base 10: '0pre2'
        """
        if not hasattr(self, '_parsed_version') \
                or self._parsed_version == None:
            num_part = self._vcs_version().split(' ')[0]
            try:
                self._parsed_version = [int(i) for i in num_part.split('.')]
            except ValueError, e:
                raise NotImplementedError(
                    'Cannot parse "%s" portion of Darcs version "%s"\n  %s'
                    % (num_part, self._vcs_version(), str(e)))
        cmps = [cmp(a,b) for a,b in zip(self._parsed_version, args)]
        for c in cmps:
            if c != 0:
                return c
        return 0

    def _vcs_get_user_id(self):
        # following http://darcs.net/manual/node4.html#SECTION00410030000000000000
        # as of June 29th, 2009
        if self.repo == None:
            return None
        darcs_dir = os.path.join(self.repo, '_darcs')
        if darcs_dir != None:
            for pref_file in ['author', 'email']:
                pref_path = os.path.join(darcs_dir, 'prefs', pref_file)
                if os.path.exists(pref_path):
                    return self.get_file_contents(pref_path)
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

        status,output,error = self._u_invoke_client( \
            'diff', '--unified', '--from-patch', revision, path,
            unicode_output=False)
        major_patch = output
        status,output,error = self._u_invoke_client( \
            'diff', '--unified', '--patch', revision, path,
            unicode_output=False)
        target_patch = output

        # '--output -' to be supported in GNU patch > 2.5.9
        # but that hasn't been released as of June 30th, 2009.

        # Rewrite path to status before the patch we want
        args=['patch', '--reverse', path]
        status,output,error = self._u_invoke(args, stdin=major_patch)
        # Now apply the patch we want
        args=['patch', path]
        status,output,error = self._u_invoke(args, stdin=target_patch)

        if os.path.exists(os.path.join(self.repo, path)) == True:
            contents = base.VCS._vcs_get_file_contents(self, path)
        else:
            contents = ''

        # Now restore path to it's current incarnation
        args=['patch', '--reverse', path]
        status,output,error = self._u_invoke(args, stdin=target_patch)
        args=['patch', path]
        status,output,error = self._u_invoke(args, stdin=major_patch)
        current_contents = base.VCS._vcs_get_file_contents(self, path)
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
        # Darcs versions <= 2.3.1 lack the --patch option for 'show files'
        raise NotImplementedError

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
                descendents = [self._u_rel_path(f, path) for f in files
                               if f.startswith(path)]
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

    def _vcs_revision_id(self, index):
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
        try:
            if index > 0:
                return revisions[index-1]
            elif index < 0:
                return revisions[index]
            else:
                return None
        except IndexError:
            return None


if libbe.TESTING == True:
    base.make_vcs_testcase_subclasses(Darcs, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
