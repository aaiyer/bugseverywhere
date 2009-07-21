# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
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
"""Add/remove bug dependencies"""
from libbe import cmdutil, bugdir
import os, copy
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> from libbe import utility
    >>> bd = bugdir.simple_bug_dir()
    >>> bd.save()
    >>> os.chdir(bd.root)
    >>> execute(["a", "b"], manipulate_encodings=False)
    Blocks on a:
    b
    >>> execute(["a"], manipulate_encodings=False)
    Blocks on a:
    b
    >>> execute(["--show-status", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Blocks on a:
    b closed
    >>> execute(["-r", "a", "b"], manipulate_encodings=False)
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True,
                                         1: lambda bug : bug.active==True})

    if len(args) < 1:
        raise cmdutil.UsageError("Please a bug id.")
    if len(args) > 2:
        help()
        raise cmdutil.UsageError("Too many arguments.")
    
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bugA = bd.bug_from_shortname(args[0])
    if len(args) == 2:
        bugB = bd.bug_from_shortname(args[1])
        estrs = bugA.extra_strings
        depend_string = "BLOCKED-BY:%s" % bugB.uuid
        if options.remove == True:
            estrs.remove(depend_string)
        else: # add the dependency
            estrs.append(depend_string)
        bugA.extra_strings = estrs # reassign to notice change

    depends = []
    for estr in bugA.extra_strings:
        if estr.startswith("BLOCKED-BY:"):
            uuid = estr[11:]
            if options.show_status == True:
                blocker = bd.bug_from_uuid(uuid)
                block_string = "%s\t%s" % (uuid, blocker.status)
            else:
                block_string = uuid
            depends.append(block_string)
    if len(depends) > 0:
        print "Blocks on %s:" % bugA.uuid
        print '\n'.join(depends)

def get_parser():
    parser = cmdutil.CmdOptionParser("be depend BUG-ID [BUG-ID]")
    parser.add_option("-r", "--remove", action="store_true", dest="remove",
                      help="Remove dependency (instead of adding it)")
    parser.add_option("-s", "--show-status", action="store_true",
                      dest="show_status",
                      help="Show status of blocking bugs")
    return parser

longhelp="""
Set a dependency with the second bug (B) blocking the first bug (A).
If bug B is not specified, just print a list of bugs blocking (A).

To search for bugs blocked by a particular bug, try
  $ be list --extra-strings BLOCKED-BY:<your-bug-uuid>
"""

def help():
    return get_parser().help_str() + longhelp
