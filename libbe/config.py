import ConfigParser
import os.path
def path():
    """Return the path to the per-user config file"""
    return os.path.expanduser("~/.bugs_everywhere")

def set_val(name, value, section="DEFAULT"):
    """Set a value in the per-user config file

    :param name: The name of the value to set
    :param value: The new value to set (or None to delete the value)
    :param section: The section to store the name/value in
    """
    config = ConfigParser.ConfigParser()
    config.read(path())
    if value is not None:
        config.set(section, name, value)
    else:
        config.remove_option(section, name)
    config.write(file(path(), "wb"))
    pass

def get_val(name, section="DEFAULT"):
    """
    Get a value from the per-user config file

    :param name: The name of the value to get
    :section: The section that the name is in
    :return: The value, or None
    >>> get_val("junk") is None
    True
    >>> set_val("junk", "random")
    >>> get_val("junk")
    'random'
    >>> set_val("junk", None)
    >>> get_val("junk") is None
    True
    """
    config = ConfigParser.ConfigParser()
    config.read(path())
    try:
        return config.get(section, name)
    except ConfigParser.NoOptionError:
        return None
