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
import zipfile


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

def ziplistdir(path):
    """Lists items in a directory contained in a zip file"""
    zipidx=path.find('.zip')
    zippath=path[:4+zipidx]
    path=path[5+zipidx:].replace(os.sep, '/')
    with zipfile.ZipFile(zippath, 'r') as zf:
        files=[f[len(path)+1:] for f in zf.namelist() if f[:len(path)]==path and '/' not in f[len(path)+1:]]
        return files

def modnames(prefix):
    """
    >>> 'list' in [n for n in modnames('libbe.command')]
    True
    >>> 'plugin' in [n for n in modnames('libbe.util')]
    True
    """
    components = prefix.split('.')
    modfilespath=os.path.join(_PLUGIN_PATH, *components)
    # Cope if we are executing from inside a zip archive full of precompiled .pyc's
    inside_zip='.zip' in modfilespath
    modfiles=ziplistdir(modfilespath) if inside_zip else os.listdir(modfilespath)
    modfiles.sort()
    # Eliminate .py/.pyc duplicates, preferring .pyc if we're in a zip archive
    if inside_zip:
        x=1
        while x<len(modfiles):
            if modfiles[x].endswith('.pyc') and modfiles[x-1]==modfiles[x][:len(modfiles[x-1])]:
                del modfiles[x-1]
            else:
                x+=1
    else:
        x=0
        while x<len(modfiles)-1:
            if modfiles[x].endswith('.py') and modfiles[x]==modfiles[x+1][:len(modfiles[x])]:
                del modfiles[x+1]
            x+=1
    for modfile in modfiles:
        if modfile.startswith('.'):
            continue # the occasional emacs temporary file
        if modfile == '__init__.py' or modfile == '__init__.pyc':
            continue
        if modfile.endswith('.py'):
            yield modfile[:-3]
        elif modfile.endswith('.pyc'):
            yield modfile[:-4]
