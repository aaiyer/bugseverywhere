# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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

"""
Allow simple listing and loading of the various becommands and libbe
submodules (i.e. "plugins").
"""

import os
import os.path
import sys


_PLUGIN_PATH = os.path.realpath(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(__file__))))
if _PLUGIN_PATH not in sys.path:
    sys.path.append(_PLUGIN_PATH)

def import_by_name(modname):
    """
    >>> mod = import_by_name('libbe.bugdir')
    >>> 'BugDir' in dir(mod)
    True
    >>> import_by_name('libbe.highly_unlikely')
    Traceback (most recent call last):
      ...
    ImportError: No module named highly_unlikely
    """
    module = __import__(modname)
    components = modname.split('.')
    for comp in components[1:]:
        module = getattr(module, comp)
    return module

def modnames(prefix):
    """
    >>> 'list' in [n for n in modnames('libbe.command')]
    True
    >>> 'plugin' in [n for n in modnames('libbe.util')]
    True
    """
    components = prefix.split('.')
    modfiles = os.listdir(os.path.join(_PLUGIN_PATH, *components))
    modfiles.sort()
    for modfile in modfiles:
        if modfile.startswith('.'):
            continue # the occasional emacs temporary file
        if modfile.endswith('.py') and modfile != '__init__.py':
            yield modfile[:-3]
