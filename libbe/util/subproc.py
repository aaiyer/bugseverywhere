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

"""
Functions for running external commands in subprocesses.
"""

from subprocess import Popen, PIPE
import sys
import types

import libbe
from encoding import get_encoding
if libbe.TESTING == True:
    import doctest

_MSWINDOWS = sys.platform == 'win32'
_POSIX = not _MSWINDOWS

if _POSIX == True:
    import os
    import select

class CommandError(Exception):
    def __init__(self, command, status, stdout=None, stderr=None):
        strerror = ['Command failed (%d):\n  %s\n' % (status, stderr),
                    'while executing\n  %s' % str(command)]
        Exception.__init__(self, '\n'.join(strerror))
        self.command = command
        self.status = status
        self.stdout = stdout
        self.stderr = stderr

def invoke(args, stdin=None, stdout=PIPE, stderr=PIPE, expect=(0,),
           cwd=None, shell=None, unicode_output=True, verbose=False,
           encoding=None, **kwargs):
    """
    expect should be a tuple of allowed exit codes.  cwd should be
    the directory from which the command will be executed.  When
    unicode_output == True, convert stdout and stdin strings to
    unicode before returing them.
    """
    if cwd == None:
        cwd = '.'
    if isinstance(shell, types.StringTypes):
        list_args = ' '.split(args)  # sloppy, but just for logging
        str_args = args
    else:
        list_args = args
        str_args = ' '.join(args)  # sloppy, but just for logging
    if verbose == True:
        print >> sys.stderr, '%s$ %s' % (cwd, str_args)
    try :
        if _POSIX:
            if shell is None:
                shell = False
            q = Popen(args, stdin=PIPE, stdout=stdout, stderr=stderr,
                      shell=shell, cwd=cwd, **kwargs)
        else:
            assert _MSWINDOWS==True, 'invalid platform'
            if shell is None:
                shell = True
            # win32 don't have os.execvp() so have to run command in a shell
            q = Popen(args, stdin=PIPE, stdout=stdout, stderr=stderr,
                      shell=shell, cwd=cwd, **kwargs)
    except OSError, e:
        raise CommandError(list_args, status=e.args[0], stderr=e)
    stdout,stderr = q.communicate(input=stdin)
    status = q.wait()
    if unicode_output == True:
        if encoding == None:
            encoding = get_encoding()
        if stdout != None:
            stdout = unicode(stdout, encoding)
        if stderr != None:
            stderr = unicode(stderr, encoding)
    if verbose == True:
        print >> sys.stderr, '%d\n%s%s' % (status, stdout, stderr)
    if status not in expect:
        raise CommandError(list_args, status, stdout, stderr)
    return status, stdout, stderr

class Pipe (object):
    """Simple interface for executing POSIX-style pipes.

    Based on the `subprocess` module.  The only complication is the
    adaptation of `subprocess.Popen._communicate` to listen to the
    stderrs of all processes involved in the pipe, as well as the
    terminal process' stdout.  There are two implementations of
    `Pipe._communicate`, one for MS Windows, and one for POSIX
    systems.  The MS Windows implementation is currently untested.

    >>> p = Pipe([['find', '/etc/'], ['grep', '^/etc/ssh$']])
    >>> p.stdout
    '/etc/ssh\\n'
    >>> p.status
    1
    >>> p.statuses
    [1, 0]
    >>> p.stderrs # doctest: +ELLIPSIS
    [...find: ...: Permission denied..., '']
    """
    def __init__(self, cmds, stdin=None):
        # spawn processes
        self._procs = []
        for cmd in cmds:
            if len(self._procs) != 0:
                stdin = self._procs[-1].stdout
            self._procs.append(Popen(cmd, stdin=stdin, stdout=PIPE, stderr=PIPE))

        self.stdout,self.stderrs = self._communicate(input=None)

        # collect process statuses
        self.statuses = []
        self.status = 0
        for proc in self._procs:
            self.statuses.append(proc.wait())
            if self.statuses[-1] != 0:
                self.status = self.statuses[-1]

    # Code excerpted from subprocess.Popen._communicate()
    if _MSWINDOWS == True:
        def _communicate(self, input=None):
            assert input == None, 'stdin != None not yet supported'
            # listen to each process' stderr
            threads = []
            std_X_arrays = []
            for proc in self._procs:
                stderr_array = []
                thread = Thread(target=proc._readerthread,
                                args=(proc.stderr, stderr_array))
                thread.setDaemon(True)
                thread.start()
                threads.append(thread)
                std_X_arrays.append(stderr_array)

            # also listen to the last processes stdout
            stdout_array = []
            thread = Thread(target=proc._readerthread,
                            args=(proc.stdout, stdout_array))
            thread.setDaemon(True)
            thread.start()
            threads.append(thread)
            std_X_arrays.append(stdout_array)

            # join threads as they die
            for thread in threads:
                thread.join()

            # read output from reader threads
            std_X_strings = []
            for std_X_array in std_X_arrays:
                std_X_strings.append(std_X_array[0])

            stdout = std_X_strings.pop(-1)
            stderrs = std_X_strings
            return (stdout, stderrs)
    else:
        assert _POSIX==True, 'invalid platform'
        def _communicate(self, input=None):
            read_set = []
            write_set = []
            read_arrays = []
            stdout = None # Return
            stderr = None # Return

            if self._procs[0].stdin:
                # Flush stdio buffer.  This might block, if the user has
                # been writing to .stdin in an uncontrolled fashion.
                self._procs[0].stdin.flush()
                if input:
                    write_set.append(self._procs[0].stdin)
                else:
                    self._procs[0].stdin.close()
            for proc in self._procs:
                read_set.append(proc.stderr)
                read_arrays.append([])
            read_set.append(self._procs[-1].stdout)
            read_arrays.append([])

            input_offset = 0
            while read_set or write_set:
                try:
                    rlist, wlist, xlist = select.select(read_set, write_set, [])
                except select.error, e:
                    if e.args[0] == errno.EINTR:
                        continue
                    raise
                if self._procs[0].stdin in wlist:
                    # When select has indicated that the file is writable,
                    # we can write up to PIPE_BUF bytes without risk
                    # blocking.  POSIX defines PIPE_BUF >= 512
                    chunk = input[input_offset : input_offset + 512]
                    bytes_written = os.write(self.stdin.fileno(), chunk)
                    input_offset += bytes_written
                    if input_offset >= len(input):
                        self._procs[0].stdin.close()
                        write_set.remove(self._procs[0].stdin)
                if self._procs[-1].stdout in rlist:
                    data = os.read(self._procs[-1].stdout.fileno(), 1024)
                    if data == '':
                        self._procs[-1].stdout.close()
                        read_set.remove(self._procs[-1].stdout)
                    read_arrays[-1].append(data)
                for i,proc in enumerate(self._procs):
                    if proc.stderr in rlist:
                        data = os.read(proc.stderr.fileno(), 1024)
                        if data == '':
                            proc.stderr.close()
                            read_set.remove(proc.stderr)
                        read_arrays[i].append(data)

            # All data exchanged.  Translate lists into strings.
            read_strings = []
            for read_array in read_arrays:
                read_strings.append(''.join(read_array))

            stdout = read_strings.pop(-1)
            stderrs = read_strings
            return (stdout, stderrs)

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
