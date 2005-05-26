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
from popen2 import Popen3
import os
import config

def invoke(args):
    q=Popen3(args, True)
    output = q.fromchild.read()
    error = q.childerr.read()
    status = q.wait()
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status), output, error
    raise Exception("Command failed: %s" % error)

def invoke_client(*args, **kwargs):
    cl_args = ["bzr"]
    cl_args.extend(args)
    status,output,error = invoke(cl_args)
    if status not in (0,):
        raise Exception("Command failed: %s" % error)
    return output

def add_id(filename, paranoid=False):
    invoke_client("add", filename)

def delete_id(filename):
    invoke_client("remove", filename)

def mkdir(path, paranoid=False):
    os.mkdir(path)
    add_id(path)

def set_file_contents(path, contents):
    add = not os.path.exists(path)
    file(path, "wb").write(contents)
    if add:
        add_id(path)

def lookup_revision(revno):
    return invoke_client("lookup-revision", str(revno)).rstrip('\n')

def export(revno, revision_dir):
    invoke_client("export", "-r", str(revno), revision_dir)

def find_or_make_export(revno):
    revision_id = lookup_revision(revno)
    home = os.path.expanduser("~")
    revision_root = os.path.join(home, ".bzrrevs")
    if not os.path.exists(revision_root):
        os.mkdir(revision_root)
    revision_dir = os.path.join(revision_root, revision_id)
    if not os.path.exists(revision_dir):
        export(revno, revision_dir)
    return revision_dir

def bzr_root(path):
    return invoke_client("root", path).rstrip('\r')

def path_in_reference(bug_dir, spec):
    if spec is None:
        spec = int(invoke_client("revno"))
    rel_bug_dir = bug_dir[len(bzr_root(bug_dir)):]
    export_root = find_or_make_export(spec)
    return os.path.join(export_root, rel_bug_dir)


def unlink(path):
    try:
        os.unlink(path)
        delete_id(path)
    except OSError, e:
        if e.errno != 2:
            raise


def detect(path):
    """Detect whether a directory is revision-controlled using bzr"""
    path = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(path, ".bzr")):
            return True
        if path == "/":
            return False
        path = os.path.dirname(path)


name = "bzr"
