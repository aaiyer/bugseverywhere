"""Change tree settings"""
from libbe import cmdutil 
def execute(args):
    assert len(args) in (1, 2)
    tree = cmdutil.bug_tree()
    if len(args) == 1:
        print tree.settings.get(args[0])
    else:
        tree.settings[args[0]] = args[1]
        tree.save_settings()

