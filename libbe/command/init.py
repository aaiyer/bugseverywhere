# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
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

import os.path

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.util
import libbe.storage

class Init (libbe.command.Command):
    """Create an on-disk bug repository

    >>> import os, sys
    >>> import libbe.storage.vcs
    >>> import libbe.storage.vcs.base
    >>> import libbe.util.utility
    >>> cmd = Init()
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> dir = libbe.util.utility.Dir()
    >>> vcs = libbe.storage.vcs.vcs_by_name('None')
    >>> vcs.repo = dir.path
    >>> try:
    ...     vcs.connect()
    ... except libbe.storage.ConnectionError:
    ...     True
    True
    >>> cmd.run(vcs)
    No revision control detected.
    BE repository initialized.
    >>> bd = libbe.bugdir.BugDir(vcs)
    >>> vcs.disconnect()
    >>> vcs.destroy()
    >>> dir.cleanup()

    >>> dir = libbe.util.utility.Dir()
    >>> vcs = libbe.storage.vcs.installed_vcs()
    >>> if vcs.name in libbe.storage.vcs.base.VCS_ORDER:
    ...     vcs.repo = dir.path
    ...     vcs._vcs_init(vcs.repo)
    ...     cmd.run(vcs) # doctest: +ELLIPSIS
    ... else:
    ...     print 'Using ... for revision control.\\nDirectory initialized.'
    Using ... for revision control.
    BE repository initialized.
    >>> vcs.disconnect()
    >>> vcs.destroy()
    >>> dir.cleanup()
    """
    
    name = 'init'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.requires_unconnected_storage = True

    def _run(self, storage, bugdir=None, **params):
        if not os.path.isdir(storage.repo):
            raise libbe.command.UserError(
                'No such directory: %s' % storage.repo)
        try:
            storage.connect()
            raise libbe.command.UserError(
                'Directory already initialized: %s' % storage.repo)
        except libbe.storage.ConnectionError:
            pass
        storage.init()
        storage.connect()
        bd = libbe.bugdir.BugDir(storage, from_storage=False)
        bd.save()
        if bd.storage.name is not 'None':
            print >> self.stdout, \
                'Using %s for revision control.' % storage.name
        else:
            print >> self.stdout, 'No revision control detected.'
        print >> self.stdout, 'BE repository initialized.'

    def _long_help(self):
        return """
This command initializes Bugs Everywhere support for the specified directory
and all its subdirectories.  It will auto-detect any supported revision control
system.  You can use "be set vcs_name" to change the vcs being used.

The directory defaults to your current working directory, but you can
change that by passing the --repo option to be
  $ be --repo path/to/new/bug/root init

When initialized in a version-controlled directory, BE sinks to the
version-control root.  In that case, the BE repository will be created
under that directory, rather than the current directory or the one
passed in --repo.  Consider the following tree, versioned in Git.
  ~
  `--projectX
     |-- .git
     `-- src
Calling
  ~$ be --repo ./projectX/src init
will create the BE repository rooted in projectX:
  ~
  `--projectX
     |-- .be
     |-- .git
     `-- src
"""
