def unique_name(bug, bugs):
    return bug.name

class UserError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)
