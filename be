#!/usr/bin/env python
"""Bugs Everywhere - Distributed bug tracking

be list: list bugs
be status: view or set the status of a bug
be comment: append a comment to a bug
be set-root: assign the root directory for bug tracking
"""
from libbe.cmdutil import *
from libbe.bugdir import tree_root
import sys
import os

def list_bugs(args):
    bugs = list(tree_root(os.getcwd()).list())
    if len(bugs) == 0:
        print "No bugs found"
    for bug in bugs:
        print "%s: %s" % (unique_name(bug, bugs), bug.summary)

    

if len(sys.argv) == 1:
    print __doc__
else:
    try:
        try:
            cmd = {
                "list": list_bugs
            }[sys.argv[1]]
        except KeyError, e:
            raise UserError("Unknown command \"%s\"" % e.args[0])
        cmd(sys.argv[2:])
    except UserError, e:
        print e
        sys.exit(1)
