"""Create a new bug"""
from libbe import bugdir, cmdutil, names, utility
def execute(args):
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a summary message")
    dir = cmdutil.bug_tree()
    bug = bugdir.new_bug(dir)
    bug.summary = args[0]
    bug.save()
    bugs = (dir.list())
    print "Created bug with ID %s" % cmdutil.unique_name(bug, bugs)

