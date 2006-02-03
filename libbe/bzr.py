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
import os
import tempfile

import config
from rcs import invoke, CommandError

def invoke_client(*args, **kwargs):
    directory = kwargs['directory']
    expect = kwargs.get('expect', (0, 1))
    cl_args = ["bzr"]
    cl_args.extend(args)
    if directory:
        old_dir = os.getcwd()
        os.chdir(directory)
    try:
        status,output,error = invoke(cl_args, expect)
    finally:
        if directory:
            os.chdir(old_dir)
    return status, output

def add_id(filename, paranoid=False):
    invoke_client("add", filename, directory='.')

def delete_id(filename):
    invoke_client("remove", filename, directory='.')

def mkdir(path, paranoid=False):
    os.mkdir(path)
    add_id(path)

def set_file_contents(path, contents):
    add = not os.path.exists(path)
    file(path, "wb").write(contents)
    if add:
        add_id(path)

def lookup_revision(revno, directory):
    return invoke_client("lookup-revision", str(revno), 
                         directory=directory).rstrip('\n')[1]

def export(revno, directory, revision_dir):
    invoke_client("export", "-r", str(revno), revision_dir, directory=directory)

def find_or_make_export(revno, directory):
    revision_id = lookup_revision(revno, directory)
    home = os.path.expanduser("~")
    revision_root = os.path.join(home, ".bzrrevs")
    if not os.path.exists(revision_root):
        os.mkdir(revision_root)
    revision_dir = os.path.join(revision_root, revision_id)
    if not os.path.exists(revision_dir):
        export(revno, directory, revision_dir)
    return revision_dir

def bzr_root(path):
    return invoke_client("root", path, dirctory=None).rstrip('\r')[1]

def path_in_reference(bug_dir, spec):
    if spec is None:
        spec = int(invoke_client("revno", directory=bug_dir)[1])
    rel_bug_dir = bug_dir[len(bzr_root(bug_dir)):]
    export_root = find_or_make_export(spec, directory=bug_dir)
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
    old_path = None
    while True:
        if os.path.exists(os.path.join(path, ".bzr")):
            return True
        if path == old_path:
            return False
        old_path = path
        path = os.path.dirname(path)

def precommit(directory):
    pass

def commit(directory, summary, body=None):
    if body is not None:
        summary += '\n' + body
    descriptor, filename = tempfile.mkstemp()
    try:
        temp_file = os.fdopen(descriptor, 'wb')
        temp_file.write(summary)
        temp_file.close()
        invoke_client('commit', '--unchanged', '--file', filename, 
                      directory=directory)
    finally:
        os.unlink(filename)

def postcommit(directory):
    try:
        invoke_client('merge', directory=directory)
    except CommandError:
        status = invoke_client('revert --no-backup', directory=directory)
        status = invoke_client('resolve --all', directory=directory)
        raise
    if len(invoke_client('status', directory=directory)[1]) > 0:
        commit(directory, 'Merge from upstream')
    
name = "bzr"
