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

"""Compare bug reports with older tree"""
from libbe import cmdutil, bugdir, diff
import os
__desc__ = __doc__

def execute(args, manipulate_encodings=True, restrict_file_access=False):
    """
    >>> import os
    >>> bd = bugdir.SimpleBugDir()
    >>> bd.set_sync_with_disk(True)
    >>> original = bd.vcs.commit("Original status")
    >>> bug = bd.bug_from_uuid("a")
    >>> bug.status = "closed"
    >>> changed = bd.vcs.commit("Closed bug a")
    >>> os.chdir(bd.root)
    >>> if bd.vcs.versioned == True:
    ...     execute([original], manipulate_encodings=False)
    ... else:
    ...     print "Modified bugs:\\n  a:cm: Bug A\\n    Changed bug settings:\\n      status: open -> closed"
    Modified bugs:
      a:cm: Bug A
        Changed bug settings:
          status: open -> closed
    >>> if bd.vcs.versioned == True:
    ...     execute(["--subscribe", "%(bugdir_id)s:mod", "--uuids", original],
    ...             manipulate_encodings=False)
    ... else:
    ...     print "a"
    a
    >>> if bd.vcs.versioned == False:
    ...     execute([original], manipulate_encodings=False)
    ... else:
    ...     raise cmdutil.UsageError('This directory is not revision-controlled.')
    Traceback (most recent call last):
      ...
    UsageError: This directory is not revision-controlled.
    >>> bd.cleanup()
    """ % {'bugdir_id':diff.BUGDIR_ID}
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) == 0:
        revision = None
    if len(args) == 1:
        revision = args[0]
    if len(args) > 1:
        raise cmdutil.UsageError('Too many arguments.')
    try:
        subscriptions = diff.subscriptions_from_string(
            options.subscribe)
    except ValueError, e:
        raise cmdutil.UsageError(e.msg)
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    if bd.vcs.versioned == False:
        raise cmdutil.UsageError('This directory is not revision-controlled.')
    if options.dir == None:
        if revision == None: # get the most recent revision
            revision = bd.vcs.revision_id(-1)
        old_bd = bd.duplicate_bugdir(revision)
    else:
        cwd = os.getcwd()
        os.chdir(options.dir)
        old_bd_current = bugdir.BugDir(from_disk=True,
                                       manipulate_encodings=False)
        if revision == None: # use the current working state
            old_bd = old_bd_current
        else:
            if old_bd_current.vcs.versioned == False:
                raise cmdutil.UsageError('%s is not revision-controlled.'
                                         % options.dir)
            old_bd = old_bd_current.duplicate_bugdir(revision)
        os.chdir(cwd)
    d = diff.Diff(old_bd, bd)
    tree = d.report_tree(subscriptions)

    if options.uuids == True:
        uuids = []
        bugs = tree.child_by_path('/bugs')
        for bug_type in bugs:
            uuids.extend([bug.name for bug in bug_type])
        print '\n'.join(uuids)
    else :
        rep = tree.report_string()
        if rep != None:
            print rep
    bd.remove_duplicate_bugdir()
    if options.dir != None and revision != None:
        old_bd_current.remove_duplicate_bugdir()

def get_parser():
    parser = cmdutil.CmdOptionParser("be diff [options] REVISION")
    parser.add_option("-d", "--dir", dest="dir", metavar="DIR",
                      help="Compare with repository in DIR instead of the current directory.")
    parser.add_option("-s", "--subscribe", dest="subscribe", metavar="SUBSCRIPTION",
                      help="Only print changes matching SUBSCRIPTION, subscription is a comma-separ\ated list of ID:TYPE tuples.  See `be subscribe --help` for descriptions of ID and TYPE.")
    parser.add_option("-u", "--uuids", action="store_true", dest="uuids",
                      help="Only print the bug UUIDS.", default=False)
    return parser

longhelp="""
Uses the VCS to compare the current tree with a previous tree, and
prints a pretty report.  If REVISION is given, it is a specifier for
the particular previous tree to use.  Specifiers are specific to their
VCS.

For Arch your specifier must be a fully-qualified revision name.

Besides the standard summary output, you can use the options to output
UUIDS for the different categories.  This output can be used as the
input to 'be show' to get an understanding of the current status.
"""

def help():
    return get_parser().help_str() + longhelp
