#!/usr/bin/python
#
# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
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

import os
import os.path
import shutil
import string
import sys

from libbe.util.subproc import Pipe, invoke


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
    status,stdout,stderr = invoke(['git', 'diff', 'HEAD'])
    if len(stdout) == 0:
        return False
    return True

def set_release_version(tag):
    print "set libbe.version._VERSION = '%s'" % tag
    invoke(['sed', '-i', "s/^[# ]*_VERSION *=.*/_VERSION = '%s'/" % tag,
            os.path.join('libbe', 'version.py')])

def remove_makefile_libbe_version_dependencies(filename):
    print "set %s LIBBE_VERSION :=" % filename
    invoke(['sed', '-i', "s/^LIBBE_VERSION *:=.*/LIBBE_VERSION :=/",
            filename])

def commit(commit_message):
    print 'commit current status:', commit_message
    invoke(['git', 'commit', '-a', '-m', commit_message])

def tag(tag):
    print 'tag current revision', tag
    invoke(['git', 'tag', tag])

def export(target_dir):
    if not target_dir.endswith(os.path.sep):
        target_dir += os.path.sep
    print 'export current revision to', target_dir
    p = Pipe([['git', 'archive', '--prefix', target_dir, 'HEAD'],
              ['tar', '-xv']])
    assert p.status == 0, p.statuses

def make_version():
    print 'generate libbe/_version.py'
    invoke(['make', os.path.join('libbe', '_version.py')])

def make_changelog(filename, tag):
    """Generate a ChangeLog from the git history.

    Not the most ChangeLog-esque format, but iterating through commits
    by hand is just too slow.
    """
    print 'generate ChangeLog file', filename, 'up to tag', tag
    invoke(['git', 'log', '--no-merges',
            '%s..%s' % (INITIAL_COMMIT, tag)],
           stdout=open(filename, 'w')),

def set_vcs_name(be_dir, vcs_name='None'):
    """Exported directory is not a git repository, so set vcs_name to
    something that will work.
      vcs_name: new_vcs_name
    """
    for directory in os.listdir(be_dir):
        if not os.path.isdir(os.path.join(be_dir, directory)):
            continue
        filename = os.path.join(be_dir, directory, 'settings')
        if os.path.exists(filename):
            print 'set vcs_name in', filename, 'to', vcs_name
            invoke(['sed', '-i', "s/^vcs_name:.*/vcs_name: %s/" % vcs_name,
                    filename])

def make_id_cache():
    """Generate .be/id-cache so users won't need to.
    """
    invoke(['./be', 'list'])

def create_tarball(tag):
    release_name='be-%s' % tag
    export_dir = release_name
    export(export_dir)
    make_version()
    remove_makefile_libbe_version_dependencies(
        os.path.join(export_dir, 'Makefile'))
    print 'copy libbe/_version.py to %s/libbe/_version.py' % export_dir
    shutil.copy(os.path.join('libbe', '_version.py'),
                os.path.join(export_dir, 'libbe', '_version.py'))
    make_changelog(os.path.join(export_dir, 'ChangeLog'), tag)
    make_id_cache()
    print 'copy .be/id-cache to %s/.be/id-cache' % export_dir
    shutil.copy(os.path.join('.be', 'id-cache'),
                os.path.join(export_dir, '.be', 'id-cache'))
    set_vcs_name(os.path.join(export_dir, '.be'))
    tarball_file = '%s.tar.gz' % release_name
    print 'create tarball', tarball_file
    invoke(['tar', '-czf', tarball_file, export_dir])
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

If you don't like what got committed, you can undo the release with
  $ git tag -d 1.0.0
  $ git reset --hard HEAD^
"""
    p = optparse.OptionParser(usage)
    p.add_option('--test', dest='test', default=False,
                 action='store_true', help='Run internal tests and exit')
    options,args = p.parse_args()

    if options.test == True:
        test()
        sys.exit(0)

    assert len(args) == 1, '%d (!= 1) arguments: %s' % (len(args), args)
    _tag = args[0]
    validate_tag(_tag)

    if pending_changes() == True:
        print "Handle pending changes before releasing."
        sys.exit(1)
    set_release_version(_tag)
    print "Update copyright information..."
    env = dict(os.environ)
    pythonpath = os.path.abspath('update-copyright')
    if 'PYTHONPATH' in env:
        env['PYTHONPATH'] = '{}:{}'.format(pythonpath, env['PYTHONPATH'])
    else:
        env['PYTHONPATH'] = pythonpath
    status,stdout,stderr = invoke([
            os.path.join('update-copyright', 'bin', 'update-copyright.py')],
            env=env)
    commit("Bumped to version %s" % _tag)
    tag(_tag)
    create_tarball(_tag)
