# Bugs Everywhere, a distributed bugtracker
# Copyright (C) 2008-2012 Chris Ball <cjb@laptop.org>
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

"""
Define editor_string(), a function that invokes an editor to accept
user-produced text as a string.
"""

import codecs
import locale
import os
import sys
import tempfile

import libbe
import libbe.util.encoding

if libbe.TESTING == True:
    import doctest


comment_marker = u"== Anything below this line will be ignored\n"

class CantFindEditor(Exception):
    def __init__(self):
        Exception.__init__(self, "Can't find editor to get string from")

def editor_string(comment=None, encoding=None):
    """Invokes the editor, and returns the user-produced text as a string

    >>> if "EDITOR" in os.environ:
    ...     del os.environ["EDITOR"]
    >>> if "VISUAL" in os.environ:
    ...     del os.environ["VISUAL"]
    >>> editor_string()
    Traceback (most recent call last):
    CantFindEditor: Can't find editor to get string from
    >>> os.environ["EDITOR"] = "echo bar > "
    >>> editor_string()
    u'bar\\n'
    >>> os.environ["VISUAL"] = "echo baz > "
    >>> editor_string()
    u'baz\\n'
    >>> os.environ["VISUAL"] = "echo 'baz\\n== Anything below this line will be ignored\\nHi' > "
    >>> editor_string()
    u'baz\\n'
    >>> del os.environ["EDITOR"]
    >>> del os.environ["VISUAL"]
    """
    if encoding == None:
        encoding = libbe.util.encoding.get_text_file_encoding()
    editor = None
    for name in ('VISUAL', 'EDITOR'):
        if name in os.environ and os.environ[name] != '':
            editor = os.environ[name]
            break
    if editor == None:
        raise CantFindEditor()
    fhandle, fname = tempfile.mkstemp()
    try:
        if comment is not None:
            cstring = u'\n'+comment_string(comment)
            os.write(fhandle, cstring.encode(encoding))
        os.close(fhandle)
        oldmtime = os.path.getmtime(fname)
        os.system("%s %s" % (editor, fname))
        output = libbe.util.encoding.get_file_contents(
            fname, encoding=encoding, decode=True)
        output = trimmed_string(output)
        if output.rstrip('\n') == "":
            output = None
    finally:
        os.unlink(fname)
    return output


def comment_string(comment):
    """
    >>> comment_string('hello') == comment_marker+"hello"
    True
    """
    return comment_marker + comment


def trimmed_string(instring):
    """
    >>> trimmed_string("hello\\n"+comment_marker)
    u'hello\\n'
    >>> trimmed_string("hi!\\n" + comment_string('Booga'))
    u'hi!\\n'
    """
    out = []
    for line in instring.splitlines(True):
        if line.startswith(comment_marker):
            break
        out.append(line)
    return ''.join(out)

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
