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

class IllegalKey(Exception):
    def __init__(self, key):
        Exception.__init__(self, 'Illegal key "%s"' % key)
        self.key = key

class IllegalValue(Exception):
    def __init__(self, value):
        Exception.__init__(self, 'Illegal value "%s"' % value)
        self.value = value 

def generate(f, map, context=3):
    """Generate a format-2 mapfile.  This is a simpler format, but should merge
    better, because there's no chance of confusion for appends, and lines
    are unique for both key and value.

    >>> f = utility.FileString()
    >>> generate(f, {"q":"p"})
    >>> f.str
    '\\n\\n\\nq=p\\n\\n\\n\\n'
    >>> generate(f, {"q=":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q="
    >>> generate(f, {"q\\n":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q\\n"
    >>> generate(f, {"":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key ""
    >>> generate(f, {">q":"p"})
    Traceback (most recent call last):
    IllegalKey: Illegal key ">q"
    >>> generate(f, {"q":"p\\n"})
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

    for key in keys:
        for i in range(context):
            f.write("\n")
        f.write("%s=%s\n" % (key.encode("utf-8"), map[key].encode("utf-8")))
        for i in range(context):
            f.write("\n")

def parse(f):
    """
    Parse a format-2 mapfile.
    >>> parse('\\n\\n\\nq=p\\n\\n\\n\\n')['q']
    u'p'
    >>> parse('\\n\\nq=\\'p\\'\\n\\n\\n\\n')['q']
    u"\'p\'"
    >>> f = utility.FileString()
    >>> generate(f, {"a":"b", "c":"d", "e":"f"})
    >>> dict = parse(f)
    >>> dict["a"]
    u'b'
    >>> dict["c"]
    u'd'
    >>> dict["e"]
    u'f'
    """
    f = utility.get_file(f)
    result = {}
    for line in f:
        line = line.rstrip('\n')
        if len(line) == 0:
            continue
        name,value = [f.decode('utf-8') for f in line.split('=', 1)]
        assert not result.has_key('name')
        result[name] = value
    return result

def map_save(rcs, path, map):
    """Save the map as a mapfile to the specified path"""
    add = not os.path.exists(path)
    output = file(path, "wb")
    generate(output, map)
    if add:
        rcs.add_id(path)

class NoSuchFile(Exception):
    def __init__(self, pathname):
        Exception.__init__(self, "No such file: %s" % pathname)


def map_load(path):
    try:
        return parse(file(path, "rb"))
    except IOError, e:
        if e.errno != errno.ENOENT:
            raise e
        raise NoSuchFile(path)
