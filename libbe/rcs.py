from arch import *
def mkdir(path):
    os.mkdir(path)
    add_id(path)

def set_file_contents(path, contents):
    add = not os.path.exists(path)
    file(path, "wb").write(contents)
    if add:
        add_id(path)

def unlink(path):
    try:
        os.unlink(path)
        delete_id(path)
    except OSError, e:
        if e.errno != 2:
            raise
