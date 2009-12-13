# Copyright

import glob
import os.path

import libbe
import libbe.command

class Completer (object):
    def __init__(self, options):
        self.options = options
    def __call__(self, bugdir, fragment=None):
        return [fragment]

def complete_command(command, argument, fragment=None):
    """
    List possible command completions for fragment.

    command argument is not used.
    """
    return list(libbe.command.commands())

def complete_path(command, argument, fragment=None):
    """
    List possible path completions for fragment.

    command argument is not used.
    """
    if fragment == None:
        fragment = '.'
    comps = glob.glob(fragment+'*') + glob.glob(fragment+'/*')
    if len(comps) == 1 and os.path.isdir(comps[0]):
        comps.extend(glob.glob(comps[0]+'/*'))
    return comps
    
def complete_status(command, argument, fragment=None):
    return [fragment]
def complete_severity(command, argument, fragment=None):
    return [fragment]
def complete_assigned(command, argument, fragment=None):
    return [fragment]
def complete_extra_strings(command, argument, fragment=None):
    return [fragment]

def select_values(string, possible_values, name="unkown"):
    """
    This function allows the user to select values from a list of
    possible values.  The default is to select all the values:

    >>> select_values(None, ['abc', 'def', 'hij'])
    ['abc', 'def', 'hij']

    The user selects values with a comma-separated limit_string.
    Prepending a minus sign to such a list denotes blacklist mode:

    >>> select_values('-abc,hij', ['abc', 'def', 'hij'])
    ['def']

    Without the leading -, the selection is in whitelist mode:

    >>> select_values('abc,hij', ['abc', 'def', 'hij'])
    ['abc', 'hij']

    In either case, appropriate errors are raised if on of the
    user-values is not in the list of possible values.  The name
    parameter lets you make the error message more clear:

    >>> select_values('-xyz,hij', ['abc', 'def', 'hij'], name="foobar")
    Traceback (most recent call last):
      ...
    UserError: Invalid foobar xyz
      ['abc', 'def', 'hij']
    >>> select_values('xyz,hij', ['abc', 'def', 'hij'], name="foobar")
    Traceback (most recent call last):
      ...
    UserError: Invalid foobar xyz
      ['abc', 'def', 'hij']
    """
    possible_values = list(possible_values) # don't alter the original
    if string == None:
        pass
    elif string.startswith('-'):
        blacklisted_values = set(string[1:].split(','))
        for value in blacklisted_values:
            if value not in possible_values:
                raise UserError('Invalid %s %s\n  %s'
                                % (name, value, possible_values))
            possible_values.remove(value)
    else:
        whitelisted_values = string.split(',')
        for value in whitelisted_values:
            if value not in possible_values:
                raise UserError('Invalid %s %s\n  %s'
                                % (name, value, possible_values))
        possible_values = whitelisted_values
    return possible_values
