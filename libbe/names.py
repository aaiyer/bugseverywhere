import commands
import os

def uuid():
    return commands.getoutput('uuidgen')

def creator():
    return os.environ["LOGNAME"]

def friendly_name(bugs, ctor):
    last = 0
    for bug in bugs:
        name = bug.name
        if name is None:
            continue
        if name.startswith(ctor):
            num = int(name.split("-")[-1])
            if num > last:
                last = num
    return "%s-%i" % (ctor, last+1)


