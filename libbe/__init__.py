# Copyright (C) 2005-2010 Aaron Bentley and Panometrics, Inc.
#                         W. Trevor King <wking@drexel.edu>
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

"""The libbe module does all the legwork for bugs-everywhere_ (BE).

.. _bugs-everywhere: http://bugseverywhere.org

To facilitate faster loading, submodules are not imported by default.
The available submodules are:

* :mod:`libbe.bugdir`
* :mod:`libbe.bug`
* :mod:`libbe.comment`
* :mod:`libbe.command`
* :mod:`libbe.diff`
* :mod:`libbe.error`
* :mod:`libbe.storage`
* :mod:`libbe.ui`
* :mod:`libbe.util`
* :mod:`libbe.version`
* :mod:`libbe._version`
"""

TESTING = False
"""Flag controlling test-suite generation.

To reduce module load time, test suite generation is turned of by
default.  If you *do* want to generate the test suites, set
``TESTING=True`` before loading any :mod:`libbe` submodules.

Examples
--------

>>> import libbe
>>> libbe.TESTING = True
>>> import libbe.bugdir
>>> 'SimpleBugDir' in dir(libbe.bugdir)
True
"""
