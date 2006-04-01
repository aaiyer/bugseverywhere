# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Bug fixing in progress"""
from libbe import cmdutil
def execute(args):
    """
    >>> from libbe import tests
    >>> import os
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> dir.get_bug("a").status
    u'open'
    >>> execute(("a",))
    >>> dir.get_bug("a").status
    u'in-progress'
    >>> tests.clean_up()
    """
    assert(len(args) == 1)
    bug = cmdutil.get_bug(args[0])
    bug.status = "in-progress"
    bug.save()
