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
from libbe import cmdutil 
from libbe.bug import severity_values, severity_description
__desc__ = __doc__

def execute(args):
    """
    >>> from libbe import tests
    >>> import os
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> execute(["a"])
    minor
    >>> execute(["a", "wishlist"])
    >>> execute(["a"])
    wishlist
    >>> execute(["a", "none"])
    Traceback (most recent call last):
    UserError: Invalid severity level: none
    >>> tests.clean_up()
    """
    options, args = get_parser().parse_args(args)
    assert(len(args) in (0, 1, 2))
    if len(args) == 0:
        print help()
        return
    bug = cmdutil.get_bug(args[0])
    if len(args) == 1:
        print bug.severity
    elif len(args) == 2:
        try:
            bug.severity = args[1]
        except ValueError, e:
            if e.name != "severity":
                raise
            raise cmdutil.UserError ("Invalid severity level: %s" % e.value)
        bug.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be severity bug-id [severity]")
    return parser

longhelp=["""
Show or change a bug's severity level.

If no severity is specified, the current value is printed.  If a severity level
is specified, it will be assigned to the bug.

Severity levels are:
"""]
longest_severity_len = max([len(s) for s in severity_values])
for severity in severity_values :
    description = severity_description[severity]
    s = "%*s : %s\n" % (longest_severity_len, severity, description)
    longhelp.append(s)
longhelp = ''.join(longhelp)


def help():
    return get_parser().help_str() + longhelp
