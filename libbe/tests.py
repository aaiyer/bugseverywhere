import tempfile
import shutil
import os
import os.path
from libbe import bugdir, arch
cleanable = []
def clean_up():
    global cleanable
    tmp = cleanable
    tmp.reverse()
    for obj in tmp:
        obj.clean_up()
    cleanable = []

class Dir:
    def __init__(self):
        self.name = tempfile.mkdtemp(prefix="testdir")
        cleanable.append(self)
    def clean_up(self):
        shutil.rmtree(self.name)

def arch_dir():
    dir = Dir()
    os.mkdir(os.path.join(dir.name, "{arch}"))
    return dir

def bug_arch_dir():
    dir = arch_dir()
    return bugdir.create_bug_dir(dir.name, arch)
