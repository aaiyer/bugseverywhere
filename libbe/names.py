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

import os
import sys


def uuid():
    # this code borrowed from standard commands module
    # but adapted to win32
    pipe = os.popen('uuidgen', 'r')
    text = pipe.read()
    sts = pipe.close()
    if sts not in (0, None):
        raise "Failed to run uuidgen"
    if text[-1:] == '\n': text = text[:-1]
    return text

def creator():
    if sys.platform != "win32":
        return os.environ["LOGNAME"]
    else:
        return os.environ["USERNAME"]

def unique_name(bug, bugs):
    """
    Generate short names from uuids.  Picks the minimum number of
    characters (>=3) from the beginning of the uuid such that the
    short names are unique.
    
    Obviously, as the number of bugs in the database grows, these
    short names will cease to be unique.  The complete uuid should be
    used for long term reference.
    """
    chars = 3
    for some_bug in bugs:
        if bug.uuid == some_bug.uuid:
            continue
        while (bug.uuid[:chars] == some_bug.uuid[:chars]):
            chars+=1
    return bug.uuid[:chars]
