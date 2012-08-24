# Copyright (C) 2010-2012 Chris Ball <cjb@laptop.org>
#                         W. Trevor King <wking@drexel.edu>
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

"""Define the :class:`ServeCommands` serving BE Commands over HTTP.

See Also
--------
:py:meth:`be-libbe.command.base.Command._run_remote` : the associated client
"""

import hashlib
import logging
import os.path
import posixpath
import re
import sys
import time
import traceback
import types
import urllib
import wsgiref.simple_server

import yaml

try:
    # Python >= 2.6
    from urlparse import parse_qs
except ImportError:
    # Python <= 2.5
    from cgi import parse_qs
try:
    import cherrypy
    import cherrypy.wsgiserver
except ImportError:
    cherrypy = None
if cherrypy != None:
    try: # CherryPy >= 3.2
        import cherrypy.wsgiserver.ssl_builtin
    except ImportError: # CherryPy <= 3.1.X
        cherrypy.wsgiserver.ssl_builtin = None
try:
    import OpenSSL
except ImportError:
    OpenSSL = None

import libbe
import libbe.command
import libbe.command.serve
import libbe.command.util
import libbe.util.encoding
import libbe.util.subproc
import libbe.version

if libbe.TESTING == True:
    import copy
    import doctest
    import StringIO
    import unittest
    import wsgiref.validate
    try:
        import cherrypy.test.webtest
        cherrypy_test_webtest = True
    except ImportError:
        cherrypy_test_webtest = None

    import libbe.bugdir
    import libbe.command.list

    
