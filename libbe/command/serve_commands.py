# Copyright (C) 2010-2012 Chris Ball <cjb@laptop.org>
#                         W. Trevor King <wking@tremily.us>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option) any
# later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along with
# Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.

"""Define the :py:class:`ServeCommands` serving BE Commands over HTTP.

See Also
--------
:py:meth:`be-libbe.command.base.Command._run_remote` : the associated client
"""

import logging
import os.path
import posixpath
import re
import urllib
import wsgiref.simple_server

import libbe
import libbe.command
import libbe.command.base
import libbe.storage.util.mapfile
import libbe.util.wsgi
import libbe.version

if libbe.TESTING:
    import copy
    import doctest
    import StringIO
    import sys
    import unittest
    import wsgiref.validate
    try:
        import cherrypy.test.webtest
        cherrypy_test_webtest = True
    except ImportError:
        cherrypy_test_webtest = None

    import libbe.bugdir
    import libbe.command.list

    
class ServerApp (libbe.util.wsgi.WSGI_AppObject,
                 libbe.util.wsgi.WSGI_DataObject):
    """WSGI server for a BE Command invocation over HTTP.

    RESTful_ WSGI request handler for serving the
    libbe.command.base.Command._run_remote backend with GET, POST, and
    HEAD commands.

    This serves all commands from a single, persistant storage
    instance, usually a VCS-based repository located on the local
    machine.
    """
    server_version = "BE-command-server/" + libbe.version.version()

    def __init__(self, storage=None, notify=False, **kwargs):
        super(ServerApp, self).__init__(
            urls=[
                (r'^run/?$', self.run),
                ],
            **kwargs)
        self.storage = storage
        self.ui = libbe.command.base.UserInterface()
        self.notify = notify

    # handlers
    def run(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        source = 'post'
        try:
            name = data['command']
        except KeyError:
            raise libbe.util.wsgi.HandlerError(
                libbe.util.http.HTTP_USER_ERROR, 'UnknownCommand')
        parameters = data.get('parameters', {})
        try:
            Class = libbe.command.get_command_class(command_name=name)
        except libbe.command.UnknownCommand, e:
            raise libbe.util.wsgi.HandlerError(
                libbe.util.http.HTTP_USER_ERROR,
                'UnknownCommand {0}'.format(e))
        command = Class(ui=self.ui)
        self.ui.setup_command(command)
        arguments = [option.arg for option in command.options
                     if option.arg is not None]
        arguments.extend(command.args)
        for argument in arguments:
            if argument.name not in parameters:
                parameters[argument.name] = argument.default
        command.status = command._run(**parameters)  # already parsed params
        assert command.status == 0, command.status
        stdout = self.ui.io.get_stdout()
        if self.notify:  # TODO, check what notify does
            self._notify(environ, 'run', command)
        return self.ok_response(environ, start_response, stdout)

    # handler utility functions
    def _parse_post(self, post):
        return libbe.storage.util.mapfile.parse(post)

    def check_login(self, environ):
        user = environ.get('be-auth.user', None)
        if user is not None:  # we're running under AuthenticationApp
            if environ['REQUEST_METHOD'] == 'POST':
                # TODO: better detection of commands requiring writes
                if user == 'guest' or self.storage.is_writeable() == False:
                    raise _Unauthorized() # only non-guests allowed to write
            # allow read-only commands for all users

    def _notify(self, environ, command, id, params):
        message = self._format_notification(environ, command, id, params)
        self._submit_notification(message)

    def _format_notification(self, environ, command, id, params):
        key_length = len('command')
        for key,value in params:
            if len(key) > key_length and '\n' not in str(value):
                key_length = len(key)
        key_length += 1
        lines = []
        multi_line_params = []
        for key,value in [('address', environ.get('REMOTE_ADDR', '-')),
                          ('command', command), ('id', id)]+params:
            v = str(value)
            if '\n' in v:
                multi_line_params.append((key,v))
                continue
            lines.append('%*.*s %s' % (key_length, key_length, key+':', v))
        lines.append('')
        for key,value in multi_line_params:
            lines.extend(['=== START %s ===' % key, v,
                          '=== STOP %s ===' % key, ''])
        lines.append('')
        return '\n'.join(lines)

    def _submit_notification(self, message):
        libbe.util.subproc.invoke(self.notify, stdin=message, shell=True)


class ServeCommands (libbe.util.wsgi.ServerCommand):
    """Serve commands over HTTP.

    This allows you to run local `be` commands interfacing with remote
    data, transmitting command requests over the network.

    :py:class:`~libbe.command.base.Command` wrapper around
    :py:class:`ServerApp`.
    """

    name = 'serve-commands'

    def _get_app(self, logger, storage, **kwargs):
        return ServerApp(
            logger=logger, storage=storage, notify=kwargs.get('notify', False))

    def _long_help(self):
        return """
Example usage::

    $ be serve-commands

And in another terminal (or after backgrounding the server)::

    $ be --server http://localhost:8000/ list

If you bind your server to a public interface, take a look at the
``--read-only`` option or the combined ``--ssl --auth FILE``
options so other people can't mess with your repository.  If you do use
authentication, you'll need to send in your username and password::

    $ be --server http://username:password@localhost:8000/ list
"""


# alias for libbe.command.base.get_command_class()
Serve_commands = ServeCommands


if libbe.TESTING:
    class ServerAppTestCase (libbe.util.wsgi.WSGITestCase):
        def setUp(self):
            libbe.util.wsgi.WSGITestCase.setUp(self)
            self.bd = libbe.bugdir.SimpleBugDir(memory=False)
            self.app = ServerApp(self.bd.storage, logger=self.logger)

        def tearDown(self):
            self.bd.cleanup()
            libbe.util.wsgi.WSGITestCase.tearDown(self)

        def test_run_list(self):
            list = libbe.command.list.List()
            params = list._parse_options_args()
            data = libbe.storage.util.mapfile.generate({
                    'command': 'list',
                    'parameters': params,
                    }, context=0)
            self.getURL(self.app, '/run', method='POST', data=data)
            self.failUnless(self.status.startswith('200 '), self.status)
            self.failUnless(
                ('Content-Type', 'application/octet-stream'
                 ) in self.response_headers,
                self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
        # TODO: integration tests on ServeCommands?

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
