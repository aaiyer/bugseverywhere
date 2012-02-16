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

"""Define the :class:`Serve` serving BE Storage over HTTP.

See Also
--------
:mod:`libbe.storage.http` : the associated client
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
    
class _HandlerError (Exception):
    def __init__(self, code, msg, headers=[]):
        Exception.__init__(self, '%d %s' % (code, msg))
        self.code = code
        self.msg = msg
        self.headers = headers

class _Unauthenticated (_HandlerError):
    def __init__(self, realm, msg='User Not Authenticated', headers=[]):
        _HandlerError.__init__(self, 401, msg, headers+[
                ('WWW-Authenticate','Basic realm="%s"' % realm)])

class _Unauthorized (_HandlerError):
    def __init__(self, msg='User Not Authorized', headers=[]):
        _HandlerError.__init__(self, 403, msg, headers)

class User (object):
    def __init__(self, uname=None, name=None, passhash=None, password=None):
        self.uname = uname
        self.name = name
        self.passhash = passhash
        if passhash == None:
            if password != None:
                self.passhash = self.hash(password)
        else:
            assert password == None, \
                'Redundant password %s with passhash %s' % (password, passhash)
        self.users = None
    def from_string(self, string):
        string = string.strip()
        fields = string.split(':')
        if len(fields) != 3:
            raise ValueError, '%d!=3 fields in "%s"' % (len(fields), string)
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
            raise _Unauthorized('guest user not allowed to change %s' % property)
        if getattr(self, property) != value \
                and self.users != None:
            self.users.changed = True
        setattr(self, property, value)

class Users (dict):
    def __init__(self, filename=None):
        dict.__init__(self)
        self.filename = filename
        self.changed = False
    def load(self):
        if self.filename == None:
            return
        user_file = libbe.util.encoding.get_file_contents(
            self.filename, decode=True)
        self.clear()
        for line in user_file.splitlines():
            user = User()
            user.from_string(line)
            self.add_user(user)
    def save(self):
        if self.filename != None and self.changed == True:
            lines = []
            for user in sorted(self.users):
                lines.append(str(user))
            libbe.util.encoding.set_file_contents(self.filename)
            self.changed = False
    def add_user(self, user):
        assert user.users == None, user.users
        user.users = self
        self[user.uname] = user
    def valid_login(self, uname, password):
        if uname in self and \
                self[uname].valid_login(password) == True:
            return True
        return False

class WSGI_Object (object):
    """Utility class for WGSI clients and middleware.

    For details on WGSI, see `PEP 333`_

    .. _PEP 333: http://www.python.org/dev/peps/pep-0333/
    """
    def __init__(self, logger=None, log_level=logging.INFO, log_format=None):
        self.logger = logger
        self.log_level = log_level
        if log_format == None:
            self.log_format = (
                '%(REMOTE_ADDR)s - %(REMOTE_USER)s [%(time)s] '
                '"%(REQUEST_METHOD)s %(REQUEST_URI)s %(HTTP_VERSION)s" '
                '%(status)s %(bytes)s "%(HTTP_REFERER)s" "%(HTTP_USER_AGENT)s"')
        else:
            self.log_format = log_format

    def __call__(self, environ, start_response):
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
        response = '%d %s' % (error, message)
        self.log_request(environ, status=response, bytes=len(message))
        start_response(response,
                       [('Content-Type', 'text/plain')]+headers)
        return [message]

    def log_request(self, environ, status='-1 OK', bytes=-1):
        if self.logger == None:
            return
        req_uri = urllib.quote(environ.get('SCRIPT_NAME', '')
                               + environ.get('PATH_INFO', ''))
        if environ.get('QUERY_STRING'):
            req_uri += '?'+environ['QUERY_STRING']
        start = time.localtime()
        if time.daylight:
            offset = time.altzone / 60 / 60 * -100
        else:
            offset = time.timezone / 60 / 60 * -100
        if offset >= 0:
            offset = "+%0.4d" % (offset)
        elif offset < 0:
            offset = "%0.4d" % (offset)
        d = {
            'REMOTE_ADDR': environ.get('REMOTE_ADDR') or '-',
            'REMOTE_USER': environ.get('REMOTE_USER') or '-',
            'REQUEST_METHOD': environ['REQUEST_METHOD'],
            'REQUEST_URI': req_uri,
            'HTTP_VERSION': environ.get('SERVER_PROTOCOL'),
            'time': time.strftime('%d/%b/%Y:%H:%M:%S ', start) + offset,
            'status': status.split(None, 1)[0],
            'bytes': bytes,
            'HTTP_REFERER': environ.get('HTTP_REFERER', '-'),
            'HTTP_USER_AGENT': environ.get('HTTP_USER_AGENT', '-'),
            }
        self.logger.log(self.log_level, self.log_format % d)

class ExceptionApp (WSGI_Object):
    """Some servers (e.g. cherrypy) eat app-raised exceptions.

    Work around that by logging tracebacks by hand.
    """
    def __init__(self, app, *args, **kwargs):
        WSGI_Object.__init__(self, *args, **kwargs)
        self.app = app

    def __call__(self, environ, start_response):
        if self.logger != None:
            self.logger.log(logging.DEBUG, 'ExceptionApp')
        try:
            return self.app(environ, start_response)
        except Exception, e:
            etype,value,tb = sys.exc_info()
            trace = ''.join(
                traceback.format_exception(etype, value, tb, None))
            self.logger.log(self.log_level, trace)
            raise

class UppercaseHeaderApp (WSGI_Object):
    """WSGI middleware that uppercases incoming HTTP headers.

    From PEP 333, `The start_response() Callable`_ :

        A reminder for server/gateway authors: HTTP
        header names are case-insensitive, so be sure
        to take that into consideration when examining
        application-supplied headers!

    .. _The start_response() Callable:
      http://www.python.org/dev/peps/pep-0333/#id20
    """
    def __init__(self, app, *args, **kwargs):
        WSGI_Object.__init__(self, *args, **kwargs)
        self.app = app

    def __call__(self, environ, start_response):
        if self.logger != None:
            self.logger.log(logging.DEBUG, 'UppercaseHeaderApp')
        for key,value in environ.items():
            if key.startswith('HTTP_'):
                uppercase = key.upper()
                if uppercase != key:
                    environ[uppercase] = environ.pop(key)
        return self.app(environ, start_response)

class AuthenticationApp (WSGI_Object):
    """WSGI middleware for handling user authentication.
    """
    def __init__(self, app, realm, setting='be-auth', users=None, *args, **kwargs):
        WSGI_Object.__init__(self, *args, **kwargs)
        self.app = app
        self.realm = realm
        self.setting = setting
        self.users = users

    def __call__(self, environ, start_response):
        if self.logger != None:
            self.logger.log(logging.DEBUG, 'AuthenticationApp')
        environ['%s.realm' % self.setting] = self.realm
        try:
            username = self.authenticate(environ)
            environ['%s.user' % self.setting] = username
            environ['%s.user.name' % self.setting] = \
                self.users[username].name
            return self.app(environ, start_response)
        except _Unauthorized, e:
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
        if authorization == None:
            raise _Unauthorized('Authorization required')
        try:
            authmeth,auth = authorization.split(' ',1)
        except ValueError:
            return None
        if 'basic' != authmeth.lower():
            return None # non-basic HTTP authorization not implemented
        auth = auth.strip().decode('base64')
        try:
            username,password = auth.split(':',1)
        except ValueError:
            return None
        if self.authfunc(environ, username, password) == True:
            return username

    def authfunc(self, environ, username, password):
        if not username in self.users:
            return False
        if self.users[username].valid_login(password) == True:
            if self.logger != None:
                self.logger.log(self.log_level,
                    'Authenticated %s' % self.users[username].name)
            return True
        return False

class WSGI_AppObject (WSGI_Object):
    """Useful WSGI utilities for handling data (POST, QUERY) and
    returning responses.
    """
    def __init__(self, *args, **kwargs):
        WSGI_Object.__init__(self, *args, **kwargs)

        # Maximum input we will accept when REQUEST_METHOD is POST
        # 0 ==> unlimited input
        self.maxlen = 0

    def ok_response(self, environ, start_response, content,
                    content_type='application/octet-stream',
                    headers=[]):
        if content == None:
            start_response('200 OK', [])
            return []
        if type(content) == types.UnicodeType:
            content = content.encode('utf-8')
        for i,header in enumerate(headers):
            header_name,header_value = header
            if type(header_value) == types.UnicodeType:
                headers[i] = (header_name, header_value.encode('ISO-8859-1'))
        response = '200 OK'
        content_length = len(content)
        self.log_request(environ, status=response, bytes=content_length)
        start_response('200 OK', [
                ('Content-Type', content_type),
                ('Content-Length', str(content_length)),
                ]+headers)
        if self.is_head(environ) == True:
            return []
        return [content]

    def query_data(self, environ):
        if not environ['REQUEST_METHOD'] in ['GET', 'HEAD']:
            raise _HandlerError(404, 'Not Found')
        return self._parse_query(environ.get('QUERY_STRING', ''))

    def _parse_query(self, query):
        if len(query) == 0:
            return {}
        data = parse_qs(
            query, keep_blank_values=True, strict_parsing=True)
        for k,v in data.items():
            if len(v) == 1:
                data[k] = v[0]
        return data

    def post_data(self, environ):
        if environ['REQUEST_METHOD'] != 'POST':
            raise _HandlerError(404, 'Not Found')
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
            if default == _HandlerError:
                raise _HandlerError(406, 'Missing %s key %s' % (source, key))
            return default
        return data[key]

    def data_get_id(self, data, key='id', default=_HandlerError,
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


class AdminApp (WSGI_AppObject):
    """WSGI middleware for managing users (changing passwords,
    usernames, etc.).
    """
    def __init__(self, app, users=None, url=r'^admin/?', *args, **kwargs):
        WSGI_AppObject.__init__(self, *args, **kwargs)
        self.app = app
        self.users = users
        self.url = url

    def __call__(self, environ, start_response):
        if self.logger != None:
            self.logger.log(logging.DEBUG, 'AdminApp')
        path = environ.get('PATH_INFO', '').lstrip('/')
        match = re.search(self.url, path)
        if match is not None:
            return self.admin(environ, start_response)
        return self.app(environ, start_response)

    def admin(self, environ, start_response):
        if not 'be-auth.user' in environ:
            raise _Unauthenticated(realm=envirion.get('be-auth.realm'))
        uname = environ.get('be-auth.user')
        user = self.users[uname]
        data = self.post_data(environ)
        source = 'post'
        name = self.data_get_string(
            data, 'name', default=None, source=source)
        if name != None:
            self.users[uname].set_name(name)
        password = self.data_get_string(
            data, 'password', default=None, source=source)
        if password != None:
            self.users[uname].set_password(password)
        self.users.save()
        return self.ok_response(environ, start_response, None)

class ServerApp (WSGI_AppObject):
    """WSGI server for a BE Storage instance over HTTP.

    RESTful_ WSGI request handler for serving the
    libbe.storage.http.HTTP backend with GET, POST, and HEAD commands.
    For more information on authentication and REST, see John
    Calcote's `Open Sourcery article`_

    .. _RESTful: http://www.ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm
    .. _Open Sourcery article: http://jcalcote.wordpress.com/2009/08/10/restful-authentication/

    This serves files from a connected storage instance, usually
    a VCS-based repository located on the local machine.

    Notes
    -----

    The GET and HEAD requests are identical except that the HEAD
    request omits the actual content of the file.
    """
    server_version = "BE-server/" + libbe.version.version()

    def __init__(self, storage, notify=False, **kwargs):
        WSGI_AppObject.__init__(self, **kwargs)
        self.storage = storage
        self.notify = notify
        self.http_user_error = 418

        self.urls = [
            (r'^add/?', self.add),
            (r'^exists/?', self.exists),
            (r'^remove/?', self.remove),
            (r'^ancestors/?', self.ancestors),
            (r'^children/?', self.children),
            (r'^get/(.+)', self.get),
            (r'^set/(.+)', self.set),
            (r'^commit/?', self.commit),
            (r'^revision-id/?', self.revision_id),
            (r'^changed/?', self.changed),
            (r'^version/?', self.version),
            ]

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
                    try:
                        return callback(environ, start_response)
                    except libbe.storage.NotReadable, e:
                        raise _HandlerError(403, 'Read permission denied')
                    except libbe.storage.NotWriteable, e:
                        raise _HandlerError(403, 'Write permission denied')
                    except libbe.storage.InvalidID, e:
                        raise _HandlerError(
                            self.http_user_error, 'InvalidID %s' % e)
            raise _HandlerError(404, 'Not Found')
        except _HandlerError, e:
            return self.error(environ, start_response,
                              e.code, e.msg, e.headers)

    # handlers
    def add(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        source = 'post'
        id = self.data_get_id(data, source=source)
        parent = self.data_get_string(
            data, 'parent', default=None, source=source)
        directory = self.data_get_boolean(
            data, 'directory', default=False, source=source)
        self.storage.add(id, parent=parent, directory=directory)
        if self.notify:
            self._notify(environ, 'add', id,
                         [('parent', parent), ('directory', directory)])
        return self.ok_response(environ, start_response, None)

    def exists(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        id = self.data_get_id(data, source=source)
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = str(self.storage.exists(id, revision))
        return self.ok_response(environ, start_response, content)

    def remove(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        source = 'post'
        id = self.data_get_id(data, source=source)
        recursive = self.data_get_boolean(
            data, 'recursive', default=False, source=source)
        if recursive == True:
            self.storage.recursive_remove(id)
        else:
            self.storage.remove(id)
        if self.notify:
            self._notify(environ, 'remove', id, [('recursive', recursive)])
        return self.ok_response(environ, start_response, None)

    def ancestors(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        id = self.data_get_id(data, source=source)
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = '\n'.join(self.storage.ancestors(id, revision))+'\n'
        return self.ok_response(environ, start_response, content)

    def children(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        id = self.data_get_id(data, default=None, source=source)
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = '\n'.join(self.storage.children(id, revision))
        return self.ok_response(environ, start_response, content)

    def get(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        try:
            id = environ['be-server.url_args'][0]
        except:
            raise _HandlerError(404, 'Not Found')
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = self.storage.get(id, revision=revision)
        be_version = self.storage.storage_version(revision)
        return self.ok_response(environ, start_response, content,
                                headers=[('X-BE-Version', be_version)])

    def set(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        try:
            id = environ['be-server.url_args'][0]
        except:
            raise _HandlerError(404, 'Not Found')
        if not 'value' in data:
            raise _HandlerError(406, 'Missing query key value')
        value = data['value']
        self.storage.set(id, value)
        if self.notify:
            self._notify(environ, 'set', id, [('value', value)])
        return self.ok_response(environ, start_response, None)

    def commit(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        if not 'summary' in data:
            raise _HandlerError(406, 'Missing query key summary')
        summary = data['summary']
        if not 'body' in data or data['body'] == 'None':
            data['body'] = None
        body = data['body']
        if not 'allow_empty' in data \
                or data['allow_empty'] == 'True':
            allow_empty = True
        else:
            allow_empty = False
        try:
            revision = self.storage.commit(summary, body, allow_empty)
        except libbe.storage.EmptyCommit, e:
            raise _HandlerError(self.http_user_error, 'EmptyCommit')
        if self.notify:
            self._notify(environ, 'commit', id,
                         [('allow_empty', allow_empty), ('summary', summary),
                          ('body', body)])
        return self.ok_response(environ, start_response, revision)

    def revision_id(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        index = int(self.data_get_string(
            data, 'index', default=_HandlerError, source=source))
        content = self.storage.revision_id(index)
        return self.ok_response(environ, start_response, content)

    def changed(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        add,mod,rem = self.storage.changed(revision)
        content = '\n\n'.join(['\n'.join(p) for p in (add,mod,rem)])
        return self.ok_response(environ, start_response, content)

    def version(self, environ, start_response):
        self.check_login(environ)
        data = self.query_data(environ)
        source = 'query'
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = self.storage.storage_version(revision)
        return self.ok_response(environ, start_response, content)

    # handler utility functions
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


class Serve (libbe.command.Command):
    """Serve bug directory storage over HTTP.

    This allows you to run local `be` commands interfacing with remote
    data, transmitting file reads/writes/etc. over the network.

    :class:`~libbe.command.base.Command` wrapper around
    :class:`ServerApp`.
    """

    name = 'serve'

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
        users = Users(params['auth'])
        users.load()
        app = ServerApp(
            storage=storage, notify=params['notify'], logger=self.logger)
        if params['auth'] != None:
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
        if params['ssl'] == True:
            details['protocol'] = 'HTTPS'
            if cherrypy == None:
                raise libbe.command.UserError, \
                    '--ssl requires the cherrypy module'
            app = ExceptionApp(app, logger=self.logger)
            server = cherrypy.wsgiserver.CherryPyWSGIServer(
                (params['host'], params['port']), app)
            #server.throw_errors = True
            #server.show_tracebacks = True
            private_key,certificate = get_cert_filenames(
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
                params['host'], params['port'], app)
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

    $ be serve

And in another terminal (or after backgrounding the server)::

    $ be --repo http://localhost:8000/ list

If you bind your server to a public interface, take a look at the
``--read-only`` option or the combined ``--ssl --auth FILE``
options so other people can't mess with your repository.  If you do use
authentication, you'll need to send in your username and password with,
for example::

    $ be --repo http://username:password@localhost:8000/ list
"""

