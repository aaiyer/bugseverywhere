# Copyright

"""Usage: python test.py [module(s) ...]

When called without optional module names, run the test suites for
*all* modules.  This may raise lots of errors if you haven't installed
one of the versioning control systems.

When called with module name arguments, only run the test suites from
those modules and their submodules.  For example:
  python test.py libbe.bugdir libbe.storage
"""

import doctest
import os
import os.path
import sys
import unittest

import libbe
libbe.TESTING = True
from libbe.util.tree import Tree
from libbe.util.plugin import import_by_name

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
    mod = import_by_name(modname)
    if hasattr(mod, 'suite'):
        s = mod.suite
    else:
        s = unittest.TestLoader().loadTestsFromModule(mod)
        sdoc = doctest.DocTestSuite(mod)
        suite.addTest(sdoc)
    suite.addTest(s)

suite = unittest.TestSuite()
tree = python_tree()
if len(sys.argv) <= 1:
    for node in tree.traverse():
        add_module_tests(suite, node.modname)
else:
    added = []
    for modname in sys.argv[1:]:
        for node in tree.traverse():
            if node.modname == modname:
                for n in node.traverse():
                    if n.modname not in added:
                        add_module_tests(suite, n.modname)
                        added.append(n.modname)
                break

result = unittest.TextTestRunner(verbosity=2).run(suite)

numErrors = len(result.errors)
numFailures = len(result.failures)
numBad = numErrors + numFailures
if numBad > 126:
    numBad = 1
sys.exit(numBad)
