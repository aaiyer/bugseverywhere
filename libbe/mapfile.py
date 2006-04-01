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


def split_diff3(this, other, f):
    """Split a file or string with diff3 conflicts into two files.

    :param this: The THIS file to write.  May be a utility.FileString
    :param other: The OTHER file to write.  May be a utility.FileString
    :param f: The file or string to split.
    :return: True if there were conflicts

    >>> split_diff3(utility.FileString(), utility.FileString(), 
    ...             "a\\nb\\nc\\nd\\n")
    False
    >>> this = utility.FileString()
    >>> other = utility.FileString()
    >>> split_diff3(this, other, "<<<<<<< values1\\nstatus=closed\\n=======\\nstatus=closedd\\n>>>>>>> values2\\n")
    True
    >>> this.str
    'status=closed\\n'
    >>> other.str
    'status=closedd\\n'
    """
    f = utility.get_file(f)
    this_active = True
    other_active = True
    conflicts = False
    for line in f:
        if line.startswith("<<<<<<<"):
            conflicts = True
            this_active = True
            other_active = False
        elif line.startswith("======="):
            this_active = False
            other_active = True
        elif line.startswith(">>>>>>>"):
            this_active = True
            other_active = True
        else:
            if this_active:
                this.write(line)
            if other_active:
                other.write(line)
    return conflicts

def split_diff3_str(f):
    """Split a file/string with diff3 conflicts into two strings.  If there
    were no conflicts, one string is returned.

    >>> result = split_diff3_str("<<<<<<< values1\\nstatus=closed\\n=======\\nstatus=closedd\\n>>>>>>> values2\\n")
    >>> len(result)
    2
    >>> result[0] != result[1]
    True
    >>> result = split_diff3_str("<<<<<<< values1\\nstatus=closed\\n=======\\nstatus=closed\\n>>>>>>> values2\\n")
    >>> len(result)
    2
    >>> result[0] == result[1]
    True
    >>> result = split_diff3_str("a\\nb\\nc\\nd\\n")
    >>> len(result)
    1
    >>> result[0]
    'a\\nb\\nc\\nd\\n'
    """
    this = utility.FileString()
    other = utility.FileString()
    if split_diff3(this, other, f):
        return (this.str, other.str)
    else:
        return (this.str,)