def random_string(length=256):
    if os.path.exists(os.path.join('dev', 'urandom')):
        return open("/dev/urandom").read(length)
    else:
        import array
        from random import randint
        d = array.array('B')
        for i in xrange(1000000):
            d.append(randint(0,255))
        return d.tostring()

if libbe.TESTING == True:
    class WSGITestCase (unittest.TestCase):
        def setUp(self):
            self.logstream = StringIO.StringIO()
            self.logger = logging.getLogger('be-serve-test')
            console = logging.StreamHandler(self.logstream)
            console.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(console)
            self.logger.propagate = False
            console.setLevel(logging.INFO)
            self.logger.setLevel(logging.INFO)
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
                   scheme='http', environ={}):
            env = copy.copy(self.default_environ)
            env['PATH_INFO'] = path
            env['REQUEST_METHOD'] = method
            env['scheme'] = scheme
            if data != None:
                enc_data = urllib.urlencode(data)
                if method == 'POST':
                    env['CONTENT_LENGTH'] = len(enc_data)
                    env['wsgi.input'] = StringIO.StringIO(enc_data)
                else:
                    assert method in ['GET', 'HEAD'], method
                    env['QUERY_STRING'] = enc_data
            for key,value in environ.items():
                env[key] = value
            return ''.join(app(env, self.start_response))
        def start_response(self, status, response_headers, exc_info=None):
            self.status = status
            self.response_headers = response_headers
            self.exc_info = exc_info

    class WSGI_ObjectTestCase (WSGITestCase):
        def setUp(self):
            WSGITestCase.setUp(self)
            self.app = WSGI_Object(self.logger)
        def test_error(self):
            contents = self.app.error(
                environ=self.default_environ,
                start_response=self.start_response,
                error=123,
                message='Dummy Error',
                headers=[('X-Dummy-Header','Dummy Value')])
            self.failUnless(contents == ['Dummy Error'], contents)
            self.failUnless(self.status == '123 Dummy Error', self.status)
            self.failUnless(self.response_headers == [
                    ('Content-Type','text/plain'),
                    ('X-Dummy-Header','Dummy Value')],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
        def test_log_request(self):
            self.app.log_request(
                environ=self.default_environ, status='-1 OK', bytes=123)
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
            self.app = AdminApp(
                child_app, users=self.users, logger=self.logger)
            self.app = AuthenticationApp(
                self.app, realm='Dummy Realm', users=self.users,
                logger=self.logger)
            self.app = UppercaseHeaderApp(self.app, logger=self.logger)
        def basic_auth(self, uname, password):
            """HTTP basic authorization string"""
            return 'Basic %s' % \
                ('%s:%s' % (uname, password)).encode('base64')
        def test_new_name(self):
            self.getURL(
                self.app, '/admin/', method='POST',
                data={'name':'Prince Al'},
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
                data={'password':'New Pass'},
                environ={'HTTP_Authorization':
                             self.basic_auth('Aladdin', 'open sesame')})
            self.failUnless(self.status == '200 OK', self.status)
            self.failUnless(self.response_headers == [],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
            self.failUnless(self.users['Aladdin'].passhash == \
                            self.users['Aladdin'].hash('New Pass'),
                            self.users['Aladdin'].passhash)
            self.failUnless(self.users.changed == True,
                            self.users.changed)
        def test_guest_name(self):
            self.getURL(
                self.app, '/admin/', method='POST',
                data={'name':'SPAM'},
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
                data={'password':'SPAM'},
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

    class ServerAppTestCase (WSGITestCase):
        def setUp(self):
            WSGITestCase.setUp(self)
            self.bd = libbe.bugdir.SimpleBugDir(memory=False)
            self.app = ServerApp(self.bd.storage, logger=self.logger)
        def tearDown(self):
            self.bd.cleanup()
            WSGITestCase.tearDown(self)
        def test_add_get(self):
            self.getURL(self.app, '/add/', method='GET')
            self.failUnless(self.status.startswith('404 '), self.status)
            self.failUnless(self.response_headers == [
                    ('Content-Type', 'text/plain')],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
        def test_add_post(self):
            self.getURL(self.app, '/add/', method='POST',
                        data={'id':'123456', 'parent':'abc123',
                              'directory':'True'})
            self.failUnless(self.status == '200 OK', self.status)
            self.failUnless(self.response_headers == [],
                            self.response_headers)
            self.failUnless(self.exc_info == None, self.exc_info)
        # Note: other methods tested in libbe.storage.http

        # TODO: integration tests on Serve?

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])


# The following certificate-creation code is adapted From pyOpenSSL's
# examples.

def get_cert_filenames(server_name, autogenerate=True, logger=None):
    """
    Generate private key and certification filenames.
    get_cert_filenames(server_name) -> (pkey_filename, cert_filename)
    """
    pkey_file = '%s.pkey' % server_name
    cert_file = '%s.cert' % server_name
    if autogenerate == True:
        for file in [pkey_file, cert_file]:
            if not os.path.exists(file):
                make_certs(server_name, logger)
    return (pkey_file, cert_file)

def createKeyPair(type, bits):
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

def createCertRequest(pkey, digest="md5", **name):
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

def createCertificate(req, (issuerCert, issuerKey), serial, (notBefore, notAfter), digest="md5"):
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

def make_certs(server_name, logger=None) :
    """Generate private key and certification files.

    `mk_certs(server_name) -> (pkey_filename, cert_filename)`
    """
    if OpenSSL == None:
        raise libbe.command.UserError, \
            'SSL certificate generation requires the OpenSSL module'
    pkey_file,cert_file = get_cert_filenames(
        server_name, autogenerate=False)
    if logger != None:
        logger.log(logger._server_level,
                   'Generating certificates', pkey_file, cert_file)
    cakey = createKeyPair(OpenSSL.crypto.TYPE_RSA, 1024)
    careq = createCertRequest(cakey, CN='Certificate Authority')
    cacert = createCertificate(
        careq, (careq, cakey), 0, (0, 60*60*24*365*5)) # five years
    open(pkey_file, 'w').write(OpenSSL.crypto.dump_privatekey(
            OpenSSL.crypto.FILETYPE_PEM, cakey))
    open(cert_file, 'w').write(OpenSSL.crypto.dump_certificate(
            OpenSSL.crypto.FILETYPE_PEM, cacert))
