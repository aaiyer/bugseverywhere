# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Andrew Cooper <andrew.cooper@hkcreations.org>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Niall Douglas (s_sourceforge@nedprod.com) <spam@spamtrap.com>
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

import libbe
import libbe.command
import libbe.command.util

import sys, os

class Web (libbe.command.Command):
    "Run the web interface"
    name = 'web'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)

    def _run(self, **params):
        storage = self._get_storage()
        repo = storage.repo
        os.execl(sys.executable, sys.executable, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "interfaces", "web", "cfbe.py")), repo)
        return 0

    def _long_help(self):
        return "Launch the web interface"
