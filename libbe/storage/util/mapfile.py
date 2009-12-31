# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
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
Provide a means of saving and loading dictionaries of parameters.  The
saved "mapfiles" should be clear, flat-text files, and allow easy merging of
independent/conflicting changes.
"""

import errno
import os.path
import types
import yaml

import libbe
if libbe.TESTING == True:
    import doctest


class IllegalKey(Exception):
    def __init__(self, key):
        Exception.__init__(self, 'Illegal key "%s"' % key)
        self.key = key

class IllegalValue(Exception):
    def __init__(self, value):
        Exception.__init__(self, 'Illegal value "%s"' % value)
        self.value = value

class InvalidMapfileContents(Exception):
    def __init__(self, contents):
        Exception.__init__(self, 'Invalid YAML contents')
        self.contents = contents

def generate(map):
    """Generate a YAML mapfile content string.
    >>> generate({'q':'p'})
    'q: p\\n\\n'
    >>> generate({'q':u'Fran\u00e7ais'})
    'q: Fran\\xc3\\xa7ais\\n\\n'
    >>> generate({'q':u'hello'})
    'q: hello\\n\\n'
    >>> generate({'q=':'p'})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q="
    >>> generate({'q:':'p'})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q:"
    >>> generate({'q\\n':'p'})
    Traceback (most recent call last):
    IllegalKey: Illegal key "q\\n"
    >>> generate({'':'p'})
    Traceback (most recent call last):
    IllegalKey: Illegal key ""
    >>> generate({'>q':'p'})
    Traceback (most recent call last):
    IllegalKey: Illegal key ">q"
    >>> generate({'q':'p\\n'})
    Traceback (most recent call last):
    IllegalValue: Illegal value "p\\n"
    """
    keys = map.keys()
    keys.sort()
    for key in keys:
        try:
            assert not key.startswith('>')
            assert('\n' not in key)
            assert('=' not in key)
            assert(':' not in key)
            assert(len(key) > 0)
        except AssertionError:
            raise IllegalKey(unicode(key).encode('unicode_escape'))
        if '\n' in map[key]:
            raise IllegalValue(unicode(map[key]).encode('unicode_escape'))

    lines = []
    for key in keys:
        lines.append(yaml.safe_dump({key: map[key]},
                                    default_flow_style=False,
                                    allow_unicode=True))
        lines.append('')
    return '\n'.join(lines)

def parse(contents):
    """
    Parse a YAML mapfile string.
    >>> parse('q: p\\n\\n')['q']
    'p'
    >>> parse('q: \\'p\\'\\n\\n')['q']
    'p'
    >>> contents = generate({'a':'b', 'c':'d', 'e':'f'})
    >>> dict = parse(contents)
    >>> dict['a']
    'b'
    >>> dict['c']
    'd'
    >>> dict['e']
    'f'
    >>> contents = generate({'q':u'Fran\u00e7ais'})
    >>> dict = parse(contents)
    >>> dict['q']
    u'Fran\\xe7ais'
    >>> dict = parse('a!')
    Traceback (most recent call last):
      ...
    InvalidMapfileContents: Invalid YAML contents
    """
    c = yaml.load(contents)
    if type(c) == types.StringType:
        raise InvalidMapfileContents(
            'Unable to parse YAML (BE format missmatch?):\n\n%s' % contents)
    return c or {}

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
