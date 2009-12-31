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
    bd = command._get_bugdir()
    import libbe.bug
    return libbe.bug.status_values

def complete_severity(command, argument, fragment=None):
    bd = command._get_bugdir()
    import libbe.bug
    return libbe.bug.severity_values

def complete_assigned(command, argument, fragment=None):
    if fragment == None:
        return []
    return [fragment]

def complete_extra_strings(command, argument, fragment=None):
    if fragment == None:
        return []
    return [fragment]

def complete_bug_id(command, argument, fragment=None):
    return complete_bug_comment_id(command, argument, fragment,
                                   comments=False)

def complete_bug_comment_id(command, argument, fragment=None,
                            active_only=True, comments=True):
    import libbe.bugdir
    import libbe.util.id
    bd = command._get_bugdir()
    if fragment == None or len(fragment) == 0:
        fragment = '/'
    try:
        p = libbe.util.id.parse_user(bd, fragment)
        matches = None
        root,residual = (fragment, None)
        if not root.endswith('/'):
            root += '/'
    except libbe.util.id.InvalidIDStructure, e:
        return []
    except libbe.util.id.NoIDMatches:
        return []
    except libbe.util.id.MultipleIDMatches, e:
        if e.common == None:
            # choose among bugdirs
            return e.matches
        common = e.common
        matches = e.matches
        root,residual = libbe.util.id.residual(common, fragment)
        p = libbe.util.id.parse_user(bd, e.common)
    bug = None
    if matches == None: # fragment was complete, get a list of children uuids
        if p['type'] == 'bugdir':
            matches = bd.uuids()
            common = bd.id.user()
        elif p['type'] == 'bug':
            if comments == False:
                return [fragment]
            bug = bd.bug_from_uuid(p['bug'])
            matches = bug.uuids()
            common = bug.id.user()
        else:
            assert p['type'] == 'comment', p
            return [fragment]
    if p['type'] == 'bugdir':
        child_fn = bd.bug_from_uuid
    elif p['type'] == 'bug':
        if comments == False:
            return[fragment]
        if bug == None:
            bug = bd.bug_from_uuid(p['bug'])
        child_fn = bug.comment_from_uuid
    elif p['type'] == 'comment':
        assert matches == None, matches
        return [fragment]
    possible = []
    common += '/'
    for m in matches:
        child = child_fn(m)
        id = child.id.user()
        possible.append(id.replace(common, root))
    return possible

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
                raise libbe.command.UserError('Invalid %s %s\n  %s'
                                % (name, value, possible_values))
            possible_values.remove(value)
    else:
        whitelisted_values = string.split(',')
        for value in whitelisted_values:
            if value not in possible_values:
                raise libbe.command.UserError(
                    'Invalid %s %s\n  %s'
                    % (name, value, possible_values))
        possible_values = whitelisted_values
    return possible_values

def bug_comment_from_user_id(bugdir, id):
    p = libbe.util.id.parse_user(bugdir, id)
    if not p['type'] in ['bug', 'comment']:
        raise libbe.command.UserError(
            '%s is a %s id, not a bug or comment id' % (id, p['type']))
    if p['bugdir'] != bugdir.uuid:
        raise libbe.command.UserError(
            "%s doesn't belong to this bugdir (%s)"
            % (id, bugdir.uuid))
    bug = bugdir.bug_from_uuid(p['bug'])
    if 'comment' in p:
        comment = bug.comment_from_uuid(p['comment'])
    else:
        comment = bug.comment_root
    return (bug, comment)
