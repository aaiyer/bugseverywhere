def unique_name(bug, bugs):
    return bug.name

class UserError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

def get_bug(spec, bug_dir):
    bugs = list(bug_dir.list())
    for bug in bugs:
        if bug.uuid == spec:
            return bug
    matches = []
    for bug in bugs:
        if bug.name == spec:
            matches.append(bug)
    if len(matches) > 1:
        raise UserError("More than one bug has the name %s.  Please use the"
                        " uuid." % spec)
    if len(matches) == 0:
        raise UserError("No bug has the name %s" % spec)
    return matches[0]
