import bugdir
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
        target = "  target: %s" % target
    return "ID: %s  Severity: %s%s  Creator: %s \n%s\n" % \
            (unique_name(bug, bugs), bug.severity, target, bug.creator,
             bug.summary)

