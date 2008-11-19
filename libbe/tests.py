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
import tempfile
import shutil
from libbe import utility, names, restconvert, mapfile, config, diff, rcs, \
    arch, bzr, git, hg, bug, bugdir, plugin, cmdutil
import unittest

# can not use 'suite' or the base test.py file will include these suites twice.
testsuite = unittest.TestSuite([utility.suite, names.suite, restconvert.suite,
                                mapfile.suite, config.suite, diff.suite,
                                rcs.suite, arch.suite, bzr.suite, git.suite,
                                hg.suite, bug.suite, bugdir.suite,
                                plugin.suite, cmdutil.suite])

if __name__ == "__main__":
    unittest.TextTestRunner(verbosity=2).run(testsuite)
