from libbe import bugdir, cmdutil

def execute(args):
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a directory path")
    bugdir.create_bug_dir(args[0])
