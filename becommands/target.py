"""Show or change a bug's target for fixing"""
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
        if bug.target is None:
            print "No target assigned."
        else:
            print bug.target
    elif len(args) == 2:
        if args[1] == "none":
            bug.target = None
        else:
            bug.target = args[1]
        bug.save()


def help():
    return """be target bug-id [target]

Show or change a bug's target for fixing.  

If no target is specified, the current value is printed.  If a target 
is specified, it will be assigned to the bug.

Targets are freeform; any text may be specified.  They will generally be
milestone names or release numbers.

The value "none" can be used to unset the target.
"""
