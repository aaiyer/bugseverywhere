# Copyright (C) 2009-2010 W. Trevor King <wking@drexel.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
Tools for getting, setting, creating, and parsing the user's id.  For
example,
  'John Doe <jdoe@example.com>'
Note that the Arch VCS backend *enforces* ids with this format.
"""

import os
import re
from socket import gethostname

import libbe
import libbe.storage.util.config

def get_fallback_username():
    name = None
    for env in ["LOGNAME", "USERNAME"]:
        if os.environ.has_key(env):
            name = os.environ[env]
            break
    assert name != None
    return name

def get_fallback_email():
    hostname = gethostname()
    name = get_fallback_username()
    return "%s@%s" % (name, hostname)

def create_user_id(name, email=None):
    """
    >>> create_user_id("John Doe", "jdoe@example.com")
    'John Doe <jdoe@example.com>'
    >>> create_user_id("John Doe")
    'John Doe'
    """
    assert len(name) > 0
    if email == None or len(email) == 0:
        return name
    else:
        return "%s <%s>" % (name, email)

def parse_user_id(value):
    """
    >>> parse_user_id("John Doe <jdoe@example.com>")
    ('John Doe', 'jdoe@example.com')
    >>> parse_user_id("John Doe")
    ('John Doe', None)
    >>> try:
    ...     parse_user_id("John Doe <jdoe@example.com><what?>")
    ... except AssertionError:
    ...     print "Invalid match"
    Invalid match
    """
    emailexp = re.compile("(.*) <([^>]*)>(.*)")
    match = emailexp.search(value)
    if match == None:
        email = None
        name = value
    else:
        assert len(match.groups()) == 3
        assert match.groups()[2] == "", match.groups()
        email = match.groups()[1]
        name = match.groups()[0]
    assert name != None
    assert len(name) > 0
    return (name, email)

def get_user_id(storage=None):
    """
    Sometimes the storage will also keep track of the user id (e.g. most VCSs).
    """
    user = libbe.storage.util.config.get_val('user')
    if user != None:
        return user
    if storage != None and hasattr(storage, 'get_user_id'):
        user = storage.get_user_id()
        if user != None:
            return user
    name = get_fallback_username()
    email = get_fallback_email()
    user = create_user_id(name, email)
    return user

def set_user_id(user_id):
    """
    """
    user = libbe.storage.util.config.set_val('user', user_id)
