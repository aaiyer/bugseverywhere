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

"""Serializing and deserializing dictionaries of parameters.

The serialized "mapfiles" should be clear, flat-text strings, and allow
easy merging of independent/conflicting changes.
"""

import errno
import json
import os.path

import libbe
if libbe.TESTING == True:
    import doctest


class InvalidMapfileContents (Exception):
    def __init__(self, contents):
        super(InvalidMapfileContents, self).__init__('Invalid JSON contents')
        self.contents = contents


def generate(map):
    """Generate a YAML mapfile content string.

    Examples
    --------

    >>> import sys
    >>> sys.stdout.write(generate({'q':'p'}))
    {
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
        "q": "p"
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    }
    >>> generate({'q':u'Fran\u00e7ais'})
    '{\\n\\n\\n\\n\\n\\n\\n    "q": "Fran\\\\u00e7ais"\\n\\n\\n\\n\\n\\n\\n}\\n'
    >>> generate({'q':u'hello'})
    '{\\n\\n\\n\\n\\n\\n\\n    "q": "hello"\\n\\n\\n\\n\\n\\n\\n}\\n'
    >>> sys.stdout.write(generate(
    ...         {'p':'really long line\\n'*10, 'q': 'the next entry'}))
    {
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
        "p": "really long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\n", 
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
        "q": "the next entry"
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    <BLANKLINE>
    }

    See Also
    --------
    parse : inverse
    """
    lines = json.dumps(map, sort_keys=True, indent=4).splitlines()
    # add blank lines for context-less merging
    return '\n\n\n\n\n\n\n'.join(lines) + '\n'

def parse(contents):
    """Parse a YAML mapfile string.

    Examples
    --------

    >>> parse('{"q": "p"}')['q']
    u'p'
    >>> contents = generate({'a':'b', 'c':'d', 'e':'f'})
    >>> dict = parse(contents)
    >>> dict['a']
    u'b'
    >>> dict['c']
    u'd'
    >>> dict['e']
    u'f'
    >>> contents = generate({'q':u'Fran\u00e7ais'})
    >>> dict = parse(contents)
    >>> dict['q']
    u'Fran\\xe7ais'
    >>> dict = parse('a!')
    Traceback (most recent call last):
      ...
    InvalidMapfileContents: Invalid JSON contents

    See Also
    --------
    generate : inverse

    """
    try:
        return json.loads(contents)
    except ValueError:
        raise InvalidMapfileContents(contents)

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
