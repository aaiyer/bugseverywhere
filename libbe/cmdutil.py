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
import locale
import os
import optparse
from textwrap import TextWrapper
from StringIO import StringIO
import utility

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
    encoding = locale.getpreferredencoding() or 'ascii'
    return get_command(cmd).execute([a.decode(encoding) for a in args])

def help(cmd=None):
    if cmd != None:
        return get_command(cmd).help()
    else:
        cmdlist = []
        for name, module in iter_commands():
            cmdlist.append((name, module.__desc__))
        longest_cmd_len = max([len(name) for name,desc in cmdlist])
        ret = ["Bugs Everywhere - Distributed bug tracking\n",
               "Supported commands"]
        for name, desc in cmdlist:
            numExtraSpaces = longest_cmd_len-len(name)
            ret.append("be %s%*s    %s" % (name, numExtraSpaces, "", desc))
        return "\n".join(ret)

class GetHelp(Exception):
    pass


class UsageError(Exception):
    pass


def raise_get_help(option, opt, value, parser):
    raise GetHelp


def iter_comment_name(bug, unique_name):
    """Iterate through id, comment pairs, in date order.
    (This is a user-friendly id, not the comment uuid)
    """
    def key(comment):
        return comment.time
    for num, comment in enumerate(sorted(bug.list_comments(), key=key)):
        yield ("%s:%d" % (unique_name, num+1), comment)


def comment_from_name(bug, unique_name, name):
    """Use a comment name to look up a comment"""
    for cur_name, comment in iter_comment_name(bug, unique_name):
        if name == cur_name:
            return comment
    raise KeyError(name)


def get_bug_and_comment(identifier, bug_dir=None):
    ids = identifier.split(':')
    bug = get_bug(ids[0], bug_dir)
    if len(ids) == 2:
        comment = comment_from_name(bug, ids[0], identifier)
    else:
        comment = None
    return bug, comment

        
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


def print_threaded_comments(comments, name_map, indent=""):
    """Print a threaded display of comments"""
    tw = TextWrapper(initial_indent = indent, subsequent_indent = indent, 
                     width=80)
    for comment, children in comments:
        s = StringIO()
        print >> s, "--------- Comment ---------"
        print >> s, "Name: %s" % name_map[comment.uuid]
        print >> s, "From: %s" % comment.From
        print >> s, "Date: %s\n" % utility.time_to_str(comment.time)
        print >> s, comment.body.rstrip('\n')

        s.seek(0)
        for line in s:
            print tw.fill(line).rstrip('\n')
        print_threaded_comments(children, name_map, indent=indent+"    ")


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
