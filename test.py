# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Marien Zwart <marien.zwart@gmail.com>
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

import doctest
import os
import os.path
import sys
import unittest

import libbe
libbe.TESTING = True
from libbe.util.tree import Tree
from libbe.util.plugin import import_by_name
from libbe.version import version

def python_tree(root_path='libbe', root_modname='libbe'):
    tree = Tree()
    tree.path = root_path
    tree.parent = None
    stack = [tree]
    while len(stack) > 0:
        f = stack.pop(0)
        if f.path.endswith('.py'):
            f.name = os.path.basename(f.path)[:-len('.py')]
        elif os.path.isdir(f.path) \
                and os.path.exists(os.path.join(f.path, '__init__.py')):
            f.name = os.path.basename(f.path)
            f.is_module = True
            for child in os.listdir(f.path):
                if child == '__init__.py':
                    continue
                c = Tree()
                c.path = os.path.join(f.path, child)
                c.parent = f
                stack.append(c)
        else:
            continue
        if f.parent == None:
            f.modname = root_modname
        else:
            f.modname = f.parent.modname + '.' + f.name
            f.parent.append(f)
    return tree

def add_module_tests(suite, modname):
    try:
        mod = import_by_name(modname)
    except ValueError, e:
        print >> sys.stderr, 'Failed to import "%s"' % (modname)
        raise e
    if hasattr(mod, 'suite'):
        s = mod.suite
    else:
        s = unittest.TestLoader().loadTestsFromModule(mod)
        try:
            sdoc = doctest.DocTestSuite(mod)
            suite.addTest(sdoc)
        except ValueError:
            pass
    suite.addTest(s)

if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser(usage='%prog [options] [modules ...]',
                                   description=
"""When called without optional module names, run the test suites for
*all* modules.  This may raise lots of errors if you haven't installed
one of the versioning control systems.

When called with module name arguments, only run the test suites from
those modules and their submodules.  For example::

    $ python test.py libbe.bugdir libbe.storage
""")
    parser.add_option('-q', '--quiet', action='store_true', default=False,
                      help='Run unittests in quiet mode (verbosity 1).')
    options,args = parser.parse_args()
    print >> sys.stderr, 'Testing BE\n%s' % version(verbose=True)

    verbosity = 2
    if options.quiet == True:
        verbosity = 1

    suite = unittest.TestSuite()
    tree = python_tree()
    if len(args) == 0:
        for node in tree.traverse():
            add_module_tests(suite, node.modname)
    else:
        added = []
        for modname in args:
            for node in tree.traverse():
                if node.modname == modname:
                    for n in node.traverse():
                        if n.modname not in added:
                            add_module_tests(suite, n.modname)
                            added.append(n.modname)
                    break
    
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    
    numErrors = len(result.errors)
    numFailures = len(result.failures)
    numBad = numErrors + numFailures
    if numBad > 126:
        numBad = 1
    sys.exit(numBad)
