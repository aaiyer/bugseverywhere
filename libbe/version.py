#!/usr/bin/env python
# Copyright (C) 2009-2010 W. Trevor King <wking@drexel.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Store version info for this BE installation.  By default, use the
bzr-generated information in _version.py, but allow manual overriding
by setting _VERSION.  This allows support of both the "I don't want to
be bothered setting version strings" and the "I want complete control
over the version strings" workflows.
"""

import copy

import libbe._version as _version
import libbe.storage

# Manually set a version string (optional, defaults to bzr revision id)
#_VERSION = "1.2.3"

def version(verbose=False):
    """
    Returns the version string for this BE installation.  If
    verbose==True, the string will include extra lines with more
    detail (e.g. bzr branch nickname, etc.).
    """
    if "_VERSION" in globals():
        string = _VERSION
    else:
        string = _version.version_info["revision_id"]
    if verbose == True:
        info = copy.copy(_version.version_info)
        info['storage'] = libbe.storage.STORAGE_VERSION
        string += ("\n"
                   "revision: %(revno)d\n"
                   "nick: %(branch_nick)s\n"
                   "revision id: %(revision_id)s\n"
                   "storage version: %(storage)s"
                   % info)
    return string

if __name__ == "__main__":
    print version(verbose=True)