#!/usr/bin/env python
"""Bugs Everywhere - Distributed bug tracking

Supported commands
 set-root: assign the root directory for bug tracking
      new: Create a new bug
     list: list bugs
    close: close a bug
     open: re-open a bug

Unimplemented commands
  comment: append a comment to a bug
"""
from libbe.cmdutil import *
from libbe.bugdir import tree_root, create_bug_dir
from libbe import names
import sys
import os

def list_bugs(args):
    active = True
    severity = ("minor", "serious", "critical", "fatal")
    def filter(bug):
        if active is not None:
            if bug.active != active:
                return False
        if bug.severity not in severity:
            return False
        return True
        
    bugs = [b for b in tree_root(os.getcwd()).list() if filter(b) ]
    if len(bugs) == 0:
        print "No matching bugs found"
    for bug in bugs:
        target = bug.target
        if target is None:
            target = ""
        else:
            target = " target: %s" % target
        print "id: %s severity: %s%s creator: %s \n%s\n" % \
            (unique_name(bug, bugs), bug.severity, target, bug.creator,
             bug.summary)
def set_root(args):
    if len(args) != 1:
        raise UserError("Please supply a directory path")
    create_bug_dir(args[0])

def new_bug(args):
    if len(args) != 1:
        raise UserError("Please supply a summary message")
    dir = tree_root(".")
    bugs = (dir.list())
    bug = dir.new_bug()
    bug.creator = names.creator()
    bug.name = names.friendly_name(bugs, bug.creator)
    bug.severity = "minor"
    bug.status = "open"
    bug.summary = args[0]

def close_bug(args):
    assert(len(args) == 1)
    get_bug(args[0], tree_root('.')).status = "closed"

def open_bug(args):
    assert(len(args) == 1)
    get_bug(args[0], tree_root('.')).status = "open"

if len(sys.argv) == 1:
    print __doc__
else:
    try:
        try:
            cmd = {
                "list": list_bugs,
                "set-root": set_root,
                "new": new_bug,
                "close": close_bug,
                "open": open_bug,
            }[sys.argv[1]]
        except KeyError, e:
            raise UserError("Unknown command \"%s\"" % e.args[0])
        cmd(sys.argv[2:])
    except UserError, e:
        print e
        sys.exit(1)
