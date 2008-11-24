Bugs-Everywhere-Web

This is a TurboGears (http://www.turbogears.org) project. It can be
started by running the start-beweb.py script.

Configure by creating an appropriate beweb/config.py from
beweb/config.py.example.  The server will edit the repositories that
it manages, so you should probably have it running on a seperate
branch than your working repository.  You can then merge/push
as you require to keep the branches in sync.

See
  http://docs.turbogears.org/1.0/Configuration
For standard turbogears configuration information.

Currently, you need to login for any methods with a
@identity.require() decorator.  The only group in the current
implementation is 'editbugs'.  Basically, anyone can browse around,
but only registered 'editbugs' members can change things.

Anonymous actions:
 * See project tree
 * See buglist
 * See comments
Editbugs required actions:
 * Create new comments
 * Reply to comments
 * Update comment info


All login attempts will fail unless you have added some valid users. See
  http://docs.turbogears.org/1.0/GettingStartedWithIdentity
For a good intro.  For the impatient, try something like
  Bugs-Everywhere-Web$ tg-admin toolbox
  browse to 'CatWalk' -> 'User' -> 'Add User+'
or
  Bugs-Everywhere-Web$ tg-admin sholl
  >>> u = User(user_name=u'jdoe', email_address=u'jdoe@example.com',
      display_name=u'Jane Doe', password=u'xxx')
  >>> g = Group(group_name=u'editbugs', display_name=u'Edit Bugs')
  >>> g.addUser(u)           # BE-Web uses SQLObject
Exit the tg-admin shell with Ctrl-Z on MS Windows, Ctrl-D on other systems.
