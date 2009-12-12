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
        if modname != 'base':
            yield modname

class CommandInput (object):
    def __init__(self, name, help=''):
        self.name = name
        self.help = help

class Option (CommandInput):
    def __init__(self, option_callback=None, short_name=None, arg=None,
                 type=None, *args, **kwargs):
        CommandInput.__init__(self, *args, **kwargs)
        self.option_callback = option_callback
        self.short_name = short_name
        self.arg = arg
        self.type = type
        if self.arg != None:
            assert self.arg.name == self.name, \
                'Name missmatch: %s != %s' % (self.arg.name, self.name)

class Argument (CommandInput):
    def __init__(self, metavar=None, default=None, 
                 optional=False, repeatable=False,
                 completion_callback=None, *args, **kwargs):
        CommandInput.__init__(self, *args, **kwargs)
        self.metavar = metavar
        self.default = default
        self.optional = optional
        self.repeatable = repeatable
        self.completion_callback = completion_callback

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
    """
    >>> c = Command()
    >>> print c.help()
    usage: be command [options]
    <BLANKLINE>
    Options:
      -h HELP, --help=HELP  Print a help message
    <BLANKLINE>
      --complete=STRING     Print a list of possible completions
    <BLANKLINE>
      -r REPO, --repo=REPO  Select BE repository (see `be help repo`) rather
                            thanthe current directory.
    <BLANKLINE>
    A detailed help message.
    """

    name = 'command'

    def __init__(self, input_encoding=None, output_encoding=None):
        self.status = None
        self.result = None
        self.input_encoding = None
        self.output_encoding = None
        self.options = [
            Option(name='help', short_name='h',
                help='Print a help message',
                option_callback=self.help),
            Option(name='complete', type='string',
                help='Print a list of possible completions',
                arg=Argument(name='complete', metavar='STRING', optional=True)),
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
#        if cmd != None:
#            return get_command(cmd).help()
#        cmdlist = []
#        for name in commands():
#            module = get_command(name)
#            cmdlist.append((name, module.__desc__))
#        cmdlist.sort()
#        longest_cmd_len = max([len(name) for name,desc in cmdlist])
#        ret = ["Bugs Everywhere - Distributed bug tracking",
#               "", "Supported commands"]
#        for name, desc in cmdlist:
#            numExtraSpaces = longest_cmd_len-len(name)
#            ret.append("be %s%*s    %s" % (name, numExtraSpaces, "", desc))
#        ret.extend(["", "Run", "  be help [command]", "for more information."])
#        longhelp = "\n".join(ret)
#        if parser == None:
#            return longhelp
#        return parser.help_str() + "\n" + longhelp

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
