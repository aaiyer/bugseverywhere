# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
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
    arch.ensure_user_id()
    dir = Dir()
    arch.init_tree(dir.name)
    return dir

def bug_arch_dir():
    dir = arch_dir()
    return bugdir.create_bug_dir(dir.name, arch)

def simple_bug_dir():
    dir = bug_arch_dir()
    bug_a = bugdir.new_bug(dir, "a")
    bug_b = bugdir.new_bug(dir, "b")
    bug_b.status = "closed"
    bug_a.save()
    bug_b.save()
    return dir
