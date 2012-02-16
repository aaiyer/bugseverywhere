# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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
Assorted utility functions that don't fit in anywhere else.
"""

import calendar
import codecs
import os
import shutil
import tempfile
import time
import types
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree

import libbe
if libbe.TESTING == True:
    import doctest

class InvalidXML(ValueError):
    """Invalid XML while parsing for a `*.from_xml()` method.

    Parameters
    ----------
    type : str
        String identifying `*`, e.g. "bug", "comment", ...
    element : :class:`ElementTree.Element`
        ElementTree.Element instance which caused the error.
    error : str
        Error description.
    """
    def __init__(self, type, element, error):
        msg = 'Invalid %s xml: %s\n  %s\n' \
            % (type, error, ElementTree.tostring(element))
        ValueError.__init__(self, msg)
        self.type = type
        self.element = element
        self.error = error

def search_parent_directories(path, filename):
    """
    Find the file (or directory) named filename in path or in any
    of path's parents.  For example::

         search_parent_directories("/a/b/c", ".be")

    will return the path to the first existing file from::

        /a/b/c/.be
        /a/b/.be
        /a/.be
        /.be

    or `None` if none of those files exist.
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
    """A temporary directory for testing use.

    Make sure you run :meth:`cleanup` after you're done using the
    directory.
    """
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="BEtest")
        self.removed = False
    def cleanup(self):
        if self.removed == False:
            shutil.rmtree(self.path)
            self.removed = True
    def __call__(self):
        return self.path

RFC_2822_TIME_FMT = "%a, %d %b %Y %H:%M:%S +0000"
"""RFC 2822 [#]_ format string for :func:`time.strftime` and
:func:`time.strptime`.

.. [#] See `RFC 2822`_, sections 3.3 and A.1.1.
.. _RFC 2822: http://www.faqs.org/rfcs/rfc2822.html
"""

def time_to_str(time_val):
    """Convert a time number into an RFC 2822-formatted string.

    Parameters
    ----------
    time_val : float
      Float seconds since the Epoc, see :func:`time.time`.
      Note that while `time_val` may contain sub-second data,
      the output string will not.

    Examples
    --------

    >>> time_to_str(0)
    'Thu, 01 Jan 1970 00:00:00 +0000'

    See Also
    --------
    str_to_time : inverse
    handy_time : localtime string
    """
    return time.strftime(RFC_2822_TIME_FMT, time.gmtime(time_val))

def str_to_time(str_time):
    """Convert an RFC 2822-fomatted string into a time value.

    Parameters
    ----------
    str_time : str
      An RFC 2822-formatted string.

    Examples
    --------

    >>> str_to_time("Thu, 01 Jan 1970 00:00:00 +0000")
    0
    >>> q = time.time()
    >>> str_to_time(time_to_str(q)) == int(q)
    True
    >>> str_to_time("Thu, 01 Jan 1970 00:00:00 -1000")
    36000

    See Also
    --------
    time_to_str : inverse
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
    """Convert a time number into a useful localtime.

    Where :func:`time_to_str` returns GMT +0000, `handy_time` returns
    a string in local time.  This may be more accessible for the user.

    Parameters
    ----------
    time_val : float
      Float seconds since the Epoc, see :func:`time.time`.
    """
    return time.strftime("%a, %d %b %Y %H:%M", time.localtime(time_val))

def time_to_gmtime(str_time):
    """Convert an RFC 2822-fomatted string to a GMT string.

    Parameters
    ----------
    str_time : str
      An RFC 2822-formatted string.

    Examples
    --------

    >>> time_to_gmtime("Thu, 01 Jan 1970 00:00:00 -1000")
    'Thu, 01 Jan 1970 10:00:00 +0000'
    """
    time_val = str_to_time(str_time)
    return time_to_str(time_val)

def iterable_full_of_strings(value, alternative=None):
    """Require an iterable full of strings.

    This is useful, for example, in validating `*.extra_strings`.
    See :attr:`libbe.bugdir.BugDir.extra_strings`

    Parameters
    ----------
    value : list or None
      The potential list of strings.
    alternative
      Allow a default (e.g. `None`), such that::

        iterable_full_of_strings(value=x, alternative=x) -> True

    Examples
    --------

    >>> iterable_full_of_strings([])
    True
    >>> iterable_full_of_strings(["abc", "def", u"hij"])
    True
    >>> iterable_full_of_strings(["abc", None, u"hij"])
    False
    >>> iterable_full_of_strings(None, alternative=None)
    True
    """
    if value == alternative:
        return True
    elif not hasattr(value, '__iter__'):
        return False
    for x in value:
        if type(x) not in types.StringTypes:
            return False
    return True

def underlined(string, char='='):
    """Produces a version of a string that is underlined.

    Parameters
    ----------
    string : str
      The string to underline
    char : str
      The character to use for the underlining.

    Examples
    --------

    >>> underlined("Underlined String")
    'Underlined String\\n================='
    """
    assert len(char) == 1, char
    return '%s\n%s' % (string, char*len(string))

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
