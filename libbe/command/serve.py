# Copyright (C) 2010 W. Trevor King <wking@drexel.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import posixpath
import re
import types
import urllib
import urlparse
import wsgiref.simple_server
try:
    # Python >= 2.6
    from urlparse import parse_qs
except ImportError:
    # Python <= 2.5
    from cgi import parse_qs

import libbe
import libbe.command
import libbe.command.util
import libbe.version

if libbe.TESTING == True:
    import doctest
    import StringIO
    import unittest
    import wsgiref.validate

    import libbe.bugdir

class _HandlerError (Exception):
    def __init__(self, code, msg):
        Exception.__init__(self, '%d %s' % (code, msg))
        self.code = code
        self.msg = msg

class ServerApp (object):
    """Simple WSGI request handler for serving the
    libbe.storage.http.HTTP backend with GET, POST, and HEAD commands.

    This serves files from a connected storage instance, usually
    a VCS-based repository located on the local machine.

    The GET and HEAD requests are identical except that the HEAD
    request omits the actual content of the file.

    For details on WGSI, see `PEP 333`_

    .. PEP 333: http://www.python.org/dev/peps/pep-0333/
    """
    server_version = "BE-server/" + libbe.version.version()

    def __init__(self, command, storage):
        self.command = command
        self.storage = storage
        self.http_user_error = 418

        # Maximum input we will accept when REQUEST_METHOD is POST
        # 0 ==> unlimited input
        self.maxlen = 0

        self.urls = [(r'^add/(.+)', self.add),
                     (r'^remove/(.+)', self.remove),
                     (r'^ancestors/?', self.ancestors),
                     (r'^children/?', self.children),
                     (r'^get/(.+)', self.get),
                     (r'^set/(.+)', self.set),
                     (r'^commit/(.+)', self.commit),
                     (r'^revision-id/?', self.revision_id),
                     (r'^changed/?', self.changed),
                     (r'^version/?', self.version),
                     ]

    def __call__(self, environ, start_response):
        """The main WSGI application.  Dispatch the current request to
        the functions from above and store the regular expression
        captures in the WSGI environment as `be-server.url_args` so
        that the functions from above can access the url placeholders.
        """
        # start_response() is a callback for setting response headers
        #   start_response(status, response_headers, exc_info=None)
        # status is an HTTP status string (e.g., "200 OK").
        # response_headers is a list of 2-tuples, the HTTP headers in
        # key-value format.
        # exc_info is used in exception handling.
        #
        # The application function then returns an iterable of body chunks.

        # URL dispatcher from Armin Ronacher's "Getting Started with WSGI"
        #   http://lucumr.pocoo.org/2007/5/21/getting-started-with-wsgi
        self.log_request(environ)
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
            return self.error(start_response, e.code, e.msg)

    def log_request(self, environ):
        print >> self.command.stdout, \
            environ.get('REQUEST_METHOD'), environ.get('PATH_INFO', '')

    def error(self, start_response, error, message):
        """Called if no URL matches."""
        start_response('%d %s' % (error, message.upper()),
                       [('Content-Type', 'text/plain')])
        return [message]        

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
        start_response('200 OK', [
                ('Content-Type', content_type),
                ('Content-Length', str(len(content))),
                ]+headers)
        if self.is_head(environ) == True:
            return []
        return [content]

    def add(self, environ, start_response):
        data = self.post_data(environ)
        source = 'post'
        id = self.data_get_id(data, source=source)
        parent = self.data_get_string(
            data, 'parent', default=None, source=source)
        directory = self.data_get_boolean(
            data, 'directory', default=False, souce=source)
        self.storage.add(id, parent=parent, directory=directory)
        return self.ok_response(environ, start_response, None)

    def remove(self, environ, start_response):
        data = self.post_data(environ)
        source = 'post'
        id = self.data_get_id(data, source=source)
        recursive = self.data_get_boolean(
            data, 'recursive', default=False, souce=source)
        if recursive == True:
            self.storage.recursive_remove(id)
        else:
            self.storage.remove(id)
        return self.ok_response(environ, start_response, None)

    def ancestors(self, environ, start_response):
        data = self.query_data(environ)
        source = 'query'
        id = self.data_get_id(data, source=source)
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = '\n'.join(self.storage.ancestors(id, revision))+'\n'
        return self.ok_response(environ, start_response, content)

    def children(self, environ, start_response):
        data = self.query_data(environ)
        source = 'query'
        id = self.data_get_id(data, default=None, source=source)
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = '\n'.join(self.storage.children(id, revision))
        return self.ok_response(environ, start_response, content)

    def get(self, environ, start_response):
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
        data = self.post_data(environ)
        try:
            id = environ['be-server.url_args'][0]
        except:
            raise _HandlerError(404, 'Not Found')
        if not 'value' in data:
            raise _HandlerError(406, 'Missing query key value')
        value = data['value']
        self.storage.set(id, value)
        return self.ok_response(environ, start_response, None)

    def commit(self, environ, start_response):
        data = self.post_data(environ)
        if not 'summary' in data:
            return self.error(start_response, 406, 'Missing query key summary')
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
            self.storage.commit(summary, body, allow_empty)
        except libbe.storage.EmptyCommit, e:
            return self.error(
                start_response, self.http_user_error, 'EmptyCommit')
        return self.ok_response(environ, start_response, None)

    def revision_id(self, environ, start_response):
        data = self.query_data(environ)
        source = 'query'
        index = self.data_get_string(
            data, 'index', default=_HandlerError, source=source)
        content = self.storage.revision_id(index)
        return self.ok_response(environ, start_response, content)

    def changed(self, environ, start_response):
        data = self.query_data(environ)
        source = 'query'
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        add,mod,rem = self.storage.changed(revision)
        content = '\n\n'.join(['\n'.join(p) for p in (add,mod,rem)])
        return self.ok_response(environ, start_response, content)

    def version(self, environ, start_response):
        data = self.query_data(environ)
        source = 'query'
        revision = self.data_get_string(
            data, 'revision', default=None, source=source)
        content = self.storage.storage_version(revision)
        return self.ok_response(environ, start_response, content)

    def parse_path(self, path):
        """Parse a url to path,query,fragment parts."""
        # abandon query parameters
        scheme,netloc,path,query,fragment = urlparse.urlsplit(path)
        path = posixpath.normpath(urllib.unquote(path)).split('/')
        assert path[0] == '', path
        path = path[1:]
        return (path,query,fragment)

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
        val = self.data_get_string(self, data, key, default, source)
        if val == 'True':
            return True
        elif val == 'False':
            return False
        return val

    def is_head(self, environ):
        return environ['REQUEST_METHOD'] == 'HEAD'


