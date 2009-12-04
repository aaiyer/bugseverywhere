# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
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

"""
Define assorted utilities to make command-line handling easier.
"""

import glob
import optparse
import os
from textwrap import TextWrapper
from StringIO import StringIO
import sys
import doctest

import bugdir
import comment
import plugin
import encoding

class UserError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class UnknownCommand(UserError):
    def __init__(self, cmd):
        Exception.__init__(self, "Unknown command '%s'" % cmd)
        self.cmd = cmd

class UsageError(Exception):
    pass

class GetHelp(Exception):
    pass

class GetCompletions(Exception):
    def __init__(self, completions=[]):
        msg = "Get allowed completions"
        Exception.__init__(self, msg)
        self.completions = completions

def iter_commands():
    for name, module in plugin.iter_plugins("becommands"):
        yield name.replace("_", "-"), module

def get_command(command_name):
    """Retrieves the module for a user command

    >>> try:
    ...     get_command("asdf")
    ... except UnknownCommand, e:
    ...     print e
    Unknown command 'asdf'
    >>> repr(get_command("list")).startswith("<module 'becommands.list' from ")
    True
    """
    cmd = plugin.get_plugin("becommands", command_name.replace("-", "_"))
    if cmd is None:
        raise UnknownCommand(command_name)
    return cmd


def execute(cmd, args, manipulate_encodings=True, restrict_file_access=False):
    enc = encoding.get_encoding()
    cmd = get_command(cmd)
    ret = cmd.execute([a.decode(enc) for a in args],
                      manipulate_encodings=manipulate_encodings,
                      restrict_file_access=restrict_file_access)
    if ret == None:
        ret = 0
    return ret

def help(cmd=None, parser=None):
    if cmd != None:
        return get_command(cmd).help()
    else:
        cmdlist = []
        for name, module in iter_commands():
            cmdlist.append((name, module.__desc__))
        longest_cmd_len = max([len(name) for name,desc in cmdlist])
        ret = ["Bugs Everywhere - Distributed bug tracking",
               "", "Supported commands"]
        for name, desc in cmdlist:
            numExtraSpaces = longest_cmd_len-len(name)
            ret.append("be %s%*s    %s" % (name, numExtraSpaces, "", desc))
        ret.extend(["", "Run", "  be help [command]", "for more information."])
        longhelp = "\n".join(ret)
        if parser == None:
            return longhelp
        return parser.help_str() + "\n" + longhelp

def completions(cmd):
    parser = get_command(cmd).get_parser()
    longopts = []
    for opt in parser.option_list:
        longopts.append(opt.get_opt_string())
    return longopts

def raise_get_help(option, opt, value, parser):
    raise GetHelp

def raise_get_completions(option, opt, value, parser):
    print "got completion arg"
    if hasattr(parser, "command") and parser.command == "be":
        comps = []
        for command, module in iter_commands():
            comps.append(command)
        for opt in parser.option_list:
            comps.append(opt.get_opt_string())
        raise GetCompletions(comps)
    raise GetCompletions(completions(sys.argv[1]))

class CmdOptionParser(optparse.OptionParser):
    def __init__(self, usage):
        optparse.OptionParser.__init__(self, usage)
        self.disable_interspersed_args()
        self.remove_option("-h")
        self.add_option("-h", "--help", action="callback", 
                        callback=raise_get_help, help="Print a help message")
        self.add_option("--complete", action="callback",
                        callback=raise_get_completions,
                        help="Print a list of available completions")

    def error(self, message):
        raise UsageError(message)

    def iter_options(self):
        return iter_combine([self._short_opt.iterkeys(), 
                            self._long_opt.iterkeys()])

    def help_str(self):
        f = StringIO()
        self.print_help(f)
        return f.getvalue()

def option_value_pairs(options, parser):
    """
    Iterate through OptionParser (option, value) pairs.
    """
    for option in [o.dest for o in parser.option_list if o.dest != None]:
        value = getattr(options, option)
        yield (option, value)

