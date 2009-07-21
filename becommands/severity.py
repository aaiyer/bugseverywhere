# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
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
"""Show or change a bug's severity level"""
from libbe import cmdutil, bugdir, bug
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute(["a"], manipulate_encodings=False)
    minor
    >>> execute(["a", "wishlist"], manipulate_encodings=False)
    >>> execute(["a"], manipulate_encodings=False)
    wishlist
    >>> execute(["a", "none"], manipulate_encodings=False)
    Traceback (most recent call last):
    UserError: Invalid severity level: none
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) not in (1,2):
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bug = bd.bug_from_shortname(args[0])
    if len(args) == 1:
        print bug.severity
    elif len(args) == 2:
        try:
            bug.severity = args[1]
        except ValueError, e:
            if e.name != "severity":
                raise e
            raise cmdutil.UserError ("Invalid severity level: %s" % e.value)

def get_parser():
    parser = cmdutil.CmdOptionParser("be severity BUG-ID [SEVERITY]")
    return parser

def help():
    longhelp=["""
Show or change a bug's severity level.

If no severity is specified, the current value is printed.  If a severity level
is specified, it will be assigned to the bug.

Severity levels are:
"""]
    try: # See if there are any per-tree severity configurations
        bd = bugdir.BugDir(from_disk=True, manipulate_encodings=False)
    except bugdir.NoBugDir, e:
        pass # No tree, just show the defaults
    longest_severity_len = max([len(s) for s in bug.severity_values])
    for severity in bug.severity_values :
        description = bug.severity_description[severity]
        s = "%*s : %s\n" % (longest_severity_len, severity, description)
        longhelp.append(s)
    longhelp = ''.join(longhelp)
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option,value in cmdutil.option_value_pairs(options, parser):
        if value == "--complete":
            # no argument-options at the moment, so this is future-proofing
            raise cmdutil.GetCompletions()
    for pos,value in enumerate(args):
        if value == "--complete":
            try: # See if there are any per-tree severity configurations
                bd = bugdir.BugDir(from_disk=True,
                                   manipulate_encodings=False)
            except bugdir.NoBugDir:
                bd = None
            if pos == 0: # fist positional argument is a bug id 
                ids = []
                if bd != None:
                    bd.load_all_bugs()
                    filter = lambda bg : bg.active==True
                    bugs = [bg for bg in bd if filter(bg)==True]
                    ids = [bd.bug_shortname(bg) for bg in bugs]
                raise cmdutil.GetCompletions(ids)
            elif pos == 1: # second positional argument is a severity
                raise cmdutil.GetCompletions(bug.severity_values)
            raise cmdutil.GetCompletions()