class Serve (libbe.command.Command):
    """Serve a Storage backend for the HTTP storage client

    >>> raise NotImplementedError, "Serve tests not yet implemented"
    >>> import sys
    >>> import libbe.bugdir
    >>> import libbe.command.list
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = libbe.command.list.List(ui=ui)

    >>> ret = ui.run(cmd)
    abc/a:om: Bug A
    >>> ret = ui.run(cmd, {'status':'closed'})
    abc/b:cm: Bug B
    >>> bd.storage.writeable
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
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
                ])

    def _run(self, **params):
        storage = self._get_storage()
        if params['read-only'] == True:
            writeable = storage.writeable
            storage.writeable = False
        app = ServerApp(command=self, storage=storage)
        httpd = wsgiref.simple_server.make_server(
            params['host'], params['port'], app)
        sa = httpd.socket.getsockname()
        print >> self.stdout, 'Serving HTTP on', sa[0], 'port', sa[1], '...'
        print >> self.stdout, 'BE repository', storage.repo
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        print >> self.stdout, 'Closing server'
        httpd.server_close()
        if params['read-only'] == True:
            storage.writeable = writeable

    def _long_help(self):
        return """
Example usage:
  $ be serve
And in another terminal (or after backgrounding the server)
  $ be --repo http://localhost:8000 list

If you bind your server to a public interface, you should probably use
the --read-only option so other people can't mess with your
repository.
"""

if libbe.TESTING == True:
    class ServerAppTestCase (unittest.TestCase):
        def setUp(self):
            self.bd = libbe.bugdir.SimpleBugDir(memory=False)
            storage = self.bd.storage
            command = object()
            command.stdout = StringIO.StringIO()
            command.stdout.encoding = 'utf-8'
            self.app = ServerApp(command=self, storage=storage)
        def tearDown(self):
            self.bd.cleanup()
        def testValidWSGI(self):
            wsgiref.validate.validator(self.app)
            pass

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
