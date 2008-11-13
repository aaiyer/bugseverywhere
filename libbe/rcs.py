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
from subprocess import Popen, PIPE
import sys

def rcs_by_name(rcs_name):
    """Return the module for the RCS with the given name"""
    if rcs_name == "Arch":
        import arch
        return arch
    elif rcs_name == "bzr":
        import bzr
        return bzr
    elif rcs_name == "hg":
        import hg
        return hg
    elif rcs_name == "git":
        import git
        return git
    elif rcs_name == "None":
        import no_rcs
        return no_rcs

def detect(dir):
    """Return the module for the rcs being used in this directory"""
    import arch
    import bzr
    import hg
    import git
    if arch.detect(dir):
        return arch
    elif bzr.detect(dir):
        return bzr
    elif hg.detect(dir):
        return hg
    elif git.detect(dir):
        return git
    import no_rcs
    return no_rcs

class CommandError(Exception):
    def __init__(self, err_str, status):
        Exception.__init__(self, "Command failed (%d): %s" % (status, err_str))
        self.err_str = err_str
        self.status = status

def invoke(args, expect=(0,), cwd=None):
    try :
        if sys.platform != "win32":
            q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, cwd=cwd)
        else:
            # win32 don't have os.execvp() so have to run command in a shell
            q = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True, 
                      cwd=cwd)
    except OSError, e :
        strerror = "%s\nwhile executing %s" % (e.args[1], args)
        raise CommandError(strerror, e.args[0])
    output, error = q.communicate()
    status = q.wait()
    if status not in expect:
        raise CommandError(error, status)
    return status, output, error
