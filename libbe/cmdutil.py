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
import bugdir
import plugin
import os
import optparse
import utility

def unique_name(bug, bugs):
    chars = 1
    for some_bug in bugs:
        if bug.uuid == some_bug.uuid:
            continue
        while (bug.uuid[:chars] == some_bug.uuid[:chars]):
            chars+=1
        if chars < 3:
            chars = 3
    return bug.uuid[:chars]

class UserError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class UserErrorWrap(UserError):
    def __init__(self, exception):
        UserError.__init__(self, str(exception))
        self.exception = exception

def get_bug(spec, bug_dir=None):
    matches = []
    try:
        if bug_dir is None:
            bug_dir = bugdir.tree_root('.')
    except bugdir.NoBugDir, e:
        raise UserErrorWrap(e)
    bugs = list(bug_dir.list())
    for bug in bugs:
        if bug.uuid.startswith(spec):
            matches.append(bug)
    if len(matches) > 1:
        raise UserError("More than one bug matches %s.  Please be more"
                        " specific." % spec)
    if len(matches) == 1:
        return matches[0]
        
    matches = []
    if len(matches) == 0:
        raise UserError("No bug matches %s" % spec)
    return matches[0]

def bug_summary(bug, bugs, no_target=False, shortlist=False):
    target = bug.target
    if target is None or no_target:
        target = ""
    else:
        target = "  Target: %s" % target
    if bug.assigned is None:
        assigned = ""
    else:
        assigned = "  Assigned: %s" % bug.assigned
    if shortlist == False:
       return "  ID: %s\n  Severity: %s\n%s%s\n  Creator: %s \n%s\n" % \
            (unique_name(bug, bugs), bug.severity, assigned, target,
             bug.creator, bug.summary)
    else:
       return "%4s: %s\n" % (unique_name(bug, bugs), bug.summary)

def iter_commands():
    for name, module in plugin.iter_plugins("becommands"):
        yield name.replace("_", "-"), module

def get_command(command_name):
    """Retrieves the module for a user command

    >>> get_command("asdf")
    Traceback (most recent call last):
    UserError: Unknown command asdf
    >>> repr(get_command("list")).startswith("<module 'becommands.list' from ")
    True
    """
    cmd = plugin.get_plugin("becommands", command_name.replace("-", "_"))
    if cmd is None:
        raise UserError("Unknown command %s" % command_name)
    return cmd

def execute(cmd, args):
    return get_command(cmd).execute(args)

def help(cmd):
    return get_command(cmd).help()


class GetHelp(Exception):
    pass


class UsageError(Exception):
    pass


def raise_get_help(option, opt, value, parser):
    raise GetHelp


class CmdOptionParser(optparse.OptionParser):
    def __init__(self, usage):
        optparse.OptionParser.__init__(self, usage)
        self.remove_option("-h")
        self.add_option("-h", "--help", action="callback", 
                        callback=raise_get_help, help="Print a help message")

    def error(self, message):
        raise UsageError(message)

    def iter_options(self):
        return iter_combine([self._short_opt.iterkeys(), 
                            self._long_opt.iterkeys()])

    def help_str(self):
        fs = utility.FileString()
        self.print_help(fs)
        return fs.str


def underlined(instring):
    """Produces a version of a string that is underlined with '='

    >>> underlined("Underlined String")
    'Underlined String\\n================='
    """
    
    return "%s\n%s" % (instring, "="*len(instring))


def bug_tree(dir=None):
    """Retrieve the bug tree specified by the user.  If no directory is
    specified, the current working directory is used.

    :param dir: The directory to search for the bug tree in.

    >>> bug_tree() is not None
    True
    >>> bug_tree("/")
    Traceback (most recent call last):
    UserErrorWrap: The directory "/" has no bug directory.
    """
    if dir is None:
        dir = os.getcwd()
    try:
        return bugdir.tree_root(dir)
    except bugdir.NoBugDir, e:
        raise UserErrorWrap(e)


def _test():
    import doctest
    import sys
    doctest.testmod()

if __name__ == "__main__":
    _test()
