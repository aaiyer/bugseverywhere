from libbe import bugdir, cmdutil, names
def execute(args):
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a summary message")
    dir = bugdir.tree_root(".")
    bugs = (dir.list())
    bug = dir.new_bug()
    bug.creator = names.creator()
    bug.severity = "minor"
    bug.status = "open"
    bug.summary = args[0]


