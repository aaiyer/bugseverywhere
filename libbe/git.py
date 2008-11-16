# Copyright (C) 2007 Chris Ball <chris@printf.net>
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

from rcs import invoke

def strip_git(filename):
    # Find the base path of the GIT tree, in order to strip that leading
    # path from arguments to git -- it doesn't like absolute paths.
    if os.path.isabs(filename):
        absRepoDir = os.path.abspath(git_repo_for_path('.'))
        absRepoSlashedDir = os.path.join(absRepoDir,"")
        assert filename.startswith(absRepoSlashedDir), \
            "file %s not in git repo %s" % (filename, absRepoSlashedDir)
        filename = filename[len(absRepoSlashedDir):]
    return filename

def invoke_client(*args, **kwargs):
    directory = kwargs['directory']
    expect = kwargs.get('expect', (0, 1))
    cl_args = ["git"]
    cl_args.extend(args)
    status,output,error = invoke(cl_args, expect, cwd=directory)
    return status, output

def add_id(filename, paranoid=False):
    filename = strip_git(filename)
    invoke_client("add", filename, directory=git_repo_for_path('.'))

def delete_id(filename):
    filename = strip_git(filename)
    invoke_client("rm", filename, directory=git_repo_for_path('.'))

def mkdir(path, paranoid=False):
    os.mkdir(path)

def set_file_contents(path, contents):
    add = not os.path.exists(path)
    file(path, "wb").write(contents)
    if add:
        add_id(path)

def detect(path):
    """Detect whether a directory is revision-controlled using GIT"""
    path = os.path.realpath(path)
    old_path = None
    while True:
        if os.path.exists(os.path.join(path, ".git")):
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
        invoke_client('commit', '-a', '-F', filename, directory=directory)
    finally:
        os.unlink(filename)

def postcommit(directory):
    pass


# In order to diff the bug database, you need a way to check out arbitrary
# previous revisions and a mechanism for locating the bug_dir in the revision
# you've checked out.
#
# Copying the Mercurial implementation, this feature is implemented by four
# functions:
#
# git_dir_for_path : find '.git' for a git tree.
#
# export : check out a commit 'spec' from git-repo 'bug_dir' into a dir
#          'revision_dir'
#
# find_or_make_export : check out a commit 'spec' from git repo 'directory' to
#                       any location you please and return the path to the checkout
#
# path_in_reference : return a path to the bug_dir of the commit 'spec'

def git_repo_for_path(path):
    """Find the root of the deepest repository containing path."""
    # Assume that nothing funny is going on; in particular, that we aren't
    # dealing with a bare repo.
    dirname = os.path.dirname(git_dir_for_path(path))
    if dirname == '' : # os.path.dirname('filename') == ''
        dirname = '.'
    return dirname

def git_dir_for_path(path):
    """Find the git-dir of the deepest repo containing path."""
    return invoke_client("rev-parse", "--git-dir", directory=path)[1].rstrip()

def export(spec, bug_dir, revision_dir):
    """Check out commit 'spec' from the git repo containing bug_dir into
    'revision_dir'."""
    if not os.path.exists(revision_dir):
        os.makedirs(revision_dir)
    invoke_client("init", directory=revision_dir)
    invoke_client("pull", git_dir_for_path(bug_dir), directory=revision_dir)
    invoke_client("checkout", '-f', spec, directory=revision_dir)

def find_or_make_export(spec, directory):
    """Checkout 'spec' from the repo at 'directory' by hook or by crook and
    return the path to the working copy."""
    home = os.path.expanduser("~")
    revision_root = os.path.join(home, ".be_revs")
    if not os.path.exists(revision_root):
        os.mkdir(revision_root)
    revision_dir = os.path.join(revision_root, spec)
    if not os.path.exists(revision_dir):
        export(spec, directory, revision_dir)
    return revision_dir

def path_in_reference(bug_dir, spec):
    """Check out 'spec' and return the path to its bug_dir."""
    spec = spec or 'HEAD'
    spec = invoke_client('rev-parse', spec, directory=bug_dir)[1].rstrip()
    # This is a really hairy computation.
    # The theory is that we can't possibly be working out of a bare repo;
    # hence, we get the rel_bug_dir by chopping off dirname(git_dir_for_path(bug_dir))
    # + '/'.
    rel_bug_dir = strip_git(bug_dir)
    export_root = find_or_make_export(spec, directory=bug_dir)
    return os.path.join(export_root, rel_bug_dir)


name = "git"

