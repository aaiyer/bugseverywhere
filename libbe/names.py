import commands
import os

def uuid():
    return commands.getoutput('uuidgen')

def creator():
    return os.environ["LOGNAME"]
