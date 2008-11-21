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
import optparse
import os
import locale
from textwrap import TextWrapper
from StringIO import StringIO
import doctest

import bugdir
import plugin
import utility

class UserError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class UserErrorWrap(UserError):
    def __init__(self, exception):
        UserError.__init__(self, str(exception))
        self.exception = exception

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


def _test():
    import doctest
    import sys
    doctest.testmod()

if __name__ == "__main__":
    _test()

suite = doctest.DocTestSuite()
