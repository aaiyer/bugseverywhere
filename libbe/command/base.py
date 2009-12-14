# Copyright

import codecs
import optparse
import os.path
import sys

import libbe
import libbe.ui.util.user
import libbe.util.encoding
import libbe.util.plugin

class UserError(Exception):
    pass

class UnknownCommand(UserError):
    def __init__(self, cmd):
        Exception.__init__(self, "Unknown command '%s'" % cmd)
        self.cmd = cmd


def get_command(command_name):
    """Retrieves the module for a user command

    >>> try:
    ...     get_command('asdf')
    ... except UnknownCommand, e:
    ...     print e
    Unknown command 'asdf'
    >>> repr(get_command('list')).startswith("<module 'libbe.command.list' from ")
    True
    """
    try:
        cmd = libbe.util.plugin.import_by_name(
            'libbe.command.%s' % command_name.replace("-", "_"))
    except ImportError, e:
        raise UnknownCommand(command_name)
    return cmd

def get_command_class(module, command_name):
    """Retrieves a command class from a module.

    >>> import_xml_mod = get_command('import-xml')
    >>> import_xml = get_command_class(import_xml_mod, 'import-xml')
    >>> repr(import_xml)
    "<class 'libbe.command.import_xml.Import_XML'>"
    """
    try:
        cname = command_name.capitalize().replace('-', '_')
        cmd = getattr(module, cname)
    except ImportError, e:
        raise UnknownCommand(command_name)
    return cmd

def commands():
    for modname in libbe.util.plugin.modnames('libbe.command'):
        if modname not in ['base', 'util']:
            yield modname

class CommandInput (object):
    def __init__(self, name, help=''):
        self.name = name
        self.help = help

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
    """One-line command description.

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

    def __init__(self, input_encoding=None, output_encoding=None):
        self.status = None
        self.result = None
        self.requires_bugdir = False
        self.requires_storage = False
        self.requires_unconnected_storage = False
        self.restrict_file_access = True
        self.input_encoding = None
        self.output_encoding = None
        self.options = [
            Option(name='help', short_name='h',
                help='Print a help message.',
                callback=self.help),
            Option(name='complete',
                help='Print a list of possible completions.',
                callback=self.complete),
                ]
        self.args = []

    def run(self, storage=None, bugdir=None, options=None, args=None):
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
            params['user-id'] = options.pop('user-id')
        else:
            params['user-id'] = libbe.ui.util.user.get_user_id(storage)
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
                if arg.repeatable == True:
                    params[arg.name] = [arg.default]
                else:
                    params[arg.name] = arg.default
        if len(args) > len(self.args):  # add some additional repeats
            assert self.args[-1].repeatable == True, self.args[-1].name
            params[self.args[-1].name].extend(args[len(self.args):])

        if params['help'] == True:
            pass
        else:
            params.pop('help')
        if params['complete'] != None:
            pass
        else:
            params.pop('complete')

        self._setup_io(self.input_encoding, self.output_encoding)
        self.status = self._run(storage, bugdir, **params)
        return self.status

    def _run(self, storage, bugdir, **kwargs):
        pass

    def _setup_io(self, input_encoding=None, output_encoding=None):
        if input_encoding == None:
            input_encoding = libbe.util.encoding.get_input_encoding()
        if output_encoding == None:
            output_encoding = libbe.util.encoding.get_output_encoding()
        self.stdin = codecs.getwriter(input_encoding)(sys.stdin)
        self.stdin.encoding = input_encoding
        self.stdout = codecs.getwriter(output_encoding)(sys.stdout)
        self.stdout.encoding = output_encoding

    def help(self, *args):       
        return '\n\n'.join([self._usage(),
                            self._option_help(),
                            self._long_help()])

    def _usage(self):
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
            ret = ['--%s' % o.name for o in self.options]
            if len(self.args) > 0 and self.args[0].completion_callback != None:
                ret.extend(self.args[0].completion_callback(self, argument))
            return ret
        elif argument.completion_callback != None:
            # finish a particular argument
            return argument.completion_callback(self, argument, fragment)
        return [] # the particular argument doesn't supply completion info

    def check_restricted_access(self, storage, path):
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
        ...     c.check_restricted_access(s, os.path.expanduser('~/.ssh/id_rsa'))
        ... except UserError, e:
        ...     assert str(e).startswith('file access restricted!'), str(e)
        ...     print 'we got the expected error'
        we got the expected error
        >>> c.check_restricted_access(s, os.path.expanduser('~/x'))
        >>> c.check_restricted_access(s, os.path.expanduser('~/x/y'))
        >>> c.restrict_file_access = False
        >>> c.check_restricted_access(s, os.path.expanduser('~/.ssh/id_rsa'))
        """
        if self.restrict_file_access == True:
            path = os.path.abspath(path)
            repo = os.path.abspath(storage.repo).rstrip(os.path.sep)
            if path == repo or path.startswith(repo+os.path.sep):
                return
            raise UserError('file access restricted!\n  %s not in %s'
                            % (path, repo))
