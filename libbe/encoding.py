# Bugs Everywhere, a distributed bugtracker
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
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#    MA 02110-1301, USA
import codecs
import locale
import sys
import doctest

def get_encoding():
    """
    Guess a useful input/output/filesystem encoding...  Maybe we need
    seperate encodings for input/output and filesystem?  Hmm...
    """
    encoding = locale.getpreferredencoding() or sys.getdefaultencoding()
    if sys.platform != 'win32' or sys.version_info[:2] > (2, 3):
        encoding = locale.getlocale(locale.LC_TIME)[1] or encoding
        # Python 2.3 on windows doesn't know about 'XYZ' alias for 'cpXYZ'
    return encoding

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

def set_IO_stream_encodings(encoding):
    sys.stdin = codecs.getreader(encoding)(sys.__stdin__)
    sys.stdout = codecs.getwriter(encoding)(sys.__stdout__)
    sys.stderr = codecs.getwriter(encoding)(sys.__stderr__)

suite = doctest.DocTestSuite()
