"""Create a new bug"""
from libbe import bugdir, cmdutil, names, utility
def execute(args):
    """
    >>> import os, time
    >>> from libbe import tests
    >>> dir = tests.bug_arch_dir()
    >>> os.chdir(dir.dir)
    >>> names.uuid = lambda: "a"
    >>> execute (("this is a test",))
    Created bug with ID a
    >>> bug = list(dir.list())[0]
    >>> bug.summary
    'this is a test'
    >>> bug.creator = os.environ["LOGNAME"]
    >>> bug.time <= int(time.time())
    True
    >>> bug.severity
    'minor'
    >>> bug.target == None
    True
    >>> tests.clean_up()
    """
    if len(args) != 1:
        raise cmdutil.UserError("Please supply a summary message")
    dir = cmdutil.bug_tree()
    bug = bugdir.new_bug(dir)
    bug.summary = args[0]
    bug.save()
    bugs = (dir.list())
    print "Created bug with ID %s" % cmdutil.unique_name(bug, bugs)

