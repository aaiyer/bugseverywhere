"""Show a particular bug"""
from libbe import bugdir, cmdutil
import os

def execute(args):
    bug_dir = cmdutil.bug_tree()
    if len(args) !=1:
        raise cmdutil.UserError("Please specify a bug id.")
    print cmdutil.bug_summary(cmdutil.get_bug(args[0], bug_dir), 
                              list(bug_dir.list()))
