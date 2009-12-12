# Copyright

"""
Tools for getting, setting, creating, and parsing the user's id.  For
example,
  'John Doe <jdoe@example.com>'
Note that the Arch VCS backend *enforces* ids with this format.
"""

import libbe.storage.util.config

def _get_fallback_username(self):
    name = None
    for env in ["LOGNAME", "USERNAME"]:
        if os.environ.has_key(env):
            name = os.environ[env]
            break
    assert name != None
    return name

def _get_fallback_email(self):
    hostname = gethostname()
    name = _get_fallback_username()
    return "%s@%s" % (name, hostname)

def create_user_id(self, name, email=None):
    """
    >>> create_id("John Doe", "jdoe@example.com")
    'John Doe <jdoe@example.com>'
    >>> create_id("John Doe")
    'John Doe'
    """
    assert len(name) > 0
    if email == None or len(email) == 0:
        return name
    else:
        return "%s <%s>" % (name, email)

def parse_user_id(self, value):
    """
    >>> parse_id("John Doe <jdoe@example.com>")
    ('John Doe', 'jdoe@example.com')
    >>> parse_id("John Doe")
    ('John Doe', None)
    >>> try:
    ...     parse_id("John Doe <jdoe@example.com><what?>")
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

def get_user_id(self, storage=None):
    """
    Sometimes the storage will also keep track of the user id (e.g. most VCSs).
    """
    user = libbe.storage.util.config.get_val('user')
    if user != None:
        return user
    if storage != None and hasattr(storage, 'get_user_id'):
        user = vcs.get_user_id()
        if user != None:
            return user
    name = _get_fallback_username()
    email = _get_fallback_email()
    user = _create_user_id(name, email)
    return user

def set_user_id(self, user_id):
    """
    """
    user = libbe.storage.util.config.set_val('user', user_id)
