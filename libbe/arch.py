from popen2 import Popen4
import os
import config
client = config.get_val("arch_client")
if client is None:
    client = "tla"
    config.set_val("arch_client", client)

def invoke(args):
    q=Popen4(args)
    output = q.fromchild.read()
    status = q.wait()
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    raise Exception("Command failed")

def invoke_client(*args, **kwargs):
    status = invoke((client,) + args)
    if status not in (0,):
        raise Exception("Command failed")

def add_id(filename):
    invoke_client("add-id", filename)

def delete_id(filename):
    invoke_client("delete-id", filename)
