"""Assign the root directory for bug tracking"""
from libbe import bugdir, cmdutil, rcs

def execute(args):
    """
    >>> from libbe import tests
    >>> dir = tests.Dir()
    >>> try:
    ...     bugdir.tree_root(dir.name)
    ... except bugdir.NoBugDir, e:
    ...     True
    True
    >>> execute([dir.name])
    No revision control detected.
    Directory initialized.
    >>> bd = bugdir.tree_root(dir.name)
    >>> bd.root = dir.name
    >>> dir = tests.arch_dir()
    >>> execute([dir.name+"/{arch}"])
    Using Arch for revision control.
    Directory initialized.
    >>> bd = bugdir.tree_root(dir.name+"/{arch}")
    >>> bd.root = dir.name
    >>> tests.clean_up()
    """
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a directory path")
    dir_rcs = rcs.detect(args[0])
    if dir_rcs.name is not "None":
        print "Using %s for revision control." % dir_rcs.name
    else:
        print "No revision control detected."
    bugdir.create_bug_dir(args[0], dir_rcs)
    print "Directory initialized."
