# Copyright (C) 2008-2009 Gianluca Montecchi <gian@grys.it>
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

"""
Handle ID creation and parsing.
"""

import os.path

import libbe

if libbe.TESTING == True:
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


def _assemble(*args):
    args = list(args)
    for i,arg in enumerate(args):
        if arg == None:
            args[i] = ''
    return '/'.join(args)

def _split(id):
    args = id.split('/')
    for i,arg in enumerate(args):
        if arg == '':
            args[i] = None
    return args

def _is_a_uuid(id):
    if id.startswith('uuid:'):
        return True
    return False

def _uuid_to_id(id):
    return 'uuid:' + id

def _id_to_uuid(id):
    return id[len('uuid:'):]

def bugdir_id(bugdir, *args):
    return _assemble(_uuid_to_id(bugdir.uuid), *args)

def bug_id(bug, *args):
    if bug.bugdir == None:
        bdid = None
    else:
        bdid = bugdir_id(bug.bugdir)
    return _assemble(bdid, _uuid_to_id(bug.uuid), *args)

def comment_id(comment, *args):
    if comment.bug == None:
        bid = None
    else:
        bid = bug_id(comment.bug)
    return _assemble(bid, _uuid_to_id(comment.uuid), *args)

def parse_id(id):
    args = _split(id)    
    ret = {'bugdir':_id_to_uuid(args.pop(0))}
    type = 'bugdir'
    for child_name in ['bug', 'comment']:
        if len(args) > 0 and _is_a_uuid(args[0]):
            ret[child_name] = _id_to_uuid(args.pop(0))
            type = child_name
    ret['type'] = type
    ret['remaining'] = os.path.join(args)
    return ret

if libbe.TESTING == True:
    class UUIDtestCase(unittest.TestCase):
        def testUUID_gen(self):
            id = uuid_gen()
            self.failUnless(len(id) == 36, "invalid UUID '%s'" % id)

    suite = unittest.TestLoader().loadTestsFromTestCase(UUIDtestCase)
