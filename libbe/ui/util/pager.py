# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
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

"""Automatic pager for terminal output (a la Git).
"""

import os as _os
import select as _select
import shlex as _shlex
import sys as _sys


# Inspired by Nathan Weizenbaum's
#   http://nex-3.com/posts/73-git-style-automatic-paging-in-ruby
def run_pager(paginate='auto'):
    """Use the environment variable PAGER page future stdout output

    paginate should be one of 'never', 'auto', or 'always'.

    usage: just call this function and continue using sys.stdout like
    you normally would.

    Notes
    -----

    This function creates forks a child, which continues executing the
    calling code.  The parent calls :py:func:`os.execvpe` to morph
    into `PAGER`.  The child keeps the original stdin, and the child's
    stdout becomes the parent's stdin.  The parent keeps the original
    stdout.
    """
    if (paginate == 'never' or
        _sys.platform == 'win32' or
        not hasattr(_sys.stdout, 'isatty') or
        not _sys.stdout.isatty()):
        return

    env = dict(_os.environ)
    if paginate == 'auto':
        if 'LESS' not in env:
            env['LESS'] = ''  # += doesn't work on undefined var
        else:
            env['LESS'] += ' '  # separate from existing variables
        # don't page if the input is short enough
        env['LESS'] += '-FRX'
    pager = _os.environ.get('PAGER', 'less')
    args = _shlex.split(pager)
    pager = args[0]
    if not pager:  # handle PAGER=''
        return

    read_fd, write_fd = _os.pipe()
    if _os.fork() == 0:
        # child process, keep executing Python program
        _os.close(read_fd)
        _os.dup2(write_fd, 1)
        _os.close(write_fd)
        if hasattr(_sys.stderr, 'isatty') and _sys.stderr.isatty():
            _os.dup2(1, 2)
        return

    # parent process, become pager
    _os.close(write_fd)
    _os.dup2(read_fd, 0)
    _os.close(read_fd)

    # Wait until we have input before we start the pager
    _select.select([0], [], [])
    _os.execvpe(pager, args, env)
