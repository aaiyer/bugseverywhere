"""Usage: python test.py [module(s) ...]

When called without optional module names, run the doctests from *all*
modules.  This may raise lots of errors if you haven't installed one
of the versioning control systems.

When called with module name arguments, only run the doctests from
those modules.
"""

from libbe import plugin
import unittest
import doctest
import sys

suite = unittest.TestSuite()

if len(sys.argv) > 1:
    for submodname in sys.argv[1:]:
        match = False
        mod = plugin.get_plugin("libbe", submodname)
        if mod is not None and hasattr(mod, "suite"):
            suite.addTest(mod.suite)
            match = True
        else:
            print "Module \"%s\" has no test suite" % submodname
        mod = plugin.get_plugin("becommands", submodname)
        if mod is not None:
            suite.addTest(doctest.DocTestSuite(mod))
            match = True
        if not match:
            print "No modules match \"%s\"" % submodname
            sys.exit(1)
else:
    failed = False
    for modname,module in plugin.iter_plugins("libbe"):
        if not hasattr(module, "suite"):
            continue
        suite.addTest(module.suite)
    for modname,module in plugin.iter_plugins("becommands"):
        suite.addTest(doctest.DocTestSuite(module))

#for s in suite._tests:
#    print s
#exit(0)
result = unittest.TextTestRunner(verbosity=2).run(suite)

numErrors = len(result.errors)
numFailures = len(result.failures)
numBad = numErrors + numFailures
if numBad > 126:
    numBad = 1
sys.exit(numBad)
