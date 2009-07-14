# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
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
import calendar
import codecs
import os
import shutil
import tempfile
import time
import types
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
    """Convert an RFC 2822-fomatted string into a time value.
    >>> str_to_time("Thu, 01 Jan 1970 00:00:00 +0000")
    0
    >>> q = time.time()
    >>> str_to_time(time_to_str(q)) == int(q)
    True
    >>> str_to_time("Thu, 01 Jan 1970 00:00:00 -1000")
    36000
    """
    timezone_str = str_time[-5:]
    if timezone_str != "+0000":
        str_time = str_time.replace(timezone_str, "+0000")
    time_val = calendar.timegm(time.strptime(str_time, RFC_2822_TIME_FMT))
    timesign = -int(timezone_str[0]+"1") # "+" -> time_val ahead of GMT
    timezone_tuple = time.strptime(timezone_str[1:], "%H%M")
    timezone = timezone_tuple.tm_hour*3600 + timezone_tuple.tm_min*60 
    return time_val + timesign*timezone

def handy_time(time_val):
    return time.strftime("%a, %d %b %Y %H:%M", time.localtime(time_val))

def time_to_gmtime(str_time):
    """Convert an RFC 2822-fomatted string to a GMT string.
    >>> time_to_gmtime("Thu, 01 Jan 1970 00:00:00 -1000")
    'Thu, 01 Jan 1970 10:00:00 +0000'
    """
    time_val = str_to_time(str_time)
    return time_to_str(time_val)


suite = doctest.DocTestSuite()
