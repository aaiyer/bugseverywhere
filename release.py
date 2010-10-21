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

from libbe.util.subproc import Pipe, invoke
from libbe.util.encoding import set_file_contents
from update_copyright import update_authors, update_files


INITIAL_COMMIT = '1bf1ec598b436f41ff27094eddf0b28c797e359d'


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

def pending_changes():
    """Use `git diff`s output to detect change.
    """
    p = Pipe([['git', 'diff', 'HEAD']])
    assert p.status == 0, p.statuses
    if len(p.stdout) == 0:
        return False
    return True

def set_release_version(tag):
    print "set libbe.version._VERSION = '%s'" % tag
    p = Pipe([['sed', '-i', "s/^# *_VERSION *=.*/_VERSION = '%s'/" % tag,
               os.path.join('libbe', 'version.py')]])
    assert p.status == 0, p.statuses

def remove_makefile_libbe_version_dependencies():
    print "set Makefile LIBBE_VERSION :="
    p = Pipe([['sed', '-i', "s/^LIBBE_VERSION *:=.*/LIBBE_VERSION :=/",
               'Makefile']])
    assert p.status == 0, p.statuses

def commit(commit_message):
    print 'commit current status:', commit_message
    p = Pipe([['git', 'commit', '-m', commit_message]])
    assert p.status == 0, p.statuses

def tag(tag):
    print 'tag current revision', tag
    p = Pipe([['git', 'tag', tag]])
    assert p.status == 0, p.statuses

def export(target_dir):
    print 'export current revision to', target_dir
    p = Pipe([['git', 'archive', '--prefix', target_dir, 'HEAD'],
              ['tar', '-xv']])
    assert p.status == 0, p.statuses

def make_version():
    print 'generate libbe/_version.py'
    p = Pipe([['make', os.path.join('libbe', '_version.py')]])
    assert p.status == 0, p.statuses

def make_changelog(filename, tag):
    """Generate a ChangeLog from the git history.

    Based on
      http://stackoverflow.com/questions/2976665/git-changelog-day-by-day
    """
    print 'generate ChangeLog file', filename, 'up to tag', tag
    p = invoke(['git', 'log', '--no-merges', '--format="%cd"', '--date=short',
                '%s..%s' % (INITIAL_COMMIT, tag)])
    days = sorted(set(p.stdout.split('\n')), reverse=True)
    log = []
    next = None
    for day in days:
        args = ['git', 'log', '--no-merges', '--format=" * s"', '--since', day]
        if next != None:
            args.extend(['--until', next])
        p = invoke(args)
        log.extend(['', day, p.stdout])
        next = day
    set_file_contents(filename, '\n'.join(log), encoding='utf-8')

def set_vcs_name(filename, vcs_name='None'):
    """Exported directory is not a git repository, so set vcs_name to
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
    export(export_dir)
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

Create a git tag and a release tarball from the current revision.
For example
  %prog 1.0.0

You may wish to test this out in a dummy branch first to make sure it
works as expected to avoid the tedium of unwinding the version-bump
commit if it fails.
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

    if pending_changes() == True:
        print "Handle pending changes before releasing."
        sys.exit(1)
    set_release_version(tag)
    update_authors()
    update_files()
    commit("Bumped to version %s" % tag)
    tag(tag)
    create_tarball(tag)
