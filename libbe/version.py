#!/usr/bin/env python
# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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
Store version info for this BE installation.  By default, use the
bzr-generated information in _version.py, but allow manual overriding
by setting _VERSION.  This allows support of both the "I don't want to
be bothered setting version strings" and the "I want complete control
over the version strings" workflows.
"""

import copy

import libbe.storage
try:
    from ._version import version_info    
except ImportError, e:
    import logging
    logging.warn('unable to import libbe._version: %s' % e)
    version_info = {
        'revision': 'unknown',
        'date': 'unknown',
        'committer': 'unknown',
        }

# Manually set a version string (optional, defaults to bzr revision id)
_VERSION = '1.0.0'

def version(verbose=False):
    """
    Returns the version string for this BE installation.  If
    verbose==True, the string will include extra lines with more
    detail (e.g. last committer's name, etc.).
    """
    if "_VERSION" in globals():
        string = _VERSION
    else:
        string = version_info['revision']
    if verbose == True:
        info = copy.copy(version_info)
        info['storage'] = libbe.storage.STORAGE_VERSION
        string += ("\n"
                   "revision: %(revision)s\n"
                   "date: %(date)s\n"
                   "committer: %(committer)s\n"
                   "storage version: %(storage)s"
                   % info)
    return string

if __name__ == "__main__":
    print version(verbose=True)
