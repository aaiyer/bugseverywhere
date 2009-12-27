# Copyright

import base

ConnectionError = base.ConnectionError
InvalidStorageVersion = base.InvalidStorageVersion
InvalidID = base.InvalidID
InvalidRevision = base.InvalidRevision
InvalidDirectory = base.InvalidDirectory
NotWriteable = base.NotWriteable
NotReadable = base.NotReadable
EmptyCommit = base.EmptyCommit

# a list of all past versions
STORAGE_VERSIONS = ['Bugs Everywhere Tree 1 0',
                    'Bugs Everywhere Directory v1.1',
                    'Bugs Everywhere Directory v1.2',
                    'Bugs Everywhere Directory v1.3',
                    'Bugs Everywhere Directory v1.4',
                    ]

# the current version
STORAGE_VERSION = STORAGE_VERSIONS[-1]

def get_storage(location):
    """
    Return a Storage instance from a repo location string.
    """
    import vcs
    s = vcs.detect_vcs(location)
    s.repo = location
    return s

__all__ = [ConnectionError, InvalidStorageVersion, InvalidID,
           InvalidRevision, InvalidDirectory, NotWriteable, NotReadable,
           EmptyCommit, STORAGE_VERSIONS, STORAGE_VERSION,
           get_storage]
