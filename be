#!/usr/bin/env python
"""Bugs Everywhere - Distributed bug tracking

be list: list bugs
be status: view or set the status of a bug
be comment: append a comment to a bug
be set-root: assign the root directory for bug tracking
"""
from libbe.cmdutil import *
import sys

def list_bugs(args):
    bugs = list(tree_root(os.getcwd()).list())
    if len(bugs) == 0:
        print "No bugs found"
    for bug in bugs:
        print "%s: %s" % (unique_name(bug, bugs), bug.summary)


        
    

if len(sys.argv) == 1:
    print __doc__
else:
    {
        "list": list_bugs
    }[sys.argv[1]](sys.argv[2:])

    
