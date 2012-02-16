# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
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
