# Copyright (C) 2008-2009 Gianluca Montecchi <gian@grys.it>
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

"""
Support input/output/filesystem encodings (e.g. UTF-8).
"""

import codecs
import locale
import sys

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


    def _guess_encoding(self):
        return encoding.get_encoding()
    def _check_encoding(value):
        if value != None:
            return encoding.known_encoding(value)
    def _setup_encoding(self, new_encoding):
        # change hook called before generator.
        if new_encoding not in [None, settings_object.EMPTY]:
            if self._manipulate_encodings == True:
                encoding.set_IO_stream_encodings(new_encoding)
    def _set_encoding(self, old_encoding, new_encoding):
        self._setup_encoding(new_encoding)
        self._prop_save_settings(old_encoding, new_encoding)

    @_versioned_property(name="encoding",
                         doc="""The default input/output encoding to use (e.g. "utf-8").""",
                         change_hook=_set_encoding,
                         generator=_guess_encoding,
                         check_fn=_check_encoding)
    def encoding(): return {}

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
