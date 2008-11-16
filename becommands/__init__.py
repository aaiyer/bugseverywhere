"Command plugins for the BugsEverywhere be script."

__all__ = ["set_root", "set", "new", "remove", "list", "show", "close", "open",
           "assign", "severity", "status", "target", "comment", "diff",
           "upgrade", "help"]

def import_all():
    for i in __all__:
        name = __name__ + "." + i
        try:
            __import__(name, globals(), locals(), [])
        except ImportError:
            print "Import of %s failed!" % (name,)

import_all()
