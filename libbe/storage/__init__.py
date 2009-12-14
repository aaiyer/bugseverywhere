# Copyright

import base

ConnectionError = base.ConnectionError
InvalidID = base.InvalidID
InvalidRevision = base.InvalidRevision
InvalidDirectory = base.InvalidDirectory
NotWriteable = base.NotWriteable
NotReadable = base.NotReadable
EmptyCommit = base.EmptyCommit

def get_storage(location):
    """
    Return a Storage instance from a repo location string.
    """
    import vcs
    s = vcs.detect_vcs(location)
    s.repo = location
    return s

__all__ = [ConnectionError, InvalidID, InvalidRevision,
           InvalidDirectory, NotWriteable, NotReadable,
           EmptyCommit, get_storage]
