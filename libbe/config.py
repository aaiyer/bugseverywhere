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
import ConfigParser
import codecs
import locale
import os.path
import sys
import doctest

default_encoding = sys.getfilesystemencoding() or locale.getpreferredencoding()

def path():
    """Return the path to the per-user config file"""
    return os.path.expanduser("~/.bugs_everywhere")

def set_val(name, value, section="DEFAULT", encoding=None):
    """Set a value in the per-user config file

    :param name: The name of the value to set
    :param value: The new value to set (or None to delete the value)
    :param section: The section to store the name/value in
    """
    if encoding == None:
        encoding = default_encoding
    config = ConfigParser.ConfigParser()
    f = codecs.open(path(), "r", encoding)
    config.readfp(f, path())
    f.close()
    if value is not None:
        config.set(section, name, value)
    else:
        config.remove_option(section, name)
    f = codecs.open(path(), "w", encoding)
    config.write(f)
    f.close()

def get_val(name, section="DEFAULT", encoding=None):
    """
    Get a value from the per-user config file

    :param name: The name of the value to get
    :section: The section that the name is in
    :return: The value, or None
    >>> get_val("junk") is None
    True
    >>> set_val("junk", "random")
    >>> get_val("junk")
    u'random'
    >>> set_val("junk", None)
    >>> get_val("junk") is None
    True
    """
    if encoding == None:
        encoding = default_encoding
    config = ConfigParser.ConfigParser()
    f = codecs.open(path(), "r", encoding)
    config.readfp(f, path())
    f.close()
    try:
        return config.get(section, name)
    except ConfigParser.NoOptionError:
        return None

suite = doctest.DocTestSuite()
