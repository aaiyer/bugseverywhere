import os
import os.path
import sys
def my_import(mod_name):
    module = __import__(mod_name)
    components = mod_name.split('.')
    for comp in components[1:]:
        module = getattr(module, comp)
    return module

def iter_plugins(prefix):
    modfiles = os.listdir(os.path.join(sys.path[0], prefix))
    modfiles.sort()
    for modfile in modfiles:
        if modfile.endswith(".py") and modfile != "__init__.py":
            yield modfile[:-3], my_import(prefix+"."+modfile[:-3])


def get_plugin(prefix, name):
    dirprefix = '/'.join(prefix.split('.'))
    command_path = os.path.join(sys.path[0], dirprefix, name+".py")
    if os.path.isfile(command_path):
        return my_import(prefix + "." + name)
    return None
 
