"""Usage: python test.py [module]

When called without an optional module name, run the doctests from
*all* modules.  This may raise lots of errors if you haven't installed
one of the versioning control systems.

When called with an optional module name, only run the doctests from
that module.
"""

from libbe import plugin
import unittest
import doctest
import sys

suite = unittest.TestSuite()

if len(sys.argv) > 1:
    submodname = sys.argv[1]
    match = False
    mod = plugin.get_plugin("libbe", submodname)
    if mod is not None and hasattr(mod, "suite"):
        suite.addTest(mod.suite)
        match = True
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
