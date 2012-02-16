#!/usr/bin/python
#
# Copyright (C) 2010-2012 Chris Ball <cjb@laptop.org>
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

"""Auto-generate reStructuredText of the libbe module tree for Sphinx.
"""

import sys
import os, os.path

sys.path.insert(0, os.path.abspath('..'))
from test import python_tree

def title(modname):
    t = ':mod:`%s`' % modname
    delim = '*'*len(t)
    return '\n'.join([delim, t, delim, '', ''])

def automodule(modname):
    return '\n'.join([
            '.. automodule:: %s' % modname,
            '   :members:',
            '   :undoc-members:',
            '', ''])

def toctree(children):
    if len(children) == 0:
        return ''
    return '\n'.join([
            '.. toctree::',
            '   :maxdepth: 2',
            '',
            ] + [
            '   %s.txt' % c for c in sorted(children)
            ] + ['', ''])

def make_module_txt(modname, children, subdir='libbe'):
    filename = os.path.join(subdir, '%s.txt' % modname)
    if not os.path.exists(subdir):
        os.mkdir(subdir)
    if os.path.exists(filename):
        return None # don't overwrite potentially hand-written files.
    f = file(filename, 'w')
    f.write(title(modname))
    f.write(automodule(modname))
    f.write(toctree(children))
    f.close()

if __name__ == '__main__':
    pt = python_tree(root_path='../libbe', root_modname='libbe')
    for node in pt.traverse():
        make_module_txt(node.modname, [c.modname for c in node])
