#!/usr/bin/env python
from libbe.cmdutil import *
from libbe.bugdir import tree_root, create_bug_dir
from libbe import names
import sys
import os
import commands
import commands.severity
__doc__ = """Bugs Everywhere - Distributed bug tracking

Supported commands
 set-root: assign the root directory for bug tracking
      new: Create a new bug
     list: list bugs
     show: show a particular bug
    close: close a bug
     open: re-open a bug
 severity: %s

Unimplemented commands
  comment: append a comment to a bug
""" % commands.severity.__desc__

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
    all_bugs = list(tree_root(os.getcwd()).list())
    bugs = [b for b in all_bugs if filter(b) ]
    if len(bugs) == 0:
        print "No matching bugs found"
    for bug in bugs:
        print bug_summary(bug, all_bugs)

def show_bug(args):
    bug_dir = tree_root(os.getcwd())
    if len(args) !=1:
        raise UserError("Please specify a bug id.")
    print bug_summary(get_bug(args[0], bug_dir), list(bug_dir.list()))

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
                "show": show_bug,
                "set-root": set_root,
                "new": new_bug,
                "close": close_bug,
                "open": open_bug,
                "severity": commands.severity.execute,
            }[sys.argv[1]]
        except KeyError, e:
            raise UserError("Unknown command \"%s\"" % e.args[0])
        cmd(sys.argv[2:])
    except UserError, e:
        print e
        sys.exit(1)
