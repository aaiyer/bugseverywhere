#!/usr/bin/python
#
# Copyright

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
            '   %s.txt' % c for c in children
            ] + ['', ''])

def make_module_txt(modname, children):
    filename = os.path.join('libbe', '%s.txt' % modname)
    if not os.path.exists('libbe'):
        os.mkdir('libbe')
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
