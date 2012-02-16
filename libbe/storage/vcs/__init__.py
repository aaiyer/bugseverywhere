# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
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

"""Define the Version Controlled System (VCS)-based
:class:`~libbe.storage.base.Storage` and
:class:`~libbe.storage.base.VersionedStorage` implementations.

There is a base class (:class:`~libbe.storage.vcs.VCS`) translating 
Storage language to VCS language, and a number of `VCS` implementations:

* :class:`~libbe.storage.vcs.arch.Arch`
* :class:`~libbe.storage.vcs.bzr.Bzr`
* :class:`~libbe.storage.vcs.darcs.Darcs`
* :class:`~libbe.storage.vcs.git.Git`
* :class:`~libbe.storage.vcs.hg.Hg`

The base `VCS` class also serves as a filesystem Storage backend (not
versioning) in the event that a user has no VCS installed.
"""

import base

set_preferred_vcs = base.set_preferred_vcs
vcs_by_name = base.vcs_by_name
detect_vcs = base.detect_vcs
installed_vcs = base.installed_vcs

__all__ = [set_preferred_vcs, vcs_by_name, detect_vcs, installed_vcs]
