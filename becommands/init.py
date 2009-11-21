# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
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
"""Assign the root directory for bug tracking"""
import os.path
from libbe import cmdutil, bugdir
__desc__ = __doc__

def execute(args, manipulate_encodings=True, restrict_file_access=False):
    """
    >>> from libbe import utility, vcs
    >>> import os
    >>> dir = utility.Dir()
    >>> try:
    ...     bugdir.BugDir(dir.path)
    ... except bugdir.NoBugDir, e:
    ...     True
    True
    >>> execute(['--root', dir.path], manipulate_encodings=False)
    No revision control detected.
    Directory initialized.
    >>> dir.cleanup()

    >>> dir = utility.Dir()
    >>> os.chdir(dir.path)
    >>> _vcs = vcs.installed_vcs()
    >>> _vcs.init('.')
    >>> _vcs.name in vcs.VCS_ORDER
    True
    >>> execute([], manipulate_encodings=False)  # doctest: +ELLIPSIS
    Using ... for revision control.
    Directory initialized.
    >>> _vcs.cleanup()

    >>> try:
    ...     execute(['--root', '.'], manipulate_encodings=False)
    ... except cmdutil.UserError, e:
    ...     str(e).startswith("Directory already initialized: ")
    True
    >>> execute(['--root', '/highly-unlikely-to-exist'], manipulate_encodings=False)
    Traceback (most recent call last):
    UserError: No such directory: /highly-unlikely-to-exist
    >>> os.chdir('/')
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) > 0:
        raise cmdutil.UsageError
    try:
        bd = bugdir.BugDir(options.root_dir, from_disk=False,
                           sink_to_existing_root=False,
                           assert_new_BugDir=True,
                           manipulate_encodings=manipulate_encodings)
    except bugdir.NoRootEntry:
        raise cmdutil.UserError("No such directory: %s" % options.root_dir)
    except bugdir.AlreadyInitialized:
        raise cmdutil.UserError("Directory already initialized: %s" % options.root_dir)
    bd.save()
    if bd.vcs.name is not "None":
        print "Using %s for revision control." % bd.vcs.name
    else:
        print "No revision control detected."
    print "Directory initialized."

def get_parser():
    parser = cmdutil.CmdOptionParser("be init")
    parser.add_option("-r", "--root", metavar="DIR", dest="root_dir",
                      help="Set root dir to something other than the current directory.",
                      default=".")
    return parser

longhelp="""
This command initializes Bugs Everywhere support for the specified directory
and all its subdirectories.  It will auto-detect any supported revision control
system.  You can use "be set vcs_name" to change the vcs being used.

The directory defaults to your current working directory.

It is usually a good idea to put the Bugs Everywhere root at the source code
root, but you can put it anywhere.  If you root Bugs Everywhere in a
subdirectory, then only bugs created in that subdirectory (and its children)
will appear there.
"""

def help():
    return get_parser().help_str() + longhelp
