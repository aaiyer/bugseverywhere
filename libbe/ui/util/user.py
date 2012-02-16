# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""Tools for getting, setting, creating, and parsing the user's ID.

IDs will look like 'John Doe <jdoe@example.com>'.  Note that the
:mod:`libbe.storage.vcs.arch <Arch VCS backend>` *enforces* IDs with
this format.

Do not confuse the user IDs discussed in this module, which refer to
humans, with the "user IDs" discussed in :mod:`libbe.util.id`, which
are human-readable tags refering to objects.
"""

try:
    from email.utils import formataddr, parseaddr
except ImportErrror:  # adjust to old python < 2.5
    from email.Utils import formataddr, parseaddr
import os
try:
    import pwd
except ImportError:  # handle non-Unix systems
    pwd = None
import re
from socket import gethostname

import libbe
import libbe.storage.util.config


def get_fallback_username():
    """Return a username extracted from environmental variables.
    """
    name = None
    for env in ['LOGNAME', 'USERNAME']:
        if os.environ.has_key(env):
            name = os.environ[env]
            break
    if name is None and pwd:
        pw_ent = pwd.getpwuid(os.getuid())
        name = pw_ent.pw_name
    assert name is not None
    return name

def get_fallback_fullname():
    """Return a full name extracted from environmental variables.
    """
    name = None
    for env in ['FULLNAME']:
        if os.environ.has_key(env):
            name = os.environ[env]
            break
    if pwd and not name:
        pw_ent = pwd.getpwuid(os.getuid())
        name = pw_ent.pw_gecos.split(',', 1)[0]
    if not name:
        name = get_fallback_username()
    return name

def get_fallback_email():
    """Return an email address extracted from environmental variables.
    """
    return os.getenv('EMAIL') or '%s@%s' % (
        get_fallback_username(), gethostname())

def create_user_id(name, email=None):
    """Create a user ID string from given `name` and `email` strings.

    Examples
    --------

    >>> create_user_id("John Doe", "jdoe@example.com")
    'John Doe <jdoe@example.com>'
    >>> create_user_id("John Doe")
    'John Doe'

    See Also
    --------
    parse_user_id : inverse
    """
    assert len(name) > 0
    if email == None or len(email) == 0:
        return name
    else:
        return formataddr((name, email))

def parse_user_id(value):
    """Parse a user ID string into `name` and `email` strings.

    Examples
    --------

    >>> parse_user_id("John Doe <jdoe@example.com>")
    ('John Doe', 'jdoe@example.com')
    >>> parse_user_id("John Doe")
    ('John Doe', None)
    >>> parse_user_id("John Doe <jdoe@example.com><what?>")
    ('John Doe', 'jdoe@example.com')
 
    See Also
    --------
    create_user_id : inverse
    """
    if '<' not in value:
        return (value, None)
    return parseaddr(value)

def get_user_id(storage=None):
    """Return a user ID, checking a list of possible sources.

    The source order is:

    1. Global BE configuration [#]_ (default section, setting 'user').
    2. `storage.get_user_id`, if that function is defined.
    3. :func:`get_fallback_username` and :func:`get_fallback_email`.

    .. [#] See :mod:`libbe.storage.util.config`.

    Notes
    -----
    Sometimes the storage will keep track of the user ID (e.g. most
    VCSs, see :meth:`libbe.storage.vcs.base.VCS.get_user_id`).  If so,
    we prefer that ID to the fallback, since the user has likely
    configured it directly.
    """
    user = libbe.storage.util.config.get_val('user')
    if user != None:
        return user
    if storage != None and hasattr(storage, 'get_user_id'):
        user = storage.get_user_id()
        if user != None:
            return user
    name = get_fallback_fullname()
    email = get_fallback_email()
    user = create_user_id(name, email)
    return user

def set_user_id(user_id):
    """Set the user ID in a user's BE configuration.

    See Also
    --------
    libbe.storage.util.config.set_val
    """
    user = libbe.storage.util.config.set_val('user', user_id)
