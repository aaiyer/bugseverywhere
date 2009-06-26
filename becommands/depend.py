# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
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
"""Add/remove bug dependencies"""
from libbe import cmdutil, bugdir
import os, copy
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> from libbe import utility
    >>> bd = bugdir.simple_bug_dir()
    >>> bd.save()
    >>> os.chdir(bd.root)
    >>> execute(["a", "b"], test=True)
    Blocks on a:
    b
    >>> execute(["a"], test=True)
    Blocks on a:
    b
    >>> execute(["-r", "a", "b"], test=True)
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
    
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
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
        bugA.save()

    depends = []
    for estr in bugA.extra_strings:
        if estr.startswith("BLOCKED-BY:"):
            depends.append(estr[11:])
    if len(depends) > 0:
        print "Blocks on %s:" % bugA.uuid
        print '\n'.join(depends)

def get_parser():
    parser = cmdutil.CmdOptionParser("be depend BUG-ID [BUG-ID]")
    parser.add_option("-r", "--remove", action="store_true", dest="remove",
                      help="Remove dependency (instead of adding it)")
    return parser

longhelp="""
Set a dependency with the second bug (B) blocking the first bug (A).
If bug B is not specified, just print a list of bugs blocking (A).

To search for bugs blocked by a particular bug, try
  $ be list --extra-strings BLOCKED-BY:<your-bug-uuid>
"""

def help():
    return get_parser().help_str() + longhelp
