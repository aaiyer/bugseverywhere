from sqlobject import *
from turbogears.database import PackageHub
# Uncomment the following line if you wish to use Identity and SO_Provider
from turbogears.identity.soprovider import TG_User, TG_Group, TG_Permission
from turbogears import identity

hub = PackageHub("beweb")
__connection__ = hub

def people_map():
    return dict([(u.userId, u.displayName) for u in TG_User.select() if 
                "fixbugs" in identity.current.permissions])

# class YourDataClass(SQLObject):
#     pass
