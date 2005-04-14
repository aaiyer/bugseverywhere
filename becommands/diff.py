# This is the standard command template.  To use it, please fill in values for
# Short description, long help and COMMANDSPEC
#
"""Compare bug reports with older tree"""
from libbe import bugdir, diff, cmdutil
import os
def execute(args):
    options, args = get_parser().parse_args(args)
    if len(args) == 0:
        spec = None
    elif len(args) == 1:
        spec = args[0]
    else:
        raise cmdutil.UsageError
    tree = bugdir.tree_root(".")
    if tree.rcs_name == "None":
        print "This directory is not revision-controlled."
    else:
        diff.diff_report(diff.reference_diff(tree, spec), tree)


def get_parser():
    parser = cmdutil.CmdOptionParser("be diff [specifier]")
    return parser

longhelp="""
Uses the RCS to compare the current tree with a previous tree, and prints
a pretty report.  If specifier is given, it is a specifier for the particular
previous tree to use.  Specifiers are specific to their RCS.  

For Arch: a fully-qualified revision name
"""

def help():
    return get_parser().help_str() + longhelp
