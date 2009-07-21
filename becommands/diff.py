# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
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

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> bd.set_sync_with_disk(True)
    >>> original = bd.rcs.commit("Original status")
    >>> bug = bd.bug_from_uuid("a")
    >>> bug.status = "closed"
    >>> changed = bd.rcs.commit("Closed bug a")
    >>> os.chdir(bd.root)
    >>> if bd.rcs.versioned == True:
    ...     execute([original], manipulate_encodings=False)
    ... else:
    ...     print "a:cm: Bug A\\nstatus: open -> closed\\n"
    Modified bug reports:
    a:cm: Bug A
      status: open -> closed
    <BLANKLINE>
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser)
    if len(args) == 0:
        revision = None
    if len(args) == 1:
        revision = args[0]
    if len(args) > 1:
        raise cmdutil.UsageError("Too many arguments.")
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    if bd.rcs.versioned == False:
        print "This directory is not revision-controlled."
    else:
        old_bd = bd.duplicate_bugdir(revision)
        r,m,a = diff.diff(old_bd, bd)
        
        optbugs = []
        if options.all == True:
            options.new = options.modified = options.removed = True
        if options.new == True:
            optbugs.extend(a)
        if options.modified == True:
            optbugs.extend([new for old,new in m])
        if options.removed == True:
            optbugs.extend(r)
        if len(optbugs) > 0:
            for bug in optbugs:
                print bug.uuid
        else :
            print diff.diff_report((r,m,a), bd).encode(bd.encoding)
        bd.remove_duplicate_bugdir()

def get_parser():
    parser = cmdutil.CmdOptionParser("be diff [options] REVISION")
    # boolean options
    bools = (("n", "new", "Print UUIDS for new bugs"),
             ("m", "modified", "Print UUIDS for modified bugs"),
             ("r", "removed", "Print UUIDS for removed bugs"),
             ("a", "all", "Print UUIDS for all changed bugs"))
    for s in bools:
        attr = s[1].replace('-','_')
        short = "-%c" % s[0]
        long = "--%s" % s[1]
        help = s[2]
        parser.add_option(short, long, action="store_true",
                          dest=attr, help=help)
    return parser

longhelp="""
Uses the RCS to compare the current tree with a previous tree, and
prints a pretty report.  If REVISION is given, it is a specifier for
the particular previous tree to use.  Specifiers are specific to their
RCS.

For Arch your specifier must be a fully-qualified revision name.

Besides the standard summary output, you can use the options to output
UUIDS for the different categories.  This output can be used as the
input to 'be show' to get and understanding of the current status.
"""

def help():
    return get_parser().help_str() + longhelp
