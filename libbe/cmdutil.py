import bugdir
import plugin
def unique_name(bug, bugs):
    chars = 1
    for some_bug in bugs:
        if bug.uuid == some_bug.uuid:
            continue
        while (bug.uuid[:chars] == some_bug.uuid[:chars]):
            chars+=1
    return bug.uuid[:chars]

class UserError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class UserErrorWrap(UserError):
    def __init__(self, exception):
        UserError.__init__(self, str(exception))
        self.exception = exception

def get_bug(spec, bug_dir=None):
    matches = []
    try:
        if bug_dir is None:
            bug_dir = bugdir.tree_root('.')
    except bugdir.NoBugDir, e:
        raise UserErrorWrap(e)
    bugs = list(bug_dir.list())
    for bug in bugs:
        if bug.uuid.startswith(spec):
            matches.append(bug)
    if len(matches) > 1:
        raise UserError("More than one bug matches %s.  Please be more"
                        " specific." % spec)
    if len(matches) == 1:
        return matches[0]
        
    matches = []
    if len(matches) == 0:
        raise UserError("No bug matches %s" % spec)
    return matches[0]

def bug_summary(bug, bugs):
    target = bug.target
    if target is None:
        target = ""
    else:
        target = "  Target: %s" % target
    if bug.assigned is None:
        assigned = ""
    else:
        assigned = "  Assigned: %s" % bug.assigned
    return "ID: %s  Severity: %s%s%s  Creator: %s \n%s\n" % \
            (unique_name(bug, bugs), bug.severity, assigned, target,
             bug.creator, bug.summary)

def iter_commands():
    for name, module in plugin.iter_plugins("becommands"):
        yield name.replace("_", "-"), module

def get_command(command_name):
    """Retrieves the module for a user command

    >>> get_command("asdf")
    Traceback (most recent call last):
    File "<stdin>", line 1, in ?
    File "/home/abentley/be/libbe/cmdutil.py", line 60, in get_command
      raise UserError("Unknown command %s" % command_name)
    UserError: Unknown command asdf
    >>> get_command("list")
    <module 'becommands.list' from '/home/abentley/be/becommands/list.pyc'>
    """
    cmd = plugin.get_plugin("becommands", command_name.replace("-", "_"))
    if cmd is None:
        raise UserError("Unknown command %s" % command_name)
    return cmd

def execute(cmd, args):
    return get_command(cmd).execute(args)

def help(cmd, args):
    return get_command(cmd).help()

def _test():
    import doctest
    import sys
    doctest.testmod()

if __name__ == "__main__":
    _test()
