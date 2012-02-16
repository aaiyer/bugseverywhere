# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

import libbe
import libbe.command
import libbe.command.util

TOPICS = {}

class Help (libbe.command.Command):
    """Print help for given command or topic

    >>> import sys
    >>> import libbe.bugdir
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> cmd = Help()

    >>> ret = ui.run(cmd, args=['help'])
    usage: be help [options] [TOPIC]
    <BLANKLINE>
    Options:
      -h, --help  Print a help message.
    <BLANKLINE>
      --complete  Print a list of possible completions.
    <BLANKLINE>
    <BLANKLINE>
    Print help for specified command/topic or list of all commands.
    """
    name = 'help'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.args.extend([
                libbe.command.Argument(
                    name='topic', metavar='TOPIC', default=None,
                    optional=True,
                    completion_callback=self.complete_topic)
                ])

    def _run(self, **params):
        if params['topic'] == None:
            if hasattr(self.ui, 'help'):
                print >> self.stdout, self.ui.help().rstrip('\n')
        elif params['topic'] in libbe.command.commands():
            module = libbe.command.get_command(params['topic'])
            Class = libbe.command.get_command_class(module,params['topic'])
            c = Class(ui=self.ui)
            self.ui.setup_command(c)
            print >> self.stdout, c.help().rstrip('\n')
        elif params['topic'] in TOPICS:
            print >> self.stdout, TOPICS[params['topic']].rstrip('\n')
        else:
            raise libbe.command.UserError(
                '"%s" is neither a command nor topic' % params['topic'])
        return 0

    def _long_help(self):
        return """
Print help for specified command/topic or list of all commands.
"""

    def complete_topic(self, command, argument, fragment=None):
        commands = libbe.command.util.complete_command()
        topics = sorted(TOPICS.keys())
        return commands + topics
