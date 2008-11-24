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
import os.path
import errno
import utility
import doctest

class IllegalKey(Exception):
    def __init__(self, key):
        Exception.__init__(self, 'Illegal key "%s"' % key)
        self.key = key

class IllegalValue(Exception):
    def __init__(self, value):
        Exception.__init__(self, 'Illegal value "%s"' % value)
        self.value = value 

def generate(map, context=3):
    """Generate a format-2 mapfile content string.  This is a simpler
    format, but should merge better, because there's no chance of
    confusion for appends, and lines are unique for both key and
    value.

    >>> generate({"q":"p"})
    '\\n\\n\\nq=p\\n\\n\\n\\n'
    >>> generate({"q=":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q="
    >>> generate({"q\\n":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q\\n"
    >>> generate({"":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key ""
    >>> generate({">q":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key ">q"
    >>> generate({"q":"p\\n"})
    Traceback (most recent call last):
    IllegalValue: Illegal value "p\\n"
    """
    assert(context > 0)
    keys = map.keys()
    keys.sort()
    for key in keys:
        try:
            assert not key.startswith('>')
            assert('\n' not in key)
            assert('=' not in key)
            assert(len(key) > 0)
        except AssertionError:
            raise IllegalKey(key.encode('string_escape'))
        if "\n" in map[key]:
            raise IllegalValue(map[key].encode('string_escape'))

    lines = []
    for key in keys:
        for i in range(context):
            lines.append("")
        lines.append("%s=%s" % (key, map[key]))
        for i in range(context):
            lines.append("")
    return '\n'.join(lines) + '\n'

def parse(contents):
    """
    Parse a format-2 mapfile string.
    >>> parse('\\n\\n\\nq=p\\n\\n\\n\\n')['q']
    'p'
    >>> parse('\\n\\nq=\\'p\\'\\n\\n\\n\\n')['q']
    "\'p\'"
    >>> contents = generate({"a":"b", "c":"d", "e":"f"})
    >>> dict = parse(contents)
    >>> dict["a"]
    'b'
    >>> dict["c"]
    'd'
    >>> dict["e"]
    'f'
    """
    result = {}
    for line in contents.splitlines():
        line = line.rstrip('\n')
        if len(line) == 0:
            continue
        name,value = [field for field in line.split('=', 1)]
        assert not result.has_key(name)
        result[name] = value
    return result

def map_save(rcs, path, map, allow_no_rcs=False):
    """Save the map as a mapfile to the specified path"""
    contents = generate(map)
    rcs.set_file_contents(path, contents, allow_no_rcs)

def map_load(rcs, path, allow_no_rcs=False):
    contents = rcs.get_file_contents(path, allow_no_rcs=allow_no_rcs)
    return parse(contents)

suite = doctest.DocTestSuite()