class ServerApp (libbe.command.serve.WSGI_AppObject):
    """WSGI server for a BE Command invocation over HTTP.

    RESTful_ WSGI request handler for serving the
    libbe.command.base.Command._run_remote backend with GET, POST, and
    HEAD commands.

    This serves all commands from a single, persistant storage
    instance, usually a VCS-based repository located on the local
    machine.
    """
    server_version = "BE-command-server/" + libbe.version.version()

    def __init__(self, storage, notify=False, **kwargs):
        libbe.command.serve.WSGI_AppObject.__init__(self, **kwargs)
        self.storage = storage
        self.ui = libbe.command.base.UserInterface()
        self.notify = notify
        self.http_user_error = 418
        self.urls = [(r'^run$', self.run)]

    def __call__(self, environ, start_response):
        """The main WSGI application.

        Dispatch the current request to the functions from above and
        store the regular expression captures in the WSGI environment
        as `be-server.url_args` so that the functions from above can
        access the url placeholders.

        URL dispatcher from Armin Ronacher's "Getting Started with WSGI"
          http://lucumr.pocoo.org/2007/5/21/getting-started-with-wsgi
        """
        if self.logger != None:
            self.logger.log(logging.DEBUG, 'ServerApp')
        path = environ.get('PATH_INFO', '').lstrip('/')
        try:
            for regex, callback in self.urls:
                match = re.search(regex, path)
                if match is not None:
                    environ['be-server.url_args'] = match.groups()
                    return callback(environ, start_response)
            print('not found')
            raise libbe.command.serve._HandlerError(404, 'Not Found')
        except libbe.command.serve._HandlerError, e:
            return self.error(environ, start_response,
                              e.code, e.msg, e.headers)

    # handlers
    def run(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        source = 'post'
        name = data['command']
        parameters = data['parameters']
        try:
            Class = libbe.command.get_command_class(command_name=name)
        except libbe.command.UnknownCommand, e:
            raise libbe.command.serve._HandlerError(
                self.http_user_error, 'UnknownCommand {}'.format(e))
        command = Class(ui=self.ui)
        self.ui.setup_command(command)
        command.status = command._run(**parameters)  # already parsed params
        assert command.status == 0, command.status
        stdout = self.ui.io.get_stdout()
        if self.notify:  # TODO, check what notify does
            self._notify(environ, 'run', command)
        return self.ok_response(environ, start_response, stdout)

    # handler utility functions
    def _parse_post(self, post):
        return yaml.safe_load(post)

    def check_login(self, environ):
        user = environ.get('be-auth.user', None)
        if user != None: # we're running under AuthenticationApp
            if environ['REQUEST_METHOD'] == 'POST':
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


class Serve_Commands (libbe.command.Command):
    """Serve commands over HTTP.

    This allows you to run local `be` commands interfacing with remote
    data, transmitting command requests over the network.

    :class:`~libbe.command.base.Command` wrapper around
    :class:`ServerApp`.
    """

    name = 'serve-commands'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='port',
                    help='Bind server to port (%default)',
                    arg=libbe.command.Argument(
                        name='port', metavar='INT', type='int', default=8000)),
                libbe.command.Option(name='host',
                    help='Set host string (blank for localhost, %default)',
                    arg=libbe.command.Argument(
                        name='host', metavar='HOST', default='')),
                libbe.command.Option(name='read-only', short_name='r',
                    help='Dissable operations that require writing'),
                libbe.command.Option(name='notify', short_name='n',
                    help='Send notification emails for changes.',
                    arg=libbe.command.Argument(
                        name='notify', metavar='EMAIL-COMMAND', default=None)),
                libbe.command.Option(name='ssl', short_name='s',
                    help='Use CherryPy to serve HTTPS (HTTP over SSL/TLS)'),
                libbe.command.Option(name='auth', short_name='a',
                    help='Require authentication.  FILE should be a file containing colon-separated UNAME:USER:sha1(PASSWORD) lines, for example: "jdoe:John Doe <jdoe@example.com>:read:d99f8e5a4b02dc25f49da2ea67c0034f61779e72"',
                    arg=libbe.command.Argument(
                        name='auth', metavar='FILE', default=None,
                        completion_callback=libbe.command.util.complete_path)),
                ])

    def _run(self, **params):
        self._setup_logging()
        storage = self._get_storage()
        if params['read-only'] == True:
            writeable = storage.writeable
            storage.writeable = False
        if params['host'] == '':
            params['host'] = 'localhost'
        if params['auth'] != None:
            self._check_restricted_access(storage, params['auth'])
        users = libbe.command.serve.Users(params['auth'])
        users.load()
        app = ServerApp(
            storage=storage, notify=params['notify'], logger=self.logger)
        if params['auth'] != None:
            app = AdminApp(app, users=users, logger=self.logger)
            app = AuthenticationApp(app, realm=storage.repo,
                                    users=users, logger=self.logger)
        app = libbe.command.serve.UppercaseHeaderApp(app, logger=self.logger)
        server,details = self._get_server(params, app)
        details['repo'] = storage.repo
        try:
            self._start_server(params, server, details)
        except KeyboardInterrupt:
            pass
        self._stop_server(params, server)
        if params['read-only'] == True:
            storage.writeable = writeable

    def _setup_logging(self, log_level=logging.INFO):
        self.logger = logging.getLogger('be-serve')
        self.log_level = logging.INFO
        console = logging.StreamHandler(self.stdout)
        console.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(console)
        self.logger.propagate = False
        if log_level is not None:
            console.setLevel(log_level)
            self.logger.setLevel(log_level)

    def _get_server(self, params, app):
        details = {'port':params['port']}
        app = libbe.command.serve.ExceptionApp(app, logger=self.logger)
        if params['ssl'] == True:
            details['protocol'] = 'HTTPS'
            if cherrypy == None:
                raise libbe.command.UserError, \
                    '--ssl requires the cherrypy module'
            server = cherrypy.wsgiserver.CherryPyWSGIServer(
                (params['host'], params['port']), app)
            #server.throw_errors = True
            #server.show_tracebacks = True
            private_key,certificate = libbe.command.serve.get_cert_filenames(
                'be-server', logger=self.logger)
            if cherrypy.wsgiserver.ssl_builtin == None:
                server.ssl_module = 'builtin'
                server.ssl_private_key = private_key
                server.ssl_certificate = certificate
            else:
                server.ssl_adapter = \
                    cherrypy.wsgiserver.ssl_builtin.BuiltinSSLAdapter(
                    certificate=certificate, private_key=private_key)
            details['socket-name'] = params['host']
        else:
            details['protocol'] = 'HTTP'
            server = wsgiref.simple_server.make_server(
                params['host'], params['port'], app,
                handler_class=libbe.command.serve.SilentRequestHandler)
            details['socket-name'] = server.socket.getsockname()[0]
        return (server, details)

    def _start_server(self, params, server, details):
        self.logger.log(self.log_level,
            'Serving %(protocol)s on %(socket-name)s port %(port)s ...' \
            % details)
        self.logger.log(self.log_level,
                        'BE repository %(repo)s' % details)
        if params['ssl'] == True:
            server.start()
        else:
            server.serve_forever()

    def _stop_server(self, params, server):
        self.logger.log(self.log_level, 'Clossing server')
        if params['ssl'] == True:
            server.stop()
        else:
            server.server_close()

    def _long_help(self):
        return """
Example usage::

    $ be serve-commands

And in another terminal (or after backgrounding the server)::

    $ be --server http://localhost:8000/ list

If you bind your server to a public interface, take a look at the
``--read-only`` option or the combined ``--ssl --auth FILE``
options so other people can't mess with your repository.  If you do use
authentication, you'll need to send in your username and password with,
for example::

    $ be --repo http://username:password@localhost:8000/ list
"""


# alias for libbe.command.base.get_command_class()
Serve_commands = Serve_Commands

if libbe.TESTING == True:
    class ServerAppTestCase (libbe.command.serve.WSGITestCase):
        def setUp(self):
            libbe.command.serve.WSGITestCase.setUp(self)
            self.bd = libbe.bugdir.SimpleBugDir(memory=False)
            self.app = ServerApp(self.bd.storage, logger=self.logger)
        def tearDown(self):
            self.bd.cleanup()
            libbe.command.serve.WSGITestCase.tearDown(self)
        def test_run_list(self):
            list = libbe.command.list.List()
            params = list._parse_options_args()
            data = yaml.safe_dump({
                    'command': 'list',
                    'parameters': params,
                    })
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
