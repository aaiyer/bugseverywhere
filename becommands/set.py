"""Change tree settings"""
from libbe import cmdutil 
def execute(args):
    if len(args) > 2:
        raise cmdutil.UserError("Too many arguments.")
    tree = cmdutil.bug_tree()
    if len(args) == 0:
        keys = tree.settings.keys()
        keys.sort()
        for key in keys:
            print "%16s: %s" % (key, tree.settings[key])
    elif len(args) == 1:
        print tree.settings.get(args[0])
    else:
        if args[1] != "none":
            tree.settings[args[0]] = args[1]
        else:
            del tree.settings[args[0]]
        tree.save_settings()

def help():
    return """be set [name] [value]

Show or change per-tree settings. 

If name and value are supplied, the name is set to a new value.
If no value is specified, the current value is printed.
If no arguments are provided, all names and values are listed. 

Interesting settings are:
rcs_name
  The name of the revision control system.  "Arch" and "None" are supported.
target
  The current development goal 

To unset a setting, set it to "none".
"""
