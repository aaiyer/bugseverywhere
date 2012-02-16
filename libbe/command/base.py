# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Phil Schumm <philschumm@gmail.com>
#                         Robert Lehmann <mail@robertlehmann.de>
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

import codecs
import optparse
import os.path
import StringIO
import sys

import libbe
import libbe.storage
import libbe.ui.util.user
import libbe.util.encoding
import libbe.util.plugin


class UserError (Exception):
    "An error due to improper BE usage."
    pass


class UsageError (UserError):
    """A serious parsing error due to invalid BE command construction.

    The distinction between `UserError`\s and the more specific
    `UsageError`\s is that when displaying a `UsageError` to the user,
    the user is pointed towards the command usage information.  Use
    the more general `UserError` if you feel that usage information
    would not be particularly enlightening.
    """
    def __init__(self, command=None, command_name=None, message=None):
        super(UsageError, self).__init__(message)
        self.command = command
        if command_name is None and command is not None:
            command_name = command.name
        self.command_name = command_name
        self.message = message


class UnknownCommand (UsageError):
    def __init__(self, command_name, message=None):
        uc_message = "Unknown command '%s'" % command_name
        if message is None:
            message = uc_message
        else:
            message = '%s\n(%s)' % (uc_message, message)
        super(UnknownCommand, self).__init__(
            command_name=command_name,
            message=message)


def get_command(command_name):
    """Retrieves the module for a user command

    >>> try:
    ...     get_command('asdf')
    ... except UnknownCommand, e:
    ...     print e
    Unknown command 'asdf'
    (No module named asdf)
    >>> repr(get_command('list')).startswith("<module 'libbe.command.list' from ")
    True
    """
    try:
        cmd = libbe.util.plugin.import_by_name(
            'libbe.command.%s' % command_name.replace("-", "_"))
    except ImportError, e:
        raise UnknownCommand(command_name, message=unicode(e))
    return cmd

def get_command_class(module=None, command_name=None):
    """Retrieves a command class from a module.

    >>> import_xml_mod = get_command('import-xml')
    >>> import_xml = get_command_class(import_xml_mod, 'import-xml')
    >>> repr(import_xml)
    "<class 'libbe.command.import_xml.Import_XML'>"
    >>> import_xml = get_command_class(command_name='import-xml')
    >>> repr(import_xml)
    "<class 'libbe.command.import_xml.Import_XML'>"
    """
    if module == None:
        module = get_command(command_name)
    try:
        cname = command_name.capitalize().replace('-', '_')
        cmd = getattr(module, cname)
    except ImportError, e:
        raise UnknownCommand(command_name)
    return cmd

def modname_to_command_name(modname):
    """Little hack to replicate
    >>> import sys
    >>> def real_modname_to_command_name(modname):
    ...     mod = libbe.util.plugin.import_by_name(
    ...         'libbe.command.%s' % modname)
    ...     attrs = [getattr(mod, name) for name in dir(mod)]
    ...     commands = []
    ...     for attr_name in dir(mod):
    ...         attr = getattr(mod, attr_name)
    ...         try:
    ...             if issubclass(attr, Command):
    ...                 commands.append(attr)
    ...         except TypeError, e:
    ...             pass
    ...     if len(commands) == 0:
    ...         raise Exception('No Command classes in %s' % dir(mod))
    ...     return commands[0].name
    >>> real_modname_to_command_name('new')
    'new'
    >>> real_modname_to_command_name('import_xml')
    'import-xml'
    """
    return modname.replace('_', '-')

def commands(command_names=False):
    for modname in libbe.util.plugin.modnames('libbe.command'):
        if modname not in ['base', 'util']:
            if command_names == False:
                yield modname
            else:
                yield modname_to_command_name(modname)

class CommandInput (object):
    def __init__(self, name, help=''):
        self.name = name
        self.help = help

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, self.name)

    def __repr__(self):
        return self.__str__()

class Argument (CommandInput):
    def __init__(self, metavar=None, default=None, type='string',
                 optional=False, repeatable=False,
                 completion_callback=None, *args, **kwargs):
        CommandInput.__init__(self, *args, **kwargs)
        self.metavar = metavar
        self.default = default
        self.type = type
        self.optional = optional
        self.repeatable = repeatable
        self.completion_callback = completion_callback
        if self.metavar == None:
            self.metavar = self.name.upper()

