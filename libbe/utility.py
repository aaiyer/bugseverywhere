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
import codecs
import os
import shutil
import tempfile
import time
import doctest


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


suite = doctest.DocTestSuite()
