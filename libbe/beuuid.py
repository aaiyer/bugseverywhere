# Copyright (C) 2008-2009 W. Trevor King <wking@drexel.edu>
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
"""
Backwards compatibility support for Python 2.4.  Once people give up
on 2.4 ;), the uuid call should be merged into bugdir.py
"""

import unittest

try:
    from uuid import uuid4 # Python >= 2.5
    def uuid_gen():
        id = uuid4()
        idstr = id.urn
        start = "urn:uuid:"
        assert idstr.startswith(start)
        return idstr[len(start):]
except ImportError:
    import os
    import sys
    from subprocess import Popen, PIPE

    def uuid_gen():
        # Shell-out to system uuidgen
        args = ['uuidgen', 'r']
        try:
            if sys.platform != "win32":
                q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            else:
                # win32 don't have os.execvp() so have to run command in a shell
                q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, 
                          shell=True, cwd=cwd)
        except OSError, e :
            strerror = "%s\nwhile executing %s" % (e.args[1], args)
            raise OSError, strerror
        output, error = q.communicate()
        status = q.wait()
        if status != 0:
            strerror = "%s\nwhile executing %s" % (status, args)
            raise Exception, strerror
        return output.rstrip('\n')

class UUIDtestCase(unittest.TestCase):
    def testUUID_gen(self):
        id = uuid_gen()
        self.failUnless(len(id) == 36, "invalid UUID '%s'" % id)

suite = unittest.TestLoader().loadTestsFromTestCase(UUIDtestCase)
