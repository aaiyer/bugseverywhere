# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
import os
import os.path
import sys
import doctest

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
        if modfile.startswith('.'):
            continue # the occasional emacs temporary file
        if modfile.endswith(".py") and modfile != "__init__.py":
            yield modfile[:-3], my_import(prefix+"."+modfile[:-3])


def get_plugin(prefix, name):
    """
    >>> get_plugin("becommands", "asdf") is None
    True
    >>> q = repr(get_plugin("becommands", "list"))
    >>> q.startswith("<module 'becommands.list' from ")
    True
    """
    dirprefix = os.path.join(*prefix.split('.'))
    command_path = os.path.join(plugin_path, dirprefix, name+".py")
    if os.path.isfile(command_path):
        return my_import(prefix + "." + name)
    return None

plugin_path = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
if plugin_path not in sys.path:
    sys.path.append(plugin_path)

suite = doctest.DocTestSuite()

def _test():
    import doctest
    doctest.testmod()

if __name__ == "__main__":
    _test()
