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
    """
    >>> "list" in [n for n,m in iter_plugins("becommands")]
    True
    >>> "plugin" in [n for n,m in iter_plugins("libbe")]
    True
    """
    modfiles = os.listdir(os.path.join(plugin_path, prefix))
    modfiles.sort()
    for modfile in modfiles:
        if modfile.endswith(".py") and modfile != "__init__.py":
            yield modfile[:-3], my_import(prefix+"."+modfile[:-3])


def get_plugin(prefix, name):
    """
    >>> get_plugin("becommands", "asdf") is None
    True
    >>> get_plugin("becommands", "list")
    <module 'becommands.list' from '/home/abentley/be/becommands/list.pyc'>
    """
    dirprefix = '/'.join(prefix.split('.'))
    command_path = os.path.join(plugin_path, dirprefix, name+".py")
    if os.path.isfile(command_path):
        return my_import(prefix + "." + name)
    return None

plugin_path = sys.path[0]
while not os.path.isfile(os.path.join(plugin_path, "libbe/plugin.py")):
    plugin_path = os.path.realpath(os.path.dirname(plugin_path))
if plugin_path not in sys.path:
    sys.path.append(plugin_path)
def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()