class Option (CommandInput):
    def __init__(self, callback=None, short_name=None, arg=None,
                 *args, **kwargs):
        CommandInput.__init__(self, *args, **kwargs)
        self.callback = callback
        self.short_name = short_name
        self.arg = arg
        if self.arg == None and self.callback == None:
            # use an implicit boolean argument
            self.arg = Argument(name=self.name, help=self.help,
                                default=False, type='bool')
        self.validate()

    def validate(self):
        if self.arg == None:
            assert self.callback != None, self.name
            return
        assert self.callback == None, '%s: %s' (self.name, self.callback)
        assert self.arg.name == self.name, \
            'Name missmatch: %s != %s' % (self.arg.name, self.name)
        assert self.arg.optional == False, self.name
        assert self.arg.repeatable == False, self.name

    def __str__(self):
        return '--%s' % self.name

    def __repr__(self):
        return '<Option %s>' % self.__str__()

class _DummyParser (optparse.OptionParser):
    def __init__(self, command):
        optparse.OptionParser.__init__(self)
        self.remove_option('-h')
        self.command = command
        self._command_opts = []
        for option in self.command.options:
            self._add_option(option)

    def _add_option(self, option):
        # from libbe.ui.command_line.CmdOptionParser._add_option
        option.validate()
        long_opt = '--%s' % option.name
        if option.short_name != None:
            short_opt = '-%s' % option.short_name
        assert '_' not in option.name, \
            'Non-reconstructable option name %s' % option.name
        kwargs = {'dest':option.name.replace('-', '_'),
                  'help':option.help}
        if option.arg == None or option.arg.type == 'bool':
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
        #option.takes_value = lambda : option.arg != None
        opt._option = option
        self._command_opts.append(opt)
        self.add_option(opt)

class OptionFormatter (optparse.IndentedHelpFormatter):
    def __init__(self, command):
        optparse.IndentedHelpFormatter.__init__(self)
        self.command = command
    def option_help(self):
        # based on optparse.OptionParser.format_option_help()
        parser = _DummyParser(self.command)
        self.store_option_strings(parser)
        ret = []
        ret.append(self.format_heading('Options'))
        self.indent()
        for option in parser._command_opts:
            ret.append(self.format_option(option))
            ret.append('\n')
        self.dedent()
        # Drop the last '\n', or the header if no options or option groups:
        return ''.join(ret[:-1])

