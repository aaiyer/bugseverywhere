"""Re-open a bug"""
from libbe import cmdutil
def execute(args):
    """
    >>> from libbe import tests
    >>> import os
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> dir.get_bug("b").status
    'closed'
    >>> execute(("b",))
    >>> dir.get_bug("b").status
    'open'
    >>> tests.clean_up()
    """
    assert(len(args) == 1)
    bug = cmdutil.get_bug(args[0])
    bug.status = "open"
    bug.save()
