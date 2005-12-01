from sqlobject import *
from turbogears.database import PackageHub

hub = PackageHub("beweb")
__connection__ = hub

# class YourDataClass(SQLObject):
#     pass
