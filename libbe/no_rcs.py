from popen2 import Popen4
import os
import config
from os import mkdir, unlink

def add_id(filename):
    """Compatibility function"""
    pass

def delete_id(filename):
    """Compatibility function"""
    pass

def set_file_contents(path, contents):
    add = not os.path.exists(path)
    file(path, "wb").write(contents)
    if add:
        add_id(path)

def detect(path):
    """Compatibility function"""
    return True

name = "None"
