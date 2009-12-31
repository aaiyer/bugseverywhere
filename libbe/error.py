# Copyright

"""
General error classes for Bugs-Everywhere.
"""

class NotSupported (NotImplementedError):
    def __init__(self, action, message):
        msg = '%s not supported: %s' % (action, message)
        NotImplementedError.__init__(self, msg)
        self.action = action
        self.message = message
