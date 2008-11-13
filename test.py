"""Usage: python test.py [module]

When called without an optional module name, run the doctests from
*all* modules.  This may raise lots of errors if you haven't installed
one of the versioning control systems.

When called with an optional module name, only run the doctests from
that module.
"""

from libbe import plugin
import doctest
import sys
if len(sys.argv) > 1:
    match = False
    libbe_failures = libbe_tries = becommands_failures = becommands_tries = 0
    mod = plugin.get_plugin("libbe", sys.argv[1])
    if mod is not None:
        libbe_failures, libbe_tries = doctest.testmod(mod)
        match = True
    mod = plugin.get_plugin("becommands", sys.argv[1])
    if mod is not None:
        becommands_failures, becommands_tries = doctest.testmod(mod)
        match = True
    if not match:
        print "No modules match \"%s\"" % sys.argv[1]
        sys.exit(1)
    else:
        sys.exit(libbe_failures or becommands_failures)
else:
    failed = False
    for module in plugin.iter_plugins("libbe"):
        failures, tries = doctest.testmod(module[1])
        if failures:
            failed = True
    for module in plugin.iter_plugins("becommands"):
        failures, tries = doctest.testmod(module[1])
        if failures:
            failed = True
    sys.exit(failed)
