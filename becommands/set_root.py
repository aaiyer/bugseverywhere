"""Assign the root directory for bug tracking"""
from libbe import bugdir, cmdutil, rcs

def execute(args):
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a directory path")
    dir_rcs = rcs.detect(args[0])
    if dir_rcs.name is not "None":
        print "Using %s for revision control." % dir_rcs.name
    else:
        print "No revision control detected."
    bugdir.create_bug_dir(args[0], dir_rcs)
    print "Directory initialized."
