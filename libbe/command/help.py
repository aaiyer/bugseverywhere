# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marien.zwart@gmail.com>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         W. Trevor King <wking@tremily.us>
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


TOPICS = {
    'repo': """A BE repository containing child bugdirs

BE repositories are stored in an abstract `Storage` instance, which
may or may not be versioned.  If you're using BE to track bugs in your
local software, you'll probably be using an on-disk storage based on
the VCS you use to version the storage.  See `be help init` for
details about automatic VCS-detection.

While most users will be using local storage, BE also supports remote
storage servers.  This allows projects to publish their local
repository in a way that's directly accessible to remote users.  The
remote users can then use a local BE client to interact with the
remote repository, without having to create a local copy of the
repository.  The remote server will be running something like:

    $ be serve-storage --host 123.123.123.123 --port 54321

And the local client can run:

    $ be --repo http://123.123.123.123:54321 list

or whichever command they like.        

Because the storage server serves repositories at the `Storage` level,
it can be inefficient.  For example, `be list` will have to transfer
the data for all the bugs in a repository over the wire.  The storage
server can also be harder to lock down, because users with write
access can potentially store data that cannot be parsed by BE.  For a
more efficient server, see `be serve-commands`.
""",
##
    'server': """A server for remote BE command execution

The usual way for a user to interact with a BE bug tracker for a
particular project is to clone the project repository.  They can then
use their local BE client to browse the repository and make changes,
before pushing their changes back upstream.  For the average user
seeking to file a bug or comment, this can be too much work.  One way
to simplify the process is to use a storage server (see `be help
repo`), but this is not always ideal.  A more robust approach is to
use a command server.

The remote server will be running something like:

    $ be serve-commands --host 123.123.123.123 --port 54321

And the local client can run:

    $ be --server http://123.123.123.123:54321 list

or whichever command they like.  The command line arguments are parsed
locally, and then POSTed to the command server, where the command is
executed.  The output of the command is returned to the client for
display.  This requires much less traffic over the wire than running
the same command via a storage server.
""",
        }


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
        elif params['topic'] in libbe.command.commands(command_names=True):
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
