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

"""Utilities for building WSGI commands.

See Also
--------
:py:mod:`libbe.command.serve_storage` and
:py:mod:`libbe.command.serve_commands`.
"""

import copy
import hashlib
import logging
import logging.handlers
import os
import os.path
import re
import select
import signal
import StringIO
import sys
import time
import traceback
import types
import urllib
import urlparse
import wsgiref.simple_server

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

import libbe.command
import libbe.command.base
import libbe.command.util
import libbe.storage
import libbe.util.encoding
import libbe.util.http
import libbe.util.id


if libbe.TESTING == True:
    import doctest
    import unittest
    import wsgiref.validate
    try:
        import cherrypy.test.webtest
        cherrypy_test_webtest = True
    except ImportError:
        cherrypy_test_webtest = None


class HandlerError (Exception):
    def __init__(self, code, msg, headers=[]):
        super(HandlerError, self).__init__('{0} {1}'.format(code, msg))
        self.code = code
        self.msg = msg
        self.headers = headers


class Unauthenticated (HandlerError):
    def __init__(self, realm, msg='User Not Authenticated', headers=[]):
        super(Unauthenticated, self).__init__(401, msg, headers+[
                ('WWW-Authenticate','Basic realm="{0}"'.format(realm))])


class Unauthorized (HandlerError):
    def __init__(self, msg='User Not Authorized', headers=[]):
        super(Unauthorized, self).__init__(403, msg, headers)


class User (object):
    def __init__(self, uname=None, name=None, passhash=None, password=None):
        self.uname = uname
        self.name = name
        self.passhash = passhash
        if passhash is None:
            if password is not None:
                self.passhash = self.hash(password)
        else:
            assert password is None, (
                'Redundant password {0} with passhash {1}'.format(
                    password, passhash))
        self.users = None

    def from_string(self, string):
        string = string.strip()
        fields = string.split(':')
        if len(fields) != 3:
            raise ValueError, '{0}!=3 fields in "{1}"'.format(
                len(fields), string)
        self.uname,self.name,self.passhash = fields

    def __str__(self):
        return ':'.join([self.uname, self.name, self.passhash])

    def __cmp__(self, other):
        return cmp(self.uname, other.uname)

    def hash(self, password):
        return hashlib.sha1(password).hexdigest()

    def valid_login(self, password):
        if self.hash(password) == self.passhash:
            return True
        return False

    def set_name(self, name):
        self._set_property('name', name)

    def set_password(self, password):
        self._set_property('passhash', self.hash(password))

    def _set_property(self, property, value):
        if self.uname == 'guest':
            raise Unauthorized(
                'guest user not allowed to change {0}'.format(property))
        if (getattr(self, property) != value and
            self.users is not None):
            self.users.changed = True
        setattr(self, property, value)


class Users (dict):
    def __init__(self, filename=None):
        super(Users, self).__init__()
        self.filename = filename
        self.changed = False

    def load(self):
        if self.filename is None:
            return
        user_file = libbe.util.encoding.get_file_contents(
            self.filename, decode=True)
        self.clear()
        for line in user_file.splitlines():
            user = User()
            user.from_string(line)
            self.add_user(user)

    def save(self):
        if self.filename is not None and self.changed:
            lines = []
            for user in sorted(self.users):
                lines.append(str(user))
            libbe.util.encoding.set_file_contents(self.filename)
            self.changed = False

    def add_user(self, user):
        assert user.users is None, user.users
        user.users = self
        self[user.uname] = user

    def valid_login(self, uname, password):
        return (uname in self and
                self[uname].valid_login(password))


