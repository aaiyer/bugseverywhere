# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import calendar
import time
import os
import tempfile
import shutil
import doctest

class FileString(object):
    """Bare-bones pseudo-file class
    
    >>> f = FileString("me\\nyou")
    >>> len(list(f))
    2
    >>> len(list(f))
    0
    >>> f = FileString()
    >>> f.write("hello\\nthere")
    >>> "".join(list(f))
    'hello\\nthere'
    """
    def __init__(self, str=""):
        object.__init__(self)
        self.str = str
        self._iter = None

    def __iter__(self):
        if self._iter is None:
            self._iter = self._get_iter()
        return self._iter

    def _get_iter(self):
        for line in self.str.splitlines(True):
            yield line

    def write(self, line):
        self.str += line


def get_file(f):
    """
    Return a file-like object from input.  This is a helper for functions that
    can take either file or string parameters.

    :param f: file or string
    :return: a FileString if input is a string, otherwise return the imput 
    object.

    >>> isinstance(get_file(file("/dev/null")), file)
    True
    >>> isinstance(get_file("f"), FileString)
    True
    """
    if isinstance(f, basestring):
        return FileString(f)
    else:
        return f

def search_parent_directories(path, filename):
    """
    Find the file (or directory) named filename in path or in any
    of path's parents.
    
    e.g.
    search_parent_directories("/a/b/c", ".be")
    will return the path to the first existing file from
    /a/b/c/.be
    /a/b/.be
    /a/.be
    /.be
    or None if none of those files exist.
    """
    path = os.path.realpath(path)
    assert os.path.exists(path)
    old_path = None
    while True:
        check_path = os.path.join(path, filename)
        if os.path.exists(check_path):
            return check_path
        if path == old_path:
            return None
        old_path = path
        path = os.path.dirname(path)

class Dir (object):
    "A temporary directory for testing use"
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="BEtest")
        self.rmtree = shutil.rmtree # save local reference for __del__
        self.removed = False
    def __del__(self):
        self.cleanup()
    def cleanup(self):
        if self.removed == False:
            self.rmtree(self.path)
            self.removed = True
    def __call__(self):
        return self.path

RFC_2822_TIME_FMT = "%a, %d %b %Y %H:%M:%S +0000"


def time_to_str(time_val):
    """Convert a time value into an RFC 2822-formatted string.  This format
    lacks sub-second data.
    >>> time_to_str(0)
    'Thu, 01 Jan 1970 00:00:00 +0000'
    """
    return time.strftime(RFC_2822_TIME_FMT, time.gmtime(time_val))

def str_to_time(str_time):
    """Convert an RFC 2822-fomatted string into a time falue.
    >>> str_to_time("Thu, 01 Jan 1970 00:00:00 +0000")
    0
    >>> q = time.time()
    >>> str_to_time(time_to_str(q)) == int(q)
    True
    """
    return calendar.timegm(time.strptime(str_time, RFC_2822_TIME_FMT))

def handy_time(time_val):
    return time.strftime("%a, %d %b %Y %H:%M", time.localtime(time_val))

class CantFindEditor(Exception):
    def __init__(self):
        Exception.__init__(self, "Can't find editor to get string from")

def editor_string(comment=None):

    """Invokes the editor, and returns the user_produced text as a string

    >>> if "EDITOR" in os.environ:
    ...     del os.environ["EDITOR"]
    >>> if "VISUAL" in os.environ:
    ...     del os.environ["VISUAL"]
    >>> editor_string()
    Traceback (most recent call last):
    CantFindEditor: Can't find editor to get string from
    >>> os.environ["EDITOR"] = "echo bar > "
    >>> editor_string()
    'bar\\n'
    >>> os.environ["VISUAL"] = "echo baz > "
    >>> editor_string()
    'baz\\n'
    >>> del os.environ["EDITOR"]
    >>> del os.environ["VISUAL"]
    """
    for name in ('VISUAL', 'EDITOR'):
        try:
            editor = os.environ[name]
            break
        except KeyError:
            pass
    else:
        raise CantFindEditor()
    fhandle, fname = tempfile.mkstemp()
    try:
        if comment is not None:
            os.write(fhandle, '\n'+comment_string(comment))
        os.close(fhandle)
        oldmtime = os.path.getmtime(fname)
        os.system("%s %s" % (editor, fname))
        output = trimmed_string(file(fname, "rb").read())
        if output.rstrip('\n') == "":
            output = None
    finally:
        os.unlink(fname)
    return output


def comment_string(comment):
    """
    >>> comment_string('hello')
    '== Anything below this line will be ignored ==\\nhello'
    """
    return '== Anything below this line will be ignored ==\n' + comment


def trimmed_string(instring):
    """
    >>> trimmed_string("hello\\n== Anything below this line will be ignored")
    'hello\\n'
    >>> trimmed_string("hi!\\n" + comment_string('Booga'))
    'hi!\\n'
    """
    out = []
    for line in instring.splitlines(True):
        if line.startswith('== Anything below this line will be ignored'):
            break
        out.append(line)
    return ''.join(out)

suite = doctest.DocTestSuite()
