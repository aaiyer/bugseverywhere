"""Add a comment to a bug"""
from libbe import bugdir, cmdutil, names
import os
def execute(args):
    options, args = get_parser().parse_args(args)
    if len(args) < 2:
        raise cmdutil.UsageError()
    bug = cmdutil.get_bug(args[0])
    comment = bugdir.new_comment(bug, args[1])
    comment.save()


def get_parser():
    parser = cmdutil.CmdOptionParser("be comment BUG-ID COMMENT")
    return parser

longhelp="""
Add a comment to a bug.
"""

def help():
    return get_parser().help_str() + longhelp
