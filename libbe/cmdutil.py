# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
#                         W. Trevor King <wking@drexel.edu>
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
import optparse
import os
from textwrap import TextWrapper
from StringIO import StringIO
import sys
import doctest

import bugdir
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


def execute(cmd, args):
    enc = encoding.get_encoding()
    cmd = get_command(cmd)
    cmd.execute([a.decode(enc) for a in args])
    return 0

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
            raise cmdutil.GetCompletions()
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

def underlined(instring):
    """Produces a version of a string that is underlined with '='

    >>> underlined("Underlined String")
    'Underlined String\\n================='
    """
    
    return "%s\n%s" % (instring, "="*len(instring))


def _test():
    import doctest
    import sys
    doctest.testmod()

if __name__ == "__main__":
    _test()

suite = doctest.DocTestSuite()
