# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
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

"""
A command line interface to Bugs Everywhere.
"""

import optparse
import os
import sys

import libbe
import libbe.bugdir
import libbe.command
import libbe.command.util
import libbe.version
import libbe.ui.util.pager
import libbe.util.encoding


if libbe.TESTING == True:
    import doctest

class CallbackExit (Exception):
    pass

class CmdOptionParser(optparse.OptionParser):
    def __init__(self, command):
        self.command = command
        optparse.OptionParser.__init__(self)
        self.remove_option('-h')
        self.disable_interspersed_args()
        self._option_by_name = {}
        for option in self.command.options:
            self._add_option(option)
        self.set_usage(command.usage())


    def _add_option(self, option):
        option.validate()
        self._option_by_name[option.name] = option
        long_opt = '--%s' % option.name
        if option.short_name != None:
            short_opt = '-%s' % option.short_name
        assert '_' not in option.name, \
            'Non-reconstructable option name %s' % option.name
        kwargs = {'dest':option.name.replace('-', '_'),
                  'help':option.help}
        if option.arg == None: # a callback option
            kwargs['action'] = 'callback'
            kwargs['callback'] = self.callback
        elif option.arg.type == 'bool':
            kwargs['action'] = 'store_true'
            kwargs['metavar'] = None
            kwargs['default'] = False
        else:
            kwargs['type'] = option.arg.type
            kwargs['action'] = 'store'
            kwargs['metavar'] = option.arg.metavar
            kwargs['default'] = option.arg.default
        if option.short_name != None:
            opt = optparse.Option(short_opt, long_opt, **kwargs)
        else:
            opt = optparse.Option(long_opt, **kwargs)
        opt._option = option
        self.add_option(opt)

    def parse_args(self, args=None, values=None):
        args = self._get_args(args)
        options,parsed_args = optparse.OptionParser.parse_args(
            self, args=args, values=values)
        options = options.__dict__
        for name,value in options.items():
            if '_' in name: # reconstruct original option name
                options[name.replace('_', '-')] = options.pop(name)
        for name,value in options.items():
            argument = None
            option = self._option_by_name[name]
            if option.arg != None:
                argument = option.arg
            if value == '--complete':
                fragment = None
                indices = [i for i,arg in enumerate(args)
                           if arg == '--complete']
                for i in indices:
                    assert i > 0  # this --complete is an option value
                    if args[i-1] in ['--%s' % o.name
                                     for o in self.command.options]:
                        name = args[i-1][2:]
                        if name == option.name:
                            break
                    elif option.short_name != None \
                            and args[i-1].startswith('-') \
                            and args[i-1].endswith(option.short_name):
                        break
                if i+1 < len(args):
                    fragment = args[i+1]
                self.complete(argument, fragment)
            elif argument is not None:
                value = self.process_raw_argument(argument=argument, value=value)
                options[name] = value
        for i,arg in enumerate(parsed_args):
            if i > 0 and self.command.name == 'be':
                break # let this pass through for the command parser to handle
            elif i < len(self.command.args):
                argument = self.command.args[i]
            elif len(self.command.args) == 0:
                break # command doesn't take arguments
            else:
                argument = self.command.args[-1]
                if argument.repeatable == False:
                    raise libbe.command.UserError('Too many arguments')
            if arg == '--complete':
                fragment = None
                if i < len(parsed_args) - 1:
                    fragment = parsed_args[i+1]
                self.complete(argument, fragment)
            else:
                value = self.process_raw_argument(argument=argument, value=arg)
                parsed_args[i] = value
        if (len(parsed_args) > len(self.command.args) and
            (len(self.command.args) == 0 or
             self.command.args[-1].repeatable == False)):
            raise libbe.command.UserError('Too many arguments')
        for arg in self.command.args[len(parsed_args):]:
            if arg.optional == False:
                raise libbe.command.UsageError(
                    command=self.command,
                    message='Missing required argument %s' % arg.metavar)
        return (options, parsed_args)

    def callback(self, option, opt, value, parser):
        command_option = option._option
        if command_option.name == 'complete':
            argument = None
            fragment = None
            if len(parser.rargs) > 0:
                fragment = parser.rargs[0]
            self.complete(argument, fragment)
        else:
            print >> self.command.stdout, command_option.callback(
                self.command, command_option, value)
        raise CallbackExit

    def complete(self, argument=None, fragment=None):
        comps = self.command.complete(argument, fragment)
        if fragment != None:
            comps = [c for c in comps if c.startswith(fragment)]
        if len(comps) > 0:
            print >> self.command.stdout, '\n'.join(comps)
        raise CallbackExit

    def process_raw_argument(self, argument, value):
        if value == argument.default:
            return value
        if argument.type == 'string':
            if not hasattr(self, 'argv_encoding'):
                self.argv_encoding = libbe.util.encoding.get_argv_encoding()
            return unicode(value, self.argv_encoding)
        return value


