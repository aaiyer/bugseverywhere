# Copyright

import optparse
import sys

import libbe
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
            assert self.callback != None
            return
        assert self.callback == None, self.callback
        assert self.arg.name == self.name, \
            'Name missmatch: %s != %s' % (self.arg.name, self.name)
        assert self.arg.optional == False
        assert self.arg.repeatable == False

    def __str__(self):
        return '--%s' % self.name

    def __repr__(self):
        return '<Option %s>' % self.__str__()

class _DummyParser (object):
    def __init__(self, options):
        self.option_list = options
        self.option_groups = []
        for option in self.option_list: # add required methods and attributes
            option.dest = option.name
            option._short_opts = []
            if option.short_name != None:
                option._short_opts.append('-' + option.short_name)
            option._long_opts = ['--' + option.name]
            option.takes_value = lambda : option.arg != None
            if option.takes_value():
                option.metavar = option.arg.metavar
            else:
                option.metavar = None

class OptionFormatter (optparse.IndentedHelpFormatter):
    def __init__(self, options):
        optparse.IndentedHelpFormatter.__init__(self)
        self.options = options
    def option_help(self):
        # based on optparse.OptionParser.format_option_help()
        parser = _DummyParser(self.options)
        self.store_option_strings(parser)
        ret = []
        ret.append(self.format_heading('Options'))
        self.indent()
        for option in self.options:
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
      -h HELP, --help=HELP  Print a help message.
    <BLANKLINE>
      --complete=STRING     Print a list of possible completions.
    <BLANKLINE>
     A detailed help message.
    """

    name = 'command'

    def __init__(self, input_encoding=None, output_encoding=None):
        self.status = None
        self.result = None
        self.requires_bugdir = False
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

    def run(self, bugdir, options=None, args=None):
        if options == None:
            options = {}
        if args == None:
            args = []
        params = {}
        for option in self.options:
            if option.name in options:
                params[option.name] = options.pop(option.name)
            elif option.arg != None:
                params[option.name] = option.arg.default
            else: # non-arg options are flags, set to default flag value
                params[option.name] = False
        if len(options) > 0:
            raise UserError, 'Invalid options passed to command %s:\n  %s' \
                % (self.name, '\n  '.join(['%s: %s' % (k,v)
                                           for k,v in options.items()]))
        for arg in self.args:
            pass
        if params['help'] == True:
            pass
        else:
            params.pop('help')
        if params['complete'] != None:
            pass
        else:
            params.pop('complete')
        self._setup_io(self.input_encoding, self.output_encoding)
        self.status = self._run(bugdir, **params)
        return self.status

    def _run(self, bugdir, **kwargs):
        pass

    def _setup_io(self, input_encoding=None, output_encoding=None):
        if input_encoding == None:
            input_encoding = libbe.util.get_input_encoding()
        if output_encoding == None:
            output_encoding = libbe.util.get_output_encoding()
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
        o = OptionFormatter(self.options)
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