def default_complete(options, args, parser, bugid_args={}):
    """
    A dud complete implementation for becommands so that the
    --complete argument doesn't cause any problems.  Use this
    until you've set up a command-specific complete function.
    
    bugid_args is an optional dict where the keys are positional
    arguments taking bug shortnames and the values are functions for
    filtering, since that's a common enough operation.
    e.g. for "be open [options] BUGID"
      bugid_args = {0: lambda bug : bug.active == False}
    A positional argument of -1 specifies all remaining arguments
    (e.g in the case of "be show BUGID BUGID ...").
    """
    for option,value in option_value_pairs(options, parser):
        if value == "--complete":
            raise GetCompletions()
    if len(bugid_args.keys()) > 0:
        max_pos_arg = max(bugid_args.keys())
    else:
        max_pos_arg = -1
    for pos,value in enumerate(args):
        if value == "--complete":
            filter = None
            if pos in bugid_args:
                filter = bugid_args[pos]
            if pos > max_pos_arg and -1 in bugid_args:
                filter = bugid_args[-1]
            if filter != None:
                bugshortnames = []
                try:
                    bd = bugdir.BugDir(from_disk=True,
                                       manipulate_encodings=False)
                    bd.load_all_bugs()
                    bugs = [bug for bug in bd if filter(bug) == True]
                    bugshortnames = [bd.bug_shortname(bug) for bug in bugs]
                except bugdir.NoBugDir:
                    pass
                raise GetCompletions(bugshortnames)
            raise GetCompletions()

def complete_path(path):
    """List possible path completions for path."""
    comps = glob.glob(path+"*") + glob.glob(path+"/*")
    if len(comps) == 1 and os.path.isdir(comps[0]):
        comps.extend(glob.glob(comps[0]+"/*"))
    return comps

def underlined(instring):
    """Produces a version of a string that is underlined with '='

    >>> underlined("Underlined String")
    'Underlined String\\n================='
    """
    
    return "%s\n%s" % (instring, "="*len(instring))

def restrict_file_access(bugdir, path):
    """
    Check that the file at path is inside bugdir.root.  This is
    important if you allow other users to execute becommands with your
    username (e.g. if you're running be-handle-mail through your
    ~/.procmailrc).  If this check wasn't made, a user could e.g.
    run
      be commit -b ~/.ssh/id_rsa "Hack to expose ssh key"
    which would expose your ssh key to anyone who could read the VCS
    log.
    """
    in_root = bugdir.vcs.path_in_root(path, bugdir.root)
    if in_root == False:
        raise UserError('file access restricted!\n  %s not in %s'
                        % (path, bugdir.root))

def parse_id(id):
    """
    Return (bug_id, comment_id) tuple.
    Basically inverts Comment.comment_shortnames()
    >>> parse_id('XYZ')
    ('XYZ', None)
    >>> parse_id('XYZ:123')
    ('XYZ', ':123')
    >>> parse_id('')
    Traceback (most recent call last):
      ...
    UserError: invalid id ''.
    >>> parse_id('::')
    Traceback (most recent call last):
      ...
    UserError: invalid id '::'.
    """
    if len(id) == 0:
        raise UserError("invalid id '%s'." % id)
    if id.count(':') > 1:
        raise UserError("invalid id '%s'." % id)
    elif id.count(':') == 1:
        # Split shortname generated by Comment.comment_shortnames()
        bug_id,comment_id = id.split(':')
        comment_id = ':'+comment_id
    else:
        bug_id = id
        comment_id = None
    return (bug_id, comment_id)

def bug_from_id(bdir, id):
    """
    Exception translation for the command-line interface.
    id can be either the bug shortname or the full uuid.
    """
    try:
        bug = bdir.bug_from_shortname(id)
    except (bugdir.MultipleBugMatches, bugdir.NoBugMatches), e:
        raise UserError(e.message)
    return bug

def bug_comment_from_id(bdir, id):
    """
    Return (bug,comment) tuple matching shortname.  id can be either
    the bug/comment shortname or the full uuid.  If there is no
    comment part to the id, the returned comment is the bug's
    .comment_root.
    """
    bug_id,comment_id = parse_id(id)
    try:
        bug = bdir.bug_from_shortname(bug_id)
    except (bugdir.MultipleBugMatches, bugdir.NoBugMatches), e:
        raise UserError(e.message)
    if comment_id == None:
        comm = bug.comment_root
    else:
        #bug.load_comments(load_full=False)
        try:
            comm = bug.comment_root.comment_from_shortname(comment_id)
        except comment.InvalidShortname, e:
            raise UserError(e.message)
    return (bug, comm)

suite = doctest.DocTestSuite()