class WSGI_Object (object):
    """Utility class for WGSI clients and middleware.

    For details on WGSI, see `PEP 333`_

    .. _PEP 333: http://www.python.org/dev/peps/pep-0333/
    """
    def __init__(self, logger=None, log_level=logging.INFO, log_format=None):
        self.logger = logger
        self.log_level = log_level
        if log_format is None:
            self.log_format = (
                '{REMOTE_ADDR} - {REMOTE_USER} [{time}] '
                '"{REQUEST_METHOD} {REQUEST_URI} {HTTP_VERSION}" '
                '{status} {bytes} "{HTTP_REFERER}" "{HTTP_USER_AGENT}"')
        else:
            self.log_format = log_format

    def __call__(self, environ, start_response):
        if self.logger is not None:
            self.logger.log(
                logging.DEBUG, 'entering {0}'.format(self.__class__.__name__))
        ret = self._call(environ, start_response)
        if self.logger is not None:
            self.logger.log(
                logging.DEBUG, 'leaving {0}'.format(self.__class__.__name__))
        return ret

    def _call(self, environ, start_response):
        """The main WSGI entry point."""
        raise NotImplementedError
        # start_response() is a callback for setting response headers
        #   start_response(status, response_headers, exc_info=None)
        # status is an HTTP status string (e.g., "200 OK").
        # response_headers is a list of 2-tuples, the HTTP headers in
        # key-value format.
        # exc_info is used in exception handling.
        #
        # The application function then returns an iterable of body chunks.

    def error(self, environ, start_response, error, message, headers=[]):
        """Make it easy to call start_response for errors."""
        response = '{0} {1}'.format(error, message)
        self.log_request(environ, status=response, bytes=len(message))
        start_response(response,
                       [('Content-Type', 'text/plain')]+headers)
        return [message]

    def log_request(self, environ, status='-1 OK', bytes=-1):
        if self.logger is None or self.logger.level > self.log_level:
            return
        req_uri = urllib.quote(environ.get('SCRIPT_NAME', '')
                               + environ.get('PATH_INFO', ''))
        if environ.get('QUERY_STRING'):
            req_uri += '?' + environ['QUERY_STRING']
        start = time.localtime()
        if time.daylight:
            offset = time.altzone / 60 / 60 * -100
        else:
            offset = time.timezone / 60 / 60 * -100
        if offset >= 0:
            offset = '+{0:04d}'.format(offset)
        elif offset < 0:
            offset = '{0:04d}'.format(offset)
        d = {
            'REMOTE_ADDR': environ.get('REMOTE_ADDR', '-'),
            'REMOTE_USER': environ.get('REMOTE_USER', '-'),
            'REQUEST_METHOD': environ['REQUEST_METHOD'],
            'REQUEST_URI': req_uri,
            'HTTP_VERSION': environ.get('SERVER_PROTOCOL'),
            'time': time.strftime('%d/%b/%Y:%H:%M:%S ', start) + offset,
            'status': status.split(None, 1)[0],
            'bytes': bytes,
            'HTTP_REFERER': environ.get('HTTP_REFERER', '-'),
            'HTTP_USER_AGENT': environ.get('HTTP_USER_AGENT', '-'),
            }
        self.logger.log(self.log_level, self.log_format.format(**d))


class WSGI_Middleware (WSGI_Object):
    """Utility class for WGSI middleware.
    """
    def __init__(self, app, *args, **kwargs):
        super(WSGI_Middleware, self).__init__(*args, **kwargs)
        self.app = app

    def _call(self, environ, start_response):
        return self.app(environ, start_response)


