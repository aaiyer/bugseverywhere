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

import base

ConnectionError = base.ConnectionError
InvalidStorageVersion = base.InvalidStorageVersion
InvalidID = base.InvalidID
InvalidRevision = base.InvalidRevision
InvalidDirectory = base.InvalidDirectory
NotWriteable = base.NotWriteable
NotReadable = base.NotReadable
EmptyCommit = base.EmptyCommit

# a list of all past versions
STORAGE_VERSIONS = ['Bugs Everywhere Tree 1 0',
                    'Bugs Everywhere Directory v1.1',
                    'Bugs Everywhere Directory v1.2',
                    'Bugs Everywhere Directory v1.3',
                    'Bugs Everywhere Directory v1.4',
                    ]

# the current version
STORAGE_VERSION = STORAGE_VERSIONS[-1]

def get_storage(location):
    """
    Return a Storage instance from a repo location string.
    """
    import vcs
    s = vcs.detect_vcs(location)
    s.repo = location
    return s

__all__ = [ConnectionError, InvalidStorageVersion, InvalidID,
           InvalidRevision, InvalidDirectory, NotWriteable, NotReadable,
           EmptyCommit, STORAGE_VERSIONS, STORAGE_VERSION,
           get_storage]
