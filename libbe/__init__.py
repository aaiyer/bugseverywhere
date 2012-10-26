# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         W. Trevor King <wking@tremily.us>
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

* :py:mod:`libbe.bugdir`
* :py:mod:`libbe.bug`
* :py:mod:`libbe.comment`
* :py:mod:`libbe.command`
* :py:mod:`libbe.diff`
* :py:mod:`libbe.error`
* :py:mod:`libbe.storage`
* :py:mod:`libbe.ui`
* :py:mod:`libbe.util`
* :py:mod:`libbe.version`
* :py:mod:`libbe._version`
"""

TESTING = False
"""Flag controlling test-suite generation.

To reduce module load time, test suite generation is turned of by
default.  If you *do* want to generate the test suites, set
``TESTING=True`` before loading any :py:mod:`libbe` submodules.

Examples
--------

>>> import libbe
>>> libbe.TESTING = True
>>> import libbe.bugdir
>>> 'SimpleBugDir' in dir(libbe.bugdir)
True
"""
