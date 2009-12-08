# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marienz@gentoo.org>
#                         Thomas Gerigk <tgerigk@gmx.de>
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
"""Assorted bug target manipulations and queries"""
from libbe import cmdutil, bugdir
from becommands import depend
__desc__ = __doc__

def execute(args, manipulate_encodings=True, restrict_file_access=False,
            dir="."):
    """
    >>> import os, StringIO, sys
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> execute(["a"], manipulate_encodings=False)
    No target assigned.
    >>> execute(["a", "tomorrow"], manipulate_encodings=False)
    >>> execute(["a"], manipulate_encodings=False)
    tomorrow

    >>> orig_stdout = sys.stdout
    >>> tmp_stdout = StringIO.StringIO()
    >>> sys.stdout = tmp_stdout
    >>> execute(["--resolve", "tomorrow"], manipulate_encodings=False)
    >>> sys.stdout = orig_stdout
    >>> output = tmp_stdout.getvalue().strip()
    >>> target = bd.bug_from_uuid(output)
    >>> print target.summary
    tomorrow
    >>> print target.severity
    target

    >>> execute(["a", "none"], manipulate_encodings=False)
    >>> execute(["a"], manipulate_encodings=False)
    No target assigned.
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
                             
    if (options.resolve == False and len(args) not in (1, 2)) \
            or (options.resolve == True and len(args) not in (0, 1)):
            raise cmdutil.UsageError('Incorrect number of arguments.')
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings,
                       root=dir)
    if options.resolve == True:
        if len(args) == 0:
            summary = None
        else:
            summary = args[0]
        bug = bug_from_target_summary(bd, summary)
        if bug == None:
            print 'No target assigned.'
        else:
            print bug.uuid
        return
    bug = cmdutil.bug_from_id(bd, args[0])
    if len(args) == 1:
        target = bug_target(bd, bug)
        if target is None:
            print "No target assigned."
        else:
            print target.summary
    else:
        if args[1] == "none":
            target = remove_target(bd, bug)
        else:
            target = add_target(bd, bug, args[1])

def get_parser():
    parser = cmdutil.CmdOptionParser("be target BUG-ID [TARGET]\nor:    be target --resolve [TARGET]")
    parser.add_option("-r", "--resolve", action="store_true", dest="resolve",
                      help="Print the UUID for the target bug whose summary matches TARGET.  If TARGET is not given, print the UUID of the current bugdir target.  If that is not set, don't print anything.",
                      default=False)
    return parser

longhelp="""
Assorted bug target manipulations and queries.

If no target is specified, the bug's current target is printed.  If
TARGET is specified, it will be assigned to the bug, creating a new
target bug if necessary.

Targets are free-form; any text may be specified.  They will generally
be milestone names or release numbers.  The value "none" can be used
to unset the target.

In the alternative `be target --resolve TARGET` form, print the UUID
of the target-bug with summary TARGET.  If target is not given, return
use the bugdir's current target (see `be set`).

If you want to list all bugs blocking the current target, try
  $ be depend --status -closed,fixed,wontfix --severity -target \
    $(be target --resolve)

If you want to set the current bugdir target by summary (rather than
by UUID), try
  $ be set target $(be target --resolve SUMMARY)
"""

def help():
    return get_parser().help_str() + longhelp

def bug_from_target_summary(bugdir, summary=None):
    if summary == None:
        if bugdir.target == None:
            return None
        else:
            return bugdir.bug_from_uuid(bugdir.target)
    matched = []
    for uuid in bugdir.uuids():
        bug = bugdir.bug_from_uuid(uuid)
        if bug.severity == 'target' and bug.summary == summary:
            matched.append(bug)
    if len(matched) == 0:
        return None
    if len(matched) > 1:
        raise Exception('Several targets with same summary:  %s'
                        % '\n  '.join([bug.uuid for bug in matched]))
    return matched[0]

def bug_target(bugdir, bug):
    if bug.severity == 'target':
        return bug
    matched = []
    for blocked in depend.get_blocks(bugdir, bug):
        if blocked.severity == 'target':
            matched.append(blocked)
    if len(matched) == 0:
        return None
    if len(matched) > 1:
        raise Exception('This bug (%s) blocks several targets:  %s'
                        % (bug.uuid,
                           '\n  '.join([b.uuid for b in matched])))
    return matched[0]

def remove_target(bugdir, bug):
    target = bug_target(bugdir, bug)
    depend.remove_block(target, bug)
    return target

def add_target(bugdir, bug, summary):
    target = bug_from_target_summary(bugdir, summary)
    if target == None:
        target = bugdir.new_bug(summary=summary)
        target.severity = 'target'
    depend.add_block(target, bug)
    return target
