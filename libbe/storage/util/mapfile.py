# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@tremily.us>
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


def generate(map, context=6):
    """Generate a JSON mapfile content string.

    Examples
    --------

    >>> import sys
    >>> sys.stdout.write(generate({}))
    {}
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

    The blank lines ensure that merging occurs independent of
    surrounding content.  Because the mapfile format is also used by
    the :py:mod:`~libbe.command.serve_commands` where merging is not
    important, the amount of context is controllable.

    >>> sys.stdout.write(generate({'q':u'Fran\u00e7ais'}, context=0))
    {
        "q": "Fran\\u00e7ais"
    }
    >>> sys.stdout.write(generate({'q':u'hello'}, context=0))
    {
        "q": "hello"
    }
    >>> sys.stdout.write(generate(
    ...         {'p':'really long line\\n'*10, 'q': 'the next entry'},
    ...         context=1))
    {
    <BLANKLINE>
        "p": "really long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\nreally long line\\n", 
    <BLANKLINE>
        "q": "the next entry"
    <BLANKLINE>
    }

    See Also
    --------
    parse : inverse
    """
    lines = json.dumps(map, sort_keys=True, indent=4).splitlines()
    sep = '\n' * (1 + context)
    return sep.join(lines) + '\n'

def parse(contents):
    """Parse a JSON mapfile string.

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
