"""Show or change a bug's severity level"""
from libbe import bugdir
from libbe import cmdutil 
__desc__ = __doc__

def execute(args):
    assert(len(args) in (0, 1, 2))
    if len(args) == 0:
        print help()
        return
    bug = cmdutil.get_bug(args[0])
    if len(args) == 1:
        print bug.severity
    elif len(args) == 2:
        try:
            bug.severity = args[1]
        except bugdir.InvalidValue, e:
            if e.name != "severity":
                raise
            raise cmdutil.UserError ("Invalid severity level: %s" % e.value)


def help():
    return """be severity bug-id [severity]

Show or change a bug's severity level.  

If no severity is specified, the current value is printed.  If a severity level
is specified, it will be assigned to the bug.

Severity levels are:
wishlist: A feature that could improve usefulness, but not a bug. 
   minor: The standard bug level.
 serious: A bug that requires workarounds.
critical: A bug that prevents some features from working at all.
   fatal: A bug that makes the package unusable.
"""
