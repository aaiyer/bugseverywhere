"""Close a bug"""
from libbe import cmdutil
def execute(args):
    assert(len(args) == 1)
    bug = cmdutil.get_bug(args[0])
    bug.status = "closed"
    bug.save()
