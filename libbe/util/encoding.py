# Copyright (C) 2008-2011 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@drexel.edu>
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

"""
Support input/output/filesystem encodings (e.g. UTF-8).
"""

import codecs
import locale
import sys
import types

import libbe
if libbe.TESTING == True:
    import doctest


ENCODING = None # override get_encoding() output by setting this

def get_encoding():
    """
    Guess a useful input/output/filesystem encoding...  Maybe we need
    seperate encodings for input/output and filesystem?  Hmm...
    """
    if ENCODING != None:
        return ENCODING
    encoding = locale.getpreferredencoding() or sys.getdefaultencoding()
    if sys.platform != 'win32' or sys.version_info[:2] > (2, 3):
        encoding = locale.getlocale(locale.LC_TIME)[1] or encoding
        # Python 2.3 on windows doesn't know about 'XYZ' alias for 'cpXYZ'
    return encoding

def get_input_encoding():
    return get_encoding()

def get_output_encoding():
    return get_encoding()

def get_filesystem_encoding():
    return get_encoding()

def known_encoding(encoding):
    """
    >>> known_encoding("highly-unlikely-encoding")
    False
    >>> known_encoding(get_encoding())
    True
    """
    try:
        codecs.lookup(encoding)
        return True
    except LookupError:
        return False

def get_file_contents(path, mode='r', encoding=None, decode=False):
    if decode == True:
        if encoding == None:
            encoding = get_filesystem_encoding()
        f = codecs.open(path, mode, encoding)
    else:
        f = open(path, mode)
    contents = f.read()
    f.close()
    return contents

def set_file_contents(path, contents, mode='w', encoding=None):
    if type(contents) == types.UnicodeType:
        if encoding == None:
            encoding = get_filesystem_encoding()
        f = codecs.open(path, mode, encoding)
    else:
        f = open(path, mode)
    f.write(contents)
    f.close()

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
