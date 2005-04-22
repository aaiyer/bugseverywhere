"""Bug fixing in progress"""
from libbe import cmdutil
def execute(args):
    """
    >>> from libbe import tests
    >>> import os
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> dir.get_bug("a").status
    'open'
    >>> execute(("a",))
    >>> dir.get_bug("a").status
    'in-progress'
    >>> tests.clean_up()
    """
    assert(len(args) == 1)
    bug = cmdutil.get_bug(args[0])
    bug.status = "in-progress"
    bug.save()
