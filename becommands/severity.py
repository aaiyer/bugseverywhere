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
"""Show or change a bug's severity level"""
from libbe import cmdutil, bugdir, bug
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import os
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute(["a"], test=True)
    minor
    >>> execute(["a", "wishlist"], test=True)
    >>> execute(["a"], test=True)
    wishlist
    >>> execute(["a", "none"], test=True)
    Traceback (most recent call last):
    UserError: Invalid severity level: none
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})
    if len(args) not in (1,2):
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
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
        bd.save()

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