class Command (object):
    """One-line command description here.

    >>> c = Command()
    >>> print c.help()
    usage: be command [options]
    <BLANKLINE>
    Options:
      -h, --help  Print a help message.
    <BLANKLINE>
      --complete  Print a list of possible completions.
    <BLANKLINE>
    A detailed help message.
    """

    name = 'command'

    def __init__(self, ui=None):
        self.ui = ui # calling user-interface
        self.status = None
        self.result = None
        self.restrict_file_access = True
        self.options = [
            Option(name='help', short_name='h',
                help='Print a help message.',
                callback=self.help),
            Option(name='complete',
                help='Print a list of possible completions.',
                callback=self.complete),
                ]
        self.args = []

    def run(self, options=None, args=None):
        self.status = 1 # in case we raise an exception
        params = self._parse_options_args(options, args)
        if params['help'] == True:
            pass
        else:
            params.pop('help')
        if params['complete'] != None:
            pass
        else:
            params.pop('complete')

        self.status = self._run(**params)
        return self.status

    def _parse_options_args(self, options=None, args=None):
        if options == None:
            options = {}
        if args == None:
            args = []
        params = {}
        for option in self.options:
            assert option.name not in params, params[option.name]
            if option.name in options:
                params[option.name] = options.pop(option.name)
            elif option.arg != None:
                params[option.name] = option.arg.default
            else: # non-arg options are flags, set to default flag value
                params[option.name] = False
        assert 'user-id' not in params, params['user-id']
        if 'user-id' in options:
            self._user_id = options.pop('user-id')
        if len(options) > 0:
            raise UserError, 'Invalid option passed to command %s:\n  %s' \
                % (self.name, '\n  '.join(['%s: %s' % (k,v)
                                           for k,v in options.items()]))
        in_optional_args = False
        for i,arg in enumerate(self.args):
            if arg.repeatable == True:
                assert i == len(self.args)-1, arg.name
            if in_optional_args == True:
                assert arg.optional == True, arg.name
            else:
                in_optional_args = arg.optional
            if i < len(args):
                if arg.repeatable == True:
                    params[arg.name] = [args[i]]
                else:
                    params[arg.name] = args[i]
            else:  # no value given
                assert in_optional_args == True, arg.name
                params[arg.name] = arg.default
        if len(args) > len(self.args):  # add some additional repeats
            assert self.args[-1].repeatable == True, self.args[-1].name
            params[self.args[-1].name].extend(args[len(self.args):])
        return params

    def _run(self, **kwargs):
        raise NotImplementedError

    def help(self, *args):
        return '\n\n'.join([self.usage(),
                            self._option_help(),
                            self._long_help().rstrip('\n')])

    def usage(self):
        usage = 'usage: be %s [options]' % self.name
        num_optional = 0
        for arg in self.args:
            usage += ' '
            if arg.optional == True:
                usage += '['
                num_optional += 1
            usage += arg.metavar
            if arg.repeatable == True:
                usage += ' ...'
        usage += ']'*num_optional
        return usage

    def _option_help(self):
        o = OptionFormatter(self)
        return o.option_help().strip('\n')

    def _long_help(self):
        return "A detailed help message."

    def complete(self, argument=None, fragment=None):
        if argument == None:
            ret = ['--%s' % o.name for o in self.options
                    if o.name != 'complete']
            if len(self.args) > 0 and self.args[0].completion_callback != None:
                ret.extend(self.args[0].completion_callback(self, argument, fragment))
            return ret
        elif argument.completion_callback != None:
            # finish a particular argument
            return argument.completion_callback(self, argument, fragment)
        return [] # the particular argument doesn't supply completion info

    def _check_restricted_access(self, storage, path):
        """
        Check that the file at path is inside bugdir.root.  This is
        important if you allow other users to execute becommands with
        your username (e.g. if you're running be-handle-mail through
        your ~/.procmailrc).  If this check wasn't made, a user could
        e.g.  run
          be commit -b ~/.ssh/id_rsa "Hack to expose ssh key"
        which would expose your ssh key to anyone who could read the
        VCS log.

        >>> class DummyStorage (object): pass
        >>> s = DummyStorage()
        >>> s.repo = os.path.expanduser('~/x/')
        >>> c = Command()
        >>> try:
        ...     c._check_restricted_access(s, os.path.expanduser('~/.ssh/id_rsa'))
        ... except UserError, e:
        ...     assert str(e).startswith('file access restricted!'), str(e)
        ...     print 'we got the expected error'
        we got the expected error
        >>> c._check_restricted_access(s, os.path.expanduser('~/x'))
        >>> c._check_restricted_access(s, os.path.expanduser('~/x/y'))
        >>> c.restrict_file_access = False
        >>> c._check_restricted_access(s, os.path.expanduser('~/.ssh/id_rsa'))
        """
        if self.restrict_file_access == True:
            path = os.path.abspath(path)
            repo = os.path.abspath(storage.repo).rstrip(os.path.sep)
            if path == repo or path.startswith(repo+os.path.sep):
                return
            raise UserError('file access restricted!\n  %s not in %s'
                            % (path, repo))

    def cleanup(self):
        pass

class InputOutput (object):
    def __init__(self, stdin=None, stdout=None):
        self.stdin = stdin
        self.stdout = stdout

    def setup_command(self, command):
        if not hasattr(self.stdin, 'encoding'):
            self.stdin.encoding = libbe.util.encoding.get_input_encoding()
        if not hasattr(self.stdout, 'encoding'):
            self.stdout.encoding = libbe.util.encoding.get_output_encoding()
        command.stdin = self.stdin
        command.stdin.encoding = self.stdin.encoding
        command.stdout = self.stdout
        command.stdout.encoding = self.stdout.encoding

    def cleanup(self):
        pass

class StdInputOutput (InputOutput):
    def __init__(self, input_encoding=None, output_encoding=None):
        stdin,stdout = self._get_io(input_encoding, output_encoding)
        InputOutput.__init__(self, stdin, stdout)

    def _get_io(self, input_encoding=None, output_encoding=None):
        if input_encoding == None:
            input_encoding = libbe.util.encoding.get_input_encoding()
        if output_encoding == None:
            output_encoding = libbe.util.encoding.get_output_encoding()
        stdin = codecs.getreader(input_encoding)(sys.stdin)
        stdin.encoding = input_encoding
        stdout = codecs.getwriter(output_encoding)(sys.stdout)
        stdout.encoding = output_encoding
        return (stdin, stdout)

