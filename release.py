#!/usr/bin/python
#
# Copyright (C) 2009-2010 W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 2 of the License, or (at your
# option) any later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

import os
import os.path
import shutil
import string
import sys

from libbe.subproc import Pipe, invoke
from update_copyright import update_authors, update_files

def validate_tag(tag):
    """
    >>> validate_tag('1.0.0')
    >>> validate_tag('A.B.C-r7')
    >>> validate_tag('A.B.C r7')
    Traceback (most recent call last):
      ...
    Exception: Invalid character ' ' in tag 'A.B.C r7'
    >>> validate_tag('"')
    Traceback (most recent call last):
      ...
    Exception: Invalid character '"' in tag '"'
    >>> validate_tag("'")
    Traceback (most recent call last):
      ...
    Exception: Invalid character ''' in tag '''
    """
    for char in tag:
        if char in string.digits:
            continue
        elif char in string.letters:
            continue
        elif char in ['.','-']:
            continue
        raise Exception("Invalid character '%s' in tag '%s'" % (char, tag))

def bzr_pending_changes():
    """Use `bzr diff`s exit status to detect change:
    1 - changed
    2 - unrepresentable changes
    3 - error
    0 - no change
    """
    p = Pipe([['bzr', 'diff']])
    if p.status == 0:
        return False
    elif p.status in [1,2]:
        return True
    raise Exception("Error in bzr diff %d\n%s" % (p.status, p.stderrs[-1]))

def set_release_version(tag):
    print "set libbe.version._VERSION = '%s'" % tag
    p = Pipe([['sed', '-i', "s/^# *_VERSION *=.*/_VERSION = '%s'/" % tag,
               os.path.join('libbe', 'version.py')]])
    assert p.status == 0, p.statuses

def bzr_commit(commit_message):
    print 'commit current status:', commit_message
    p = Pipe([['bzr', 'commit', '-m', commit_message]])
    assert p.status == 0, p.statuses

def bzr_tag(tag):
    print 'tag current revision', tag
    p = Pipe([['bzr', 'tag', tag]])
    assert p.status == 0, p.statuses

def bzr_export(target_dir):
    print 'export current revision to', target_dir
    p = Pipe([['bzr', 'export', target_dir]])
    assert p.status == 0, p.statuses

def make_version():
    print 'generate libbe/_version.py'
    p = Pipe([['make', os.path.join('libbe', '_version.py')]])
    assert p.status == 0, p.statuses

def make_changelog(filename, tag):
    print 'generate ChangeLog file', filename, 'up to tag', tag
    p = invoke(['bzr', 'log', '--gnu-changelog', '-n1', '-r',
                '..tag:%s' % tag], stdout=file(filename, 'w'))
    status = p.wait()
    assert status == 0, status

def set_vcs_name(filename, vcs_name='None'):
    """Exported directory is not a bzr repository, so set vcs_name to
    something that will work.
      vcs_name: new_vcs_name
    """
    print 'set vcs_name in', filename, 'to', vcs_name
    p = Pipe([['sed', '-i', "s/^vcs_name:.*/vcs_name: %s/" % vcs_name,
               filename]])
    assert p.status == 0, p.statuses

def create_tarball(tag):
    release_name='be-%s' % tag
    export_dir = release_name
    bzr_export(export_dir)
    make_version()
    print 'copy libbe/_version.py to %s/libbe/_version.py' % export_dir
    shutil.copy(os.path.join('libbe', '_version.py'),
                os.path.join(export_dir, 'libbe', '_version.py'))
    make_changelog(os.path.join(export_dir, 'ChangeLog'), tag)
    set_vcs_name(os.path.join(export_dir, '.be', 'settings'))
    tarball_file = '%s.tar.gz' % release_name
    print 'create tarball', tarball_file
    p = Pipe([['tar', '-czf', tarball_file, export_dir]])
    assert p.status == 0, p.statuses
    print 'remove', export_dir
    shutil.rmtree(export_dir)

def test():
    import doctest
    doctest.testmod() 

if __name__ == '__main__':
    import optparse
    usage = """%prog [options] TAG

Create a bzr tag and a release tarball from the current revision.
For example
  %prog 1.0.0
"""
    p = optparse.OptionParser(usage)
    p.add_option('--test', dest='test', default=False,
                 action='store_true', help='Run internal tests and exit')
    options,args = p.parse_args()

    if options.test == True:
        test()
        sys.exit(0)

    assert len(args) == 1, '%d (!= 1) arguments: %s' % (len(args), args)
    tag = args[0]
    validate_tag(tag)

    if bzr_pending_changes() == True:
        print "Handle pending changes before releasing."
        sys.exit(1)
    set_release_version(tag)
    update_authors()
    update_files()
    bzr_commit("Bumped to version %s" % tag)
    bzr_tag(tag)
    create_tarball(tag)
