from popen2 import Popen3
import os
import config
client = config.get_val("arch_client")
if client is None:
    client = "tla"
    config.set_val("arch_client", client)

def invoke(args):
    q=Popen3(args, True)
    output = q.fromchild.read()
    error = q.childerr.read()
    status = q.wait()
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status), output, error
    raise Exception("Command failed: %s" % error)

def invoke_client(*args, **kwargs):
    cl_args = [client]
    cl_args.extend(args)
    status,output,error = invoke(cl_args)
    if status not in (0,):
        raise Exception("Command failed: %s" % error)
    return output

def add_id(filename):
    invoke_client("add-id", filename)

def delete_id(filename):
    invoke_client("delete-id", filename)

def mkdir(path):
    os.mkdir(path)
    add_id(path)

def set_file_contents(path, contents):
    add = not os.path.exists(path)
    file(path, "wb").write(contents)
    if add:
        add_id(path)


def path_in_reference(bug_dir, spec):
    if spec is not None:
        return invoke_client("file-find", bug_dir, spec).rstrip('\n')
    return invoke_client("file-find", bug_dir).rstrip('\n')


def unlink(path):
    try:
        os.unlink(path)
        delete_id(path)
    except OSError, e:
        if e.errno != 2:
            raise


def detect(path):
    """Detect whether a directory is revision-controlled using Arch"""
    path = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(path, "{arch}")):
            return True
        if path == "/":
            return False
        path = os.path.dirname(path)


name = "Arch"
