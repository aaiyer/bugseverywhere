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

import os.path
import posixpath
import re
import sys
import types
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

        self.urls = [
            (r'^add/(.+)', self.add),
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
        self.log_request(environ)
        # URL dispatcher from Armin Ronacher's "Getting Started with WSGI"
        #   http://lucumr.pocoo.org/2007/5/21/getting-started-with-wsgi
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

    # handlers
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

    # handler utility functions
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
                libbe.command.Option(name='ssl',
                    help='Use CherryPy to serve HTTPS (HTTP over SSL/TLS)'),
                ])

    def _run(self, **params):
        storage = self._get_storage()
        if params['read-only'] == True:
            writeable = storage.writeable
            storage.writeable = False
        if params['host'] == '':
            params['host'] = 'localhost'
        app = ServerApp(command=self, storage=storage)
        server,details = self._get_server(params, app)
        details['repo'] = storage.repo
        try:
            self._start_server(params, server, details)
        except KeyboardInterrupt:
            pass
        self._stop_server(params, server)
        if params['read-only'] == True:
            storage.writeable = writeable

    def _get_server(self, params, app):
        details = {'port':params['port']}
        if params['ssl'] == True:
            details['protocol'] = 'HTTPS'
            if cherrypy == None:
                raise libbe.command.UserError, \
                    '--ssl requires the cherrypy module'
            server = cherrypy.wsgiserver.CherryPyWSGIServer(
                (params['host'], params['port']), app)
            private_key,certificate = get_cert_filenames('be-server')
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
        print >> self.stdout, \
            'Serving %(protocol)s on %(socket-name)s port %(port)s ...' \
            % details
        print >> self.stdout, 'BE repository %(repo)s' % details
        if params['ssl'] == True:
            server.start()
        else:
            server.serve_forever()

    def _stop_server(self, params, server):
        print >> self.stdout, 'Closing server'
        if params['ssl'] == True:
            server.stop()
        else:
            server.server_close()

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


# The following certificate-creation code is adapted From pyOpenSSL's
# examples.

def get_cert_filenames(server_name, autogenerate=True):
    """
    Generate private key and certification filenames.
    get_cert_filenames(server_name) -> (pkey_filename, cert_filename)
    """
    pkey_file = '%s.pkey' % server_name
    cert_file = '%s.cert' % server_name
    if autogenerate == True:
        for file in [pkey_file, cert_file]:
            if not os.path.exists(file):
                make_certs(server_name)
    return (pkey_file, cert_file)

def createKeyPair(type, bits):
    """
    Create a public/private key pair.

    Arguments: type - Key type, must be one of TYPE_RSA and TYPE_DSA
               bits - Number of bits to use in the key
    Returns:   The public/private key pair in a PKey object
    """
    pkey = OpenSSL.crypto.PKey()
    pkey.generate_key(type, bits)
    return pkey

def createCertRequest(pkey, digest="md5", **name):
    """
    Create a certificate request.

    Arguments: pkey   - The key to associate with the request
               digest - Digestion method to use for signing, default is md5
               **name - The name of the subject of the request, possible
                        arguments are:
                          C     - Country name
                          ST    - State or province name
                          L     - Locality name
                          O     - Organization name
                          OU    - Organizational unit name
                          CN    - Common name
                          emailAddress - E-mail address
    Returns:   The certificate request in an X509Req object
    """
    req = OpenSSL.crypto.X509Req()
    subj = req.get_subject()

    for (key,value) in name.items():
        setattr(subj, key, value)

    req.set_pubkey(pkey)
    req.sign(pkey, digest)
    return req

def createCertificate(req, (issuerCert, issuerKey), serial, (notBefore, notAfter), digest="md5"):
    """
    Generate a certificate given a certificate request.

    Arguments: req        - Certificate reqeust to use
               issuerCert - The certificate of the issuer
               issuerKey  - The private key of the issuer
               serial     - Serial number for the certificate
               notBefore  - Timestamp (relative to now) when the certificate
                            starts being valid
               notAfter   - Timestamp (relative to now) when the certificate
                            stops being valid
               digest     - Digest method to use for signing, default is md5
    Returns:   The signed certificate in an X509 object
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

def make_certs(server_name) :
    """
    Generate private key and certification files.
    mk_certs(server_name) -> (pkey_filename, cert_filename)
    """
    if OpenSSL == None:
        raise libbe.command.UserError, \
            'SSL certificate generation requires the OpenSSL module'
    pkey_file,cert_file = get_cert_filenames(
        server_name, autogenerate=False)
    print >> sys.stderr, 'Generating certificates', pkey_file, cert_file
    cakey = createKeyPair(OpenSSL.crypto.TYPE_RSA, 1024)
    careq = createCertRequest(cakey, CN='Certificate Authority')
    cacert = createCertificate(
        careq, (careq, cakey), 0, (0, 60*60*24*365*5)) # five years
    open(pkey_file, 'w').write(OpenSSL.crypto.dump_privatekey(
            OpenSSL.crypto.FILETYPE_PEM, cakey))
    open(cert_file, 'w').write(OpenSSL.crypto.dump_certificate(
            OpenSSL.crypto.FILETYPE_PEM, cacert))
