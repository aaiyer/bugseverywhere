from popen2 import Popen4
import os

def invoke(args):
    q=Popen4(args)
    output = q.fromchild.read()
    status = q.wait()
    if os.WIFEXITED(status):
        return (os.WEXITSTATUS(status))

def add_id(filename):
    return invoke(("tla", "add-id", filename))

def delete_id(filename):
    return invoke(("tla", "delete-id", filename))