class BE (libbe.command.Command):
    """Class for parsing the command line arguments for `be`.
    This class does not contain a useful _run() method.  Call this
    module's main() function instead.

    >>> ui = libbe.command.UserInterface()
    >>> ui.io.stdout = sys.stdout
    >>> be = BE(ui=ui)
    >>> ui.io.setup_command(be)
    >>> p = CmdOptionParser(be)
    >>> p.exit_after_callback = False
    >>> try:
    ...     options,args = p.parse_args(['--help']) # doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
    ... except CallbackExit:
    ...     pass
    usage: be [options] [COMMAND [command-options] [COMMAND-ARGS ...]]
    <BLANKLINE>
    Options:
      -h, --help         Print a help message.
    <BLANKLINE>
      --complete         Print a list of possible completions.
    <BLANKLINE>
      --version          Print version string.
    ...
    >>> try:
    ...     options,args = p.parse_args(['--complete']) # doctest: +ELLIPSIS
    ... except CallbackExit:
    ...     print '  got callback'
    --help
    --version
    ...
    subscribe
    tag
    target
      got callback
    """
    name = 'be'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='version',
                    help='Print version string.',
                    callback=self.version),
                libbe.command.Option(name='full-version',
                    help='Print full version information.',
                    callback=self.full_version),
                libbe.command.Option(name='repo', short_name='r',
                    help='Select BE repository (see `be help repo`) rather '
                         'than the current directory.',
                    arg=libbe.command.Argument(
                        name='repo', metavar='REPO', default='.',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='paginate',
                    help='Pipe all output into less (or if set, $PAGER).'),
                libbe.command.Option(name='no-pager',
                    help='Do not pipe git output into a pager.'),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='command', optional=False,
                    completion_callback=libbe.command.util.complete_command),
                libbe.command.Argument(
                    name='args', optional=True, repeatable=True)
                ])

    def usage(self):
        return 'usage: be [options] [COMMAND [command-options] [COMMAND-ARGS ...]]'

    def _long_help(self):
        cmdlist = []
        for name in libbe.command.commands():
            Class = libbe.command.get_command_class(command_name=name)
            assert hasattr(Class, '__doc__') and Class.__doc__ != None, \
                'Command class %s missing docstring' % Class
            cmdlist.append((name, Class.__doc__.splitlines()[0]))
        cmdlist.sort()
        longest_cmd_len = max([len(name) for name,desc in cmdlist])
        ret = ['Bugs Everywhere - Distributed bug tracking',
               '', 'Supported commands']
        for name, desc in cmdlist:
            numExtraSpaces = longest_cmd_len-len(name)
            ret.append('be %s%*s    %s' % (name, numExtraSpaces, '', desc))
        ret.extend(['', 'Run', '  be help [command]', 'for more information.'])
        return '\n'.join(ret)

    def version(self, *args):
        return libbe.version.version(verbose=False)

    def full_version(self, *args):
        return libbe.version.version(verbose=True)

class CommandLine (libbe.command.UserInterface):
    def __init__(self, *args, **kwargs):
        libbe.command.UserInterface.__init__(self, *args, **kwargs)
        self.restrict_file_access = False
        self.storage_callbacks = None
    def help(self):
        be = BE(ui=self)
        self.setup_command(be)
        return be.help()

def dispatch(ui, command, args):
    parser = CmdOptionParser(command)
    try:
        options,args = parser.parse_args(args)
        ret = ui.run(command, options, args)
    except CallbackExit:
        return 0
    except UnicodeDecodeError, e:
        print >> ui.io.stdout, '\n'.join([
                'ERROR:', str(e),
                'You should set a locale that supports unicode, e.g.',
                '  export LANG=en_US.utf8',
                'See http://docs.python.org/library/locale.html for details',
                ])
        return 1
    except libbe.command.UsageError, e:
        print >> ui.io.stdout, 'Usage Error:\n', e
        if e.command:
            print >> ui.io.stdout, e.command.usage()
        print >> ui.io.stdout, 'For usage information, try'
        print >> ui.io.stdout, '  be help %s' % e.command_name
        return 1
    except libbe.command.UserError, e:
        print >> ui.io.stdout, 'ERROR:\n', e
        return 1
    except libbe.storage.ConnectionError, e:
        print >> ui.io.stdout, 'Connection Error:\n', e
        return 1
    except (libbe.util.id.MultipleIDMatches, libbe.util.id.NoIDMatches,
            libbe.util.id.InvalidIDStructure), e:
        print >> ui.io.stdout, 'Invalid id:\n', e
        return 1
    finally:
        command.cleanup()
    return ret

def main():
    io = libbe.command.StdInputOutput()
    ui = CommandLine(io)
    be = BE(ui=ui)
    ui.setup_command(be)

    parser = CmdOptionParser(be)
    try:
        options,args = parser.parse_args()
    except CallbackExit:
        return 0
    except libbe.command.UsageError, e:
        if isinstance(e.command, BE):
            # no command given, print usage string
            print >> ui.io.stdout, 'Usage Error:\n', e
            print >> ui.io.stdout, be.usage()
            print >> ui.io.stdout, 'For example, try'
            print >> ui.io.stdout, '  be help'
        else:
            print >> ui.io.stdout, 'Usage Error:\n', e
            if e.command:
                print >> ui.io.stdout, e.command.usage()
            print >> ui.io.stdout, 'For usage information, try'
            print >> ui.io.stdout, '  be help %s' % e.command_name
        return 1

    command_name = args.pop(0)
    try:
        Class = libbe.command.get_command_class(command_name=command_name)
    except libbe.command.UnknownCommand, e:
        print >> ui.io.stdout, e
        return 1

    ui.storage_callbacks = libbe.command.StorageCallbacks(options['repo'])
    command = Class(ui=ui)
    ui.setup_command(command)

    if command.name in ['comment', 'commit', 'import-xml', 'serve']:
        paginate = 'never'
    else:
        paginate = 'auto'
    if options['paginate'] == True:
        paginate = 'always'
    if options['no-pager'] == True:
        paginate = 'never'
    libbe.ui.util.pager.run_pager(paginate)

    ret = dispatch(ui, command, args)
    ui.cleanup()
    return ret

if __name__ == '__main__':
    sys.exit(main())