class ExceptionApp (WSGI_Middleware):
    """Some servers (e.g. cherrypy) eat app-raised exceptions.

    Work around that by logging tracebacks by hand.
    """
    def _call(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except Exception, e:
            etype,value,tb = sys.exc_info()
            trace = ''.join(
                traceback.format_exception(etype, value, tb, None))
            self.logger.log(self.log_level, trace)
            raise


class HandlerErrorApp (WSGI_Middleware):
    """Catch HandlerErrors and return HTTP error pages.
    """
    def _call(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except HandlerError, e:
            self.log_request(environ, status=str(e), bytes=0)
            start_response('{0} {1}'.format(e.code, e.msg), e.headers)
            return []


class BEExceptionApp (WSGI_Middleware):
    """Translate BE-specific exceptions
    """
    def __init__(self, *args, **kwargs):
        super(BEExceptionApp, self).__init__(*args, **kwargs)

    def _call(self, environ, start_response):
        try:
            return self.app(environ, start_response)
        except libbe.storage.NotReadable as e:
            raise libbe.util.wsgi.HandlerError(403, 'Read permission denied')
        except libbe.storage.NotWriteable as e:
            raise libbe.util.wsgi.HandlerError(403, 'Write permission denied')
        except (libbe.command.UsageError,
                libbe.command.UserError,
                OSError,
                libbe.storage.ConnectionError,
                libbe.util.http.HTTPError,
                libbe.util.id.MultipleIDMatches,
                libbe.util.id.NoIDMatches,
                libbe.util.id.InvalidIDStructure,
                libbe.storage.InvalidID,
                ) as e:
            msg = '{0} {1}'.format(type(e).__name__, format(e))
            raise libbe.util.wsgi.HandlerError(
                libbe.util.http.HTTP_USER_ERROR, msg)


class UppercaseHeaderApp (WSGI_Middleware):
    """WSGI middleware that uppercases incoming HTTP headers.

    From PEP 333, `The start_response() Callable`_ :

        A reminder for server/gateway authors: HTTP
        header names are case-insensitive, so be sure
        to take that into consideration when examining
        application-supplied headers!

    .. _The start_response() Callable:
      http://www.python.org/dev/peps/pep-0333/#id20
    """
    def _call(self, environ, start_response):
        for key,value in environ.items():
            if key.startswith('HTTP_'):
                uppercase = key.upper()
                if uppercase != key:
                    environ[uppercase] = environ.pop(key)
        return self.app(environ, start_response)


class AuthenticationApp (WSGI_Middleware):
    """WSGI middleware for handling user authentication.
    """
    def __init__(self, realm, setting='be-auth', users=None, *args, **kwargs):
        super(AuthenticationApp, self).__init__(*args, **kwargs)
        self.realm = realm
        self.setting = setting
        self.users = users

    def _call(self, environ, start_response):
        environ['{0}.realm'.format(self.setting)] = self.realm
        try:
            username = self.authenticate(environ)
            environ['{0}.user'.format(self.setting)] = username
            environ['{0}.user.name'.format(self.setting)
                    ] = self.users[username].name
            return self.app(environ, start_response)
        except Unauthorized, e:
            return self.error(environ, start_response,
                              e.code, e.msg, e.headers)

    def authenticate(self, environ):
        """Handle user-authentication sent in the "Authorization" header.

        This function implements ``Basic`` authentication as described in
        HTTP/1.0 specification [1]_ .  Do not use this module unless you
        are using SSL, as it transmits unencrypted passwords.

        .. [1] http://www.w3.org/Protocols/HTTP/1.0/draft-ietf-http-spec.html#BasicAA

        Examples
        --------

        >>> users = Users()
        >>> users.add_user(User('Aladdin', 'Big Al', password='open sesame'))
        >>> app = AuthenticationApp(app=None, realm='Dummy Realm', users=users)
        >>> app.authenticate({'HTTP_AUTHORIZATION':'Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ=='})
        'Aladdin'
        >>> app.authenticate({'HTTP_AUTHORIZATION':'Basic AAAAAAAAAAAAAAAAAAAAAAAAAA=='})

        Notes
        -----

        Code based on authkit/authenticate/basic.py
        (c) 2005 Clark C. Evans.
        Released under the MIT License:
        http://www.opensource.org/licenses/mit-license.php
        """
        authorization = environ.get('HTTP_AUTHORIZATION', None)
        if authorization is None:
            raise Unauthorized('Authorization required')
        try:
            authmeth,auth = authorization.split(' ', 1)
        except ValueError:
            return None
        if 'basic' != authmeth.lower():
            return None  # non-basic HTTP authorization not implemented
        auth = auth.strip().decode('base64')
        try:
            username,password = auth.split(':', 1)
        except ValueError:
            return None
        if self.authfunc(environ, username, password):
            return username

    def authfunc(self, environ, username, password):
        if not username in self.users:
            return False
        if self.users[username].valid_login(password):
            if self.logger is not None:
                self.logger.log(self.log_level,
                    'Authenticated {0}'.format(self.users[username].name))
            return True
        return False


class WSGI_DataObject (WSGI_Object):
    """Useful WSGI utilities for handling data (POST, QUERY) and
    returning responses.
    """
    def __init__(self, *args, **kwargs):
        super(WSGI_DataObject, self).__init__(*args, **kwargs)

        # Maximum input we will accept when REQUEST_METHOD is POST
        # 0 ==> unlimited input
        self.maxlen = 0

    def ok_response(self, environ, start_response, content,
                    content_type='application/octet-stream',
                    headers=[]):
        if content is None:
            start_response('200 OK', [])
            return []
        if type(content) is types.UnicodeType:
            content = content.encode('utf-8')
        for i,header in enumerate(headers):
            header_name,header_value = header
            if type(header_value) == types.UnicodeType:
                headers[i] = (header_name, header_value.encode('ISO-8859-1'))
        response = '200 OK'
        content_length = len(content)
        self.log_request(environ, status=response, bytes=content_length)
        start_response(response, [
                ('Content-Type', content_type),
                ('Content-Length', str(content_length)),
                ]+headers)
        if self.is_head(environ):
            return []
        return [content]

    def query_data(self, environ):
        if not environ['REQUEST_METHOD'] in ['GET', 'HEAD']:
            raise HandlerError(404, 'Not Found')
        return self._parse_query(environ.get('QUERY_STRING', ''))

    def _parse_query(self, query):
        if len(query) == 0:
            return {}
        data = urlparse.parse_qs(
            query, keep_blank_values=True, strict_parsing=True)
        for k,v in data.items():
            if len(v) == 1:
                data[k] = v[0]
        return data

    def post_data(self, environ):
        if environ['REQUEST_METHOD'] != 'POST':
            raise HandlerError(404, 'Not Found')
        post_data = self._read_post_data(environ)
        return self._parse_post(post_data)

    def _parse_post(self, post):
        return self._parse_query(post)

    def _read_post_data(self, environ):
        try:
            clen = int(environ.get('CONTENT_LENGTH', '0'))
        except ValueError:
            clen = 0
        if clen != 0:
            if self.maxlen > 0 and clen > self.maxlen:
                raise ValueError, 'Maximum content length exceeded'
            return environ['wsgi.input'].read(clen)
        return ''

    def data_get_string(self, data, key, default=None, source='query'):
        if not key in data or data[key] in [None, 'None']:
            if default == HandlerError:
                raise HandlerError(
                    406, 'Missing {0} key {1}'.format(source, key))
            return default
        return data[key]

    def data_get_id(self, data, key='id', default=HandlerError,
                    source='query'):
        return self.data_get_string(data, key, default, source)

    def data_get_boolean(self, data, key, default=False, source='query'):
        val = self.data_get_string(data, key, default, source)
        if val == 'True':
            return True
        elif val == 'False':
            return False
        return val

    def is_head(self, environ):
        return environ['REQUEST_METHOD'] == 'HEAD'


class WSGI_AppObject (WSGI_Object):
    """Useful WSGI utilities for handling URL delegation.
    """
    def __init__(self, urls=tuple(), default_handler=None, setting='be-server',
                 *args, **kwargs):
        super(WSGI_AppObject, self).__init__(*args, **kwargs)
        self.urls = [(re.compile(regexp),callback) for regexp,callback in urls]
        self.default_handler = default_handler
        self.setting = setting

    def _call(self, environ, start_response):
        path = environ.get('PATH_INFO', '').lstrip('/')
        for regexp,callback in self.urls:
            match = regexp.match(path)
            if match is not None:
                setting = '{0}.url_args'.format(self.setting)
                environ[setting] = match.groups()
                return callback(environ, start_response)
        if self.default_handler is None:
            raise HandlerError(404, 'Not Found')
        return self.default_handler(environ, start_response)


class AdminApp (WSGI_AppObject, WSGI_DataObject, WSGI_Middleware):
    """WSGI middleware for managing users

    Changing passwords, usernames, etc.
    """
    def __init__(self, users=None, setting='be-auth', *args, **kwargs):
        handler = ('^admin/?', self.admin)
        if 'urls' not in kwargs:
            kwargs['urls'] = [handler]
        else:
            kwargs.urls.append(handler)
        super(AdminApp, self).__init__(*args, **kwargs)
        self.users = users
        self.setting = setting

    def admin(self, environ, start_response):
        if not '{0}.user'.format(self.setting) in environ:
            realm = envirion.get('{0}.realm'.format(self.setting))
            raise Unauthenticated(realm=realm)
        uname = environ.get('{0}.user'.format(self.setting))
        user = self.users[uname]
        data = self.post_data(environ)
        source = 'post'
        name = self.data_get_string(
            data, 'name', default=None, source=source)
        if name is not None:
            self.users[uname].set_name(name)
        password = self.data_get_string(
            data, 'password', default=None, source=source)
        if password is not None:
            self.users[uname].set_password(password)
        self.users.save()
        return self.ok_response(environ, start_response, None)


class SilentRequestHandler (wsgiref.simple_server.WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


class ServerCommand (libbe.command.base.Command):
    """Serve something over HTTP.

    Use this as a base class to build commands that serve a web interface.
    """
    _daemon_actions = ['start', 'stop']
    _daemon_action_present_participle = {
        'start': 'starting',
        'stop': 'stopping',
        }

    def __init__(self, *args, **kwargs):
        super(ServerCommand, self).__init__(*args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='port',
                    help='Bind server to port',
                    arg=libbe.command.Argument(
                        name='port', metavar='INT', type='int', default=8000)),
                libbe.command.Option(name='host',
                    help='Set host string (blank for localhost)',
                    arg=libbe.command.Argument(
                        name='host', metavar='HOST', default='localhost')),
                libbe.command.Option(name='daemon',
                    help=('Start or stop a server daemon.  Stopping requires '
                          'a PID file'),
                    arg=libbe.command.Argument(
                        name='daemon', metavar='ACTION',
                        completion_callback=libbe.command.util.Completer(
                            self._daemon_actions))),
                libbe.command.Option(name='pidfile', short_name='p',
                    help='Store the process id in the given path',
                    arg=libbe.command.Argument(
                        name='pidfile', metavar='FILE',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='logfile',
                    help='Log to the given path (instead of stdout)',
                    arg=libbe.command.Argument(
                        name='logfile', metavar='FILE',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='read-only', short_name='r',
                    help='Dissable operations that require writing'),
                libbe.command.Option(name='notify', short_name='n',
                    help='Send notification emails for changes.',
                    arg=libbe.command.Argument(
                        name='notify', metavar='EMAIL-COMMAND', default=None)),
                libbe.command.Option(name='ssl', short_name='s',
                    help='Use CherryPy to serve HTTPS (HTTP over SSL/TLS)'),
                libbe.command.Option(name='auth', short_name='a',
                    help=('Require authentication.  FILE should be a file '
                          'containing colon-separated '
                          'UNAME:USER:sha1(PASSWORD) lines, for example: '
                          '"jdoe:John Doe <jdoe@example.com>:'
                          'd99f8e5a4b02dc25f49da2ea67c0034f61779e72"'),
                    arg=libbe.command.Argument(
                        name='auth', metavar='FILE', default=None,
                        completion_callback=libbe.command.util.complete_path)),
                ])

    def _run(self, **params):
        if params['daemon'] not in self._daemon_actions + [None]:
            raise libbe.command.UserError(
                'Invalid daemon action "{0}".\nValid actions:\n  {1}'.format(
                    params['daemon'], self._daemon_actions))
        self._setup_logging(params)
        if params['daemon'] not in [None, 'start']:
            self._manage_daemon(params)
            return
        storage = self._get_storage()
        if params['read-only']:
            writeable = storage.writeable
            storage.writeable = False
        if params['auth']:
            self._check_restricted_access(storage, params['auth'])
        users = Users(params['auth'])
        users.load()
        app = self._get_app(logger=self.logger, storage=storage, **params)
        if params['auth']:
            app = AdminApp(app, users=users, logger=self.logger)
            app = AuthenticationApp(app, realm=storage.repo,
                                    users=users, logger=self.logger)
        app = UppercaseHeaderApp(app, logger=self.logger)
        server,details = self._get_server(params, app)
        details['repo'] = storage.repo
        try:
            self._start_server(params, server, details)
        except KeyboardInterrupt:
            pass
        self._stop_server(params, server)
        if params['read-only']:
            storage.writeable = writeable

    def _get_app(self, logger, storage, **kwargs):
        raise NotImplementedError()

    def _setup_logging(self, params, log_level=logging.INFO):
        self.logger = logging.getLogger('be.{0}'.format(self.name))
        self.log_level = log_level
        if params['logfile']:
            path = os.path.abspath(os.path.expanduser(
                    params['logfile']))
            handler = logging.handlers.TimedRotatingFileHandler(
                path, when='w6', interval=1, backupCount=4,
                encoding=libbe.util.encoding.get_text_file_encoding())
        else:
            handler = logging.StreamHandler(self.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(handler)
        self.logger.propagate = False
        if log_level is not None:
            handler.setLevel(log_level)
            self.logger.setLevel(log_level)

    def _get_server(self, params, app):
        details = {
            'socket-name':params['host'],
            'port':params['port'],
            }
        if params['ssl']:
            details['protocol'] = 'HTTPS'
        else:
            details['protocol'] = 'HTTP'
        app = BEExceptionApp(app, logger=self.logger)
        app = HandlerErrorApp(app, logger=self.logger)
        app = ExceptionApp(app, logger=self.logger)
        if params['ssl']:
            if cherrypy is None:
                raise libbe.command.UserError(
                    '--ssl requires the cherrypy module')
            server = cherrypy.wsgiserver.CherryPyWSGIServer(
                (params['host'], params['port']), app)
            #server.throw_errors = True
            #server.show_tracebacks = True
            private_key,certificate = _get_cert_filenames(
                'be-server', logger=self.logger, level=self.log_level)
            if cherrypy.wsgiserver.ssl_builtin is None:
                server.ssl_module = 'builtin'
                server.ssl_private_key = private_key
                server.ssl_certificate = certificate
            else:
                server.ssl_adapter = (
                    cherrypy.wsgiserver.ssl_builtin.BuiltinSSLAdapter(
                        certificate=certificate, private_key=private_key))
        else:
            server = wsgiref.simple_server.make_server(
                params['host'], params['port'], app,
                handler_class=SilentRequestHandler)
        return (server, details)

    def _daemonize(self, params):
        signal.signal(signal.SIGTERM, self._sigterm)
        self.logger.log(self.log_level, 'Daemonizing')
        pid = os.fork()
        if pid > 0:
            os._exit(0)
        os.setsid()
        pid = os.fork()
        if pid > 0:
            os._exit(0)
        self.logger.log(
            self.log_level, 'Daemonized with PID {0}'.format(os.getpid()))

    def _get_pidfile(self, params):
        params['pidfile'] = os.path.abspath(os.path.expanduser(
                params['pidfile']))
        self.logger.log(
            self.log_level, 'Get PID file at {0}'.format(params['pidfile']))
        if os.path.exists(params['pidfile']):
            raise libbe.command.UserError(
                'PID file {0} already exists'.format(params['pidfile']))
        pid = os.getpid()
        with open(params['pidfile'], 'w') as f:  # race between exist and open
            f.write(str(os.getpid()))            
        self.logger.log(
            self.log_level, 'Got PID file as {0}'.format(pid))

    def _start_server(self, params, server, details):
        if params['daemon']:
            self._daemonize(params=params)
        if params['pidfile']:
            self._get_pidfile(params)
        self.logger.log(
            self.log_level,
            ('Serving {protocol} on {socket-name} port {port} ...\n'
             'BE repository {repo}').format(**details))
        params['server stopped'] = False
        if isinstance(server, wsgiref.simple_server.WSGIServer):
            try:
                server.serve_forever()
            except select.error as e:
                if len(e.args) == 2 and e.args[1] == 'Interrupted system call':
                    pass
                else:
                    raise
        else:  # CherryPy server
            server.start()

    def _stop_server(self, params, server):
        if params['server stopped']:
            return  # already stopped, e.g. via _sigterm()
        params['server stopped'] = True
        self.logger.log(self.log_level, 'Closing server')
        if isinstance(server, wsgiref.simple_server.WSGIServer):
            server.server_close()
        else:
            server.stop()
        if params['pidfile']:
            os.remove(params['pidfile'])

    def _sigterm(self, signum, frame):
        self.logger.log(self.log_level, 'Handling SIGTERM')
        # extract params and server from the stack
        f = frame
        while f is not None and f.f_code.co_name != '_start_server':
            f = f.f_back
        if f is None:
            self.logger.log(
                self.log_level,
                'SIGTERM from outside _start_server(): {0}'.format(
                    frame.f_code))
            return  # where did this signal come from?
        params = f.f_locals['params']
        server = f.f_locals['server']
        self._stop_server(params=params, server=server)

    def _manage_daemon(self, params):
        "Daemon management (any action besides 'start')"
        if not params['pidfile']:
            raise libbe.command.UserError(
                'daemon management requires --pidfile')
        try:
            with open(params['pidfile'], 'r') as f:
                pid = f.read().strip()
        except IOError as e:
            raise libbe.command.UserError(
                'could not find PID file: {0}'.format(e))
        pid = int(pid)
        pp = self._daemon_action_present_participle[params['daemon']].title()
        self.logger.log(
            self.log_level,
            '{0} daemon running on process {1}'.format(pp, pid))
        if params['daemon'] == 'stop':
            os.kill(pid, signal.SIGTERM)
        else:
            raise NotImplementedError(params['daemon'])

    def _long_help(self):
        raise NotImplementedError()


class WSGICaller (object):
    """Call into WSGI apps programmatically
    """
    def __init__(self, *args, **kwargs):
        super(WSGICaller, self).__init__(*args, **kwargs)
        self.default_environ = { # required by PEP 333
            'REQUEST_METHOD': 'GET', # 'POST', 'HEAD'
            'REMOTE_ADDR': '192.168.0.123',
            'SCRIPT_NAME':'',
            'PATH_INFO': '',
            #'QUERY_STRING':'',   # may be empty or absent
            #'CONTENT_TYPE':'',   # may be empty or absent
            #'CONTENT_LENGTH':'', # may be empty or absent
            'SERVER_NAME':'example.com',
            'SERVER_PORT':'80',
            'SERVER_PROTOCOL':'HTTP/1.1',
            'wsgi.version':(1,0),
            'wsgi.url_scheme':'http',
            'wsgi.input':StringIO.StringIO(),
            'wsgi.errors':StringIO.StringIO(),
            'wsgi.multithread':False,
            'wsgi.multiprocess':False,
            'wsgi.run_once':False,
            }

    def getURL(self, app, path='/', method='GET', data=None,
               data_dict=None, scheme='http', environ={}):
        env = copy.copy(self.default_environ)
        env['PATH_INFO'] = path
        env['REQUEST_METHOD'] = method
        env['scheme'] = scheme
        if data_dict is not None:
            assert data is None, (data, data_dict)
            data = urllib.urlencode(data_dict)
        if data is not None:
            if data_dict is None:
                assert method == 'POST', (method, data)
            if method == 'POST':
                env['CONTENT_LENGTH'] = len(data)
                env['wsgi.input'] = StringIO.StringIO(data)
            else:
                assert method in ['GET', 'HEAD'], method
                env['QUERY_STRING'] = data
        for key,value in environ.items():
            env[key] = value
        return ''.join(app(env, self.start_response))

    def start_response(self, status, response_headers, exc_info=None):
        self.status = status
        self.response_headers = response_headers
        self.exc_info = exc_info


if libbe.TESTING:
    class WSGITestCase (unittest.TestCase):
        def setUp(self):
            self.logstream = StringIO.StringIO()
            self.logger = logging.getLogger('be-wsgi-test')
            console = logging.StreamHandler(self.logstream)
            console.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(console)
            self.logger.propagate = False
            console.setLevel(logging.INFO)
            self.logger.setLevel(logging.INFO)
            self.caller = WSGICaller()

        def getURL(self, *args, **kwargs):
            content = self.caller.getURL(*args, **kwargs)
            self.status = self.caller.status
            self.response_headers = self.caller.response_headers
            self.exc_info = self.caller.exc_info
            return content

    class WSGI_ObjectTestCase (WSGITestCase):
        def setUp(self):
            WSGITestCase.setUp(self)
            self.app = WSGI_Object(self.logger)

        def test_error(self):
            contents = self.app.error(
                environ=self.caller.default_environ,
                start_response=self.caller.start_response,
                error=123,
                message='Dummy Error',
                headers=[('X-Dummy-Header','Dummy Value')])
            self.failUnless(contents == ['Dummy Error'], contents)
            self.failUnless(
                self.caller.status == '123 Dummy Error', self.caller.status)
            self.failUnless(self.caller.response_headers == [
                    ('Content-Type','text/plain'),
                    ('X-Dummy-Header','Dummy Value')],
                            self.caller.response_headers)
            self.failUnless(self.caller.exc_info == None, self.caller.exc_info)

        def test_log_request(self):
            self.app.log_request(
                environ=self.caller.default_environ, status='-1 OK', bytes=123)
            log = self.logstream.getvalue()
            self.failUnless(log.startswith('192.168.0.123 -'), log)


    class ExceptionAppTestCase (WSGITestCase):
        def setUp(self):
            WSGITestCase.setUp(self)
            def child_app(environ, start_response):
                raise ValueError('Dummy Error')
            self.app = ExceptionApp(child_app, self.logger)

        def test_traceback(self):
            try:
                self.getURL(self.app)
            except ValueError, e:
                pass
            log = self.logstream.getvalue()
            self.failUnless(log.startswith('Traceback'), log)
            self.failUnless('child_app' in log, log)
            self.failUnless('ValueError: Dummy Error' in log, log)


    class AdminAppTestCase (WSGITestCase):
        def setUp(self):
            WSGITestCase.setUp(self)
            self.users = Users()
            self.users.add_user(
                User('Aladdin', 'Big Al', password='open sesame'))
            self.users.add_user(
                User('guest', 'Guest', password='guestpass'))
            def child_app(environ, start_response):
                pass
            app = AdminApp(
                app=child_app, users=self.users, logger=self.logger)
            app = AuthenticationApp(
                app=app, realm='Dummy Realm', users=self.users,
                logger=self.logger)
            self.app = UppercaseHeaderApp(app=app, logger=self.logger)

        def basic_auth(self, uname, password):
            """HTTP basic authorization string"""
            return 'Basic {0}'.format(
                '{0}:{1}'.format(uname, password).encode('base64'))

        def test_new_name(self):
            self.getURL(
                self.app, '/admin/', method='POST',
                data_dict={'name':'Prince Al'},
                environ={'HTTP_Authorization':
                             self.basic_auth('Aladdin', 'open sesame')})
            self.failUnless(self.status == '200 OK', self.status)
            self.failUnless(self.response_headers == [],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
            self.failUnless(self.users['Aladdin'].name == 'Prince Al',
                            self.users['Aladdin'].name)
            self.failUnless(self.users.changed == True,
                            self.users.changed)

        def test_new_password(self):
            self.getURL(
                self.app, '/admin/', method='POST',
                data_dict={'password':'New Pass'},
                environ={'HTTP_Authorization':
                             self.basic_auth('Aladdin', 'open sesame')})
            self.failUnless(self.status == '200 OK', self.status)
            self.failUnless(self.response_headers == [],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
            self.failUnless((self.users['Aladdin'].passhash ==
                             self.users['Aladdin'].hash('New Pass')),
                            self.users['Aladdin'].passhash)
            self.failUnless(self.users.changed == True,
                            self.users.changed)

        def test_guest_name(self):
            self.getURL(
                self.app, '/admin/', method='POST',
                data_dict={'name':'SPAM'},
                environ={'HTTP_Authorization':
                             self.basic_auth('guest', 'guestpass')})
            self.failUnless(self.status.startswith('403 '), self.status)
            self.failUnless(self.response_headers == [
                    ('Content-Type', 'text/plain')],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
            self.failUnless(self.users['guest'].name == 'Guest',
                            self.users['guest'].name)
            self.failUnless(self.users.changed == False,
                            self.users.changed)

        def test_guest_password(self):
            self.getURL(
                self.app, '/admin/', method='POST',
                data_dict={'password':'SPAM'},
                environ={'HTTP_Authorization':
                             self.basic_auth('guest', 'guestpass')})
            self.failUnless(self.status.startswith('403 '), self.status)
            self.failUnless(self.response_headers == [
                    ('Content-Type', 'text/plain')],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
            self.failUnless(self.users['guest'].name == 'Guest',
                            self.users['guest'].name)
            self.failUnless(self.users.changed == False,
                            self.users.changed)

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])


# The following certificate-creation code is adapted from pyOpenSSL's
# examples.

def _get_cert_filenames(server_name, autogenerate=True, logger=None,
                        level=None):
    """
    Generate private key and certification filenames.
    get_cert_filenames(server_name) -> (pkey_filename, cert_filename)
    """
    pkey_file = '{0}.pkey'.format(server_name)
    cert_file = '{0}.cert'.format(server_name)
    if autogenerate:
        for file in [pkey_file, cert_file]:
            if not os.path.exists(file):
                _make_certs(server_name, logger=logger, level=level)
    return (pkey_file, cert_file)

def _create_key_pair(type, bits):
    """Create a public/private key pair.

    Returns the public/private key pair in a PKey object.

    Parameters
    ----------
    type : TYPE_RSA or TYPE_DSA
      Key type.
    bits : int
      Number of bits to use in the key.
    """
    pkey = OpenSSL.crypto.PKey()
    pkey.generate_key(type, bits)
    return pkey

def _create_cert_request(pkey, digest="md5", **name):
    """Create a certificate request.

    Returns the certificate request in an X509Req object.

    Parameters
    ----------
    pkey : PKey
      The key to associate with the request.
    digest : "md5" or ?
      Digestion method to use for signing, default is "md5",
    `**name` :
      The name of the subject of the request, possible.
      Arguments are:

      ============ ========================
      C            Country name
      ST           State or province name
      L            Locality name
      O            Organization name
      OU           Organizational unit name
      CN           Common name
      emailAddress E-mail address
      ============ ========================
    """
    req = OpenSSL.crypto.X509Req()
    subj = req.get_subject()

    for (key,value) in name.items():
        setattr(subj, key, value)

    req.set_pubkey(pkey)
    req.sign(pkey, digest)
    return req

def _create_certificate(req, (issuerCert, issuerKey), serial,
                        (notBefore, notAfter), digest='md5'):
    """Generate a certificate given a certificate request.

    Returns the signed certificate in an X509 object.

    Parameters
    ----------
    req :
      Certificate reqeust to use
    issuerCert :
      The certificate of the issuer
    issuerKey :
      The private key of the issuer
    serial :
      Serial number for the certificate
    notBefore :
      Timestamp (relative to now) when the certificate
      starts being valid
    notAfter :
      Timestamp (relative to now) when the certificate
      stops being valid
    digest :
      Digest method to use for signing, default is md5
    """
    cert = OpenSSL.crypto.X509()
    cert.set_serial_number(serial)
    cert.gmtime_adj_notBefore(notBefore)
    cert.gmtime_adj_notAfter(notAfter)
    cert.set_issuer(issuerCert.get_subject())
    cert.set_subject(req.get_subject())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(issuerKey, digest)
    return cert

def _make_certs(server_name, logger=None, level=None):
    """Generate private key and certification files.

    `mk_certs(server_name) -> (pkey_filename, cert_filename)`
    """
    if OpenSSL == None:
        raise libbe.command.UserError(
            'SSL certificate generation requires the OpenSSL module')
    pkey_file,cert_file = _get_cert_filenames(
        server_name, autogenerate=False)
    if logger != None:
        logger.log(
            level, 'Generating certificates {0} {1}'.format(
                pkey_file, cert_file))
    cakey = _create_key_pair(OpenSSL.crypto.TYPE_RSA, 1024)
    careq = _create_cert_request(cakey, CN='Certificate Authority')
    cacert = _create_certificate(
        careq, (careq, cakey), 0, (0, 60*60*24*365*5)) # five years
    open(pkey_file, 'w').write(OpenSSL.crypto.dump_privatekey(
            OpenSSL.crypto.FILETYPE_PEM, cakey))
    open(cert_file, 'w').write(OpenSSL.crypto.dump_certificate(
            OpenSSL.crypto.FILETYPE_PEM, cacert))