class StringInputOutput (InputOutput):
    """
    >>> s = StringInputOutput()
    >>> s.set_stdin('hello')
    >>> s.stdin.read()
    'hello'
    >>> s.stdin.read()
    ''
    >>> print >> s.stdout, 'goodbye'
    >>> s.get_stdout()
    'goodbye\\n'
    >>> s.get_stdout()
    ''

    Also works with unicode strings

    >>> s.set_stdin(u'hello')
    >>> s.stdin.read()
    u'hello'
    >>> print >> s.stdout, u'goodbye'
    >>> s.get_stdout()
    u'goodbye\\n'
    """
    def __init__(self):
        stdin = StringIO.StringIO()
        stdin.encoding = 'utf-8'
        stdout = StringIO.StringIO()
        stdout.encoding = 'utf-8'
        InputOutput.__init__(self, stdin, stdout)

    def set_stdin(self, stdin_string):
        self.stdin = StringIO.StringIO(stdin_string)

    def get_stdout(self):
        ret = self.stdout.getvalue()
        self.stdout = StringIO.StringIO() # clear stdout for next read
        self.stdin.encoding = 'utf-8'
        return ret

class UnconnectedStorageGetter (object):
    def __init__(self, location):
        self.location = location

    def __call__(self):
        return libbe.storage.get_storage(self.location)

class StorageCallbacks (object):
    def __init__(self, location=None):
        if location == None:
            location = '.'
        self.location = location
        self._get_unconnected_storage = UnconnectedStorageGetter(location)

    def setup_command(self, command):
        command._get_unconnected_storage = self.get_unconnected_storage
        command._get_storage = self.get_storage
        command._get_bugdir = self.get_bugdir

    def get_unconnected_storage(self):
        """
        Callback for use by commands that need it.
        
        The returned Storage instance is may actually be connected,
        but commands that make use of the returned value should only
        make use of non-connected Storage methods.  This is mainly
        intended for the init command, which calls Storage.init().
        """
        if not hasattr(self, '_unconnected_storage'):
            if self._get_unconnected_storage == None:
                raise NotImplementedError
            self._unconnected_storage = self._get_unconnected_storage()
        return self._unconnected_storage

    def set_unconnected_storage(self, unconnected_storage):
        self._unconnected_storage = unconnected_storage

    def get_storage(self):
        """Callback for use by commands that need it."""
        if not hasattr(self, '_storage'):
            self._storage = self.get_unconnected_storage()
            self._storage.connect()
            version = self._storage.storage_version()
            if version != libbe.storage.STORAGE_VERSION:
                raise libbe.storage.InvalidStorageVersion(version)
        return self._storage

    def set_storage(self, storage):
        self._storage = storage

    def get_bugdir(self):
        """Callback for use by commands that need it."""
        if not hasattr(self, '_bugdir'):
            self._bugdir = libbe.bugdir.BugDir(self.get_storage(),
                                               from_storage=True)
        return self._bugdir

    def set_bugdir(self, bugdir):
        self._bugdir = bugdir

    def cleanup(self):
        if hasattr(self, '_storage'):
            self._storage.disconnect()

class UserInterface (object):
    def __init__(self, io=None, location=None):
        if io == None:
            io = StringInputOutput()
        self.io = io
        self.storage_callbacks = StorageCallbacks(location)
        self.restrict_file_access = True

    def help(self):
        raise NotImplementedError

    def run(self, command, options=None, args=None):
        self.setup_command(command)
        return command.run(options, args)

    def setup_command(self, command):
        if command.ui == None:
            command.ui = self
        if self.io != None:
            self.io.setup_command(command)
        if self.storage_callbacks != None:
            self.storage_callbacks.setup_command(command)        
        command.restrict_file_access = self.restrict_file_access
        command._get_user_id = self._get_user_id

    def _get_user_id(self):
        """Callback for use by commands that need it."""
        if not hasattr(self, '_user_id'):
            self._user_id = libbe.ui.util.user.get_user_id(
                self.storage_callbacks.get_storage())
        return self._user_id

    def cleanup(self):
        self.storage_callbacks.cleanup()
        self.io.cleanup()
