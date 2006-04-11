# If your project uses a database, you can set up database tests
# similar to what you see below. Be sure to set the db_uri to
# an appropriate uri for your testing database. sqlite is a good
# choice for testing, because you can use an in-memory database
# which is very fast.

from turbogears import testutil
#from beweb.model import YourDataClass
#from turbogears.identity.soprovider import TG_User

# database.set_db_uri("sqlite:///:memory:")

# class testTG_User(testutil.DBTest):
#     def get_model(self):
#         return TG_User
#
#     def test_creation(self):
#         "Object creation should set the name"
#         obj = TG_User(userId = "creosote",
#                       emailAddress = "spam@python.not",
#                       displayName = "Mr Creosote",
#                       password = "Wafer-thin Mint")
#         assert obj.displayName == "Mr Creosote"

