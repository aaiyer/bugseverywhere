from libbe import plugin
import doctest
import sys
if len(sys.argv) > 1:
    match = False
    mod = plugin.get_plugin("libbe", sys.argv[1])
    if mod is not None:
        doctest.testmod(mod)
        match = True
    mod = plugin.get_plugin("becommands", sys.argv[1])
    if mod is not None:
        doctest.testmod(mod)
        match = True
    if not match:
        print "No modules match \"%s\"" % sys.argv[1]
else:    
    for module in plugin.iter_plugins("libbe"):
        doctest.testmod(module[1])
    for module in plugin.iter_plugins("becommands"):
        doctest.testmod(module[1])
