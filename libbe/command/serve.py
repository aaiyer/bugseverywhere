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

import BaseHTTPServer as server
import posixpath
import urllib
import urlparse

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

HTTP_USER_ERROR = 418
STORAGE = None
COMMAND = None

# Maximum input we will accept when REQUEST_METHOD is POST
# 0 ==> unlimited input
MAXLEN = 0


class _HandlerError (Exception):
    pass

class BERequestHandler (server.BaseHTTPRequestHandler):
    """Simple HTTP request handler for serving the
    libbe.storage.http.HTTP backend with GET, POST, and HEAD commands.

    This serves files from a connected storage instance, usually
    a VCS-based repository located on the local machine.

    The GET and HEAD requests are identical except that the HEAD
    request omits the actual content of the file.
    """

    server_version = "BE-server/" + libbe.version.version()

    def do_GET(self, head=False):
        """Serve a GET (or HEAD, if head==True) request."""
        self.s = STORAGE
        self.c = COMMAND
        request = 'GET'
        if head == True:
            request = 'HEAD'
        self.log_request(request)
        path,query,fragment = self.parse_path(self.path)
        if fragment != '':
            self.send_error(406,
                '%s implementation does not allow fragment URL portion'
                % request)
            return None
        data = self.parse_query(query)

        try:
            if path == ['ancestors']:
                content,ctype = self.handle_ancestors(data)
            elif path == ['children']:
                content,ctype = self.handle_children(data)
            elif len(path) > 1 and path[0] == 'get':
                content,ctype = self.handle_get('/'.join(path[1:]), data)
            elif path == ['revision-id']:
                content,ctype = self.handle_revision_id(data)
            elif path == ['changed']:
                content,ctype = self.handle_changed(data)
            elif path == ['version']:
                content,ctype = self.handle_version(data)
            else:
                self.send_error(400, 'File not found')
                return None
        except libbe.storage.NotReadable, e:
            self.send_error(403, 'Read permission denied')
            return None
        except libbe.storage.InvalidID, e:
            self.send_error(HTTP_USER_ERROR, 'InvalidID %s' % e)
            return None
        except _HandlerError:
            return None

        if content != None:
            self.send_header('Content-type', ctype)
            self.send_header('Content-Length', len(content))
        self.end_headers()
        if request == 'GET' and content != None:
            self.wfile.write(content)

    def do_HEAD(self):
        """Serve a HEAD request."""
        return self.do_GET(head=True)

    def do_POST(self):
        """Serve a POST request."""
        self.s = STORAGE
        self.c = COMMAND
        self.log_request('POST')
        post_data = self.read_post_data()
        data = self.parse_post(post_data)
        path,query,fragment = self.parse_path(self.path)
        if query != '':
            self.send_error(
                406, 'POST implementation does not allow query URL portion')
            return None
        if fragment != '':
            self.send_error(
                406, 'POST implementation does not allow fragment URL portion')
            return None
        try:
            if path == ['add']:
                content,ctype = self.handle_add(data)
            elif path == ['remove']:
                content,ctype = self.handle_remove(data)
            elif len(path) > 1 and path[0] == 'set':
                content,ctype = self.handle_set('/'.join(path[1:]), data)
            elif path == ['commit']:
                content,ctype = self.handle_commit(data)
            else:
                self.send_error(400, 'File not found')
                return None
        except libbe.storage.NotWriteable, e:
            self.send_error(403, 'Write permission denied')
            return None
        except libbe.storage.InvalidID, e:
            self.send_error(HTTP_USER_ERROR, 'InvalidID %s' % e)
            return None
        except _HandlerError:
            return None
        if content != None:
            self.send_header('Content-type', ctype)
            self.send_header('Content-Length', len(content))
        self.end_headers()
        if content != None:
            self.wfile.write(content)

    def handle_add(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            raise _HandlerError()
        elif data['id'] == 'None':
            data['id'] = None
        id = data['id']
        if not 'parent' in data or data['parent'] == None:
            data['parent'] = None
        parent = data['parent']
        if not 'directory' in data:
            directory = False
        elif data['directory'] == 'True':
            directory = True
        else:
            directory = False
        self.s.add(id, parent=parent, directory=directory)
        self.send_response(200)
        return (None,None)

    def handle_remove(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            raise _HandlerError()
        elif data['id'] == 'None':
            data['id'] = None
        id = data['id']
        if not 'recursive' in data:
            recursive = False
        elif data['recursive'] == 'True':
            recursive = True
        else:
            recursive = False
        if recursive == True:
            self.s.recursive_remove(id)
        else:
            self.s.remove(id)
        self.send_response(200)
        return (None,None)

    def handle_ancestors(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            raise _HandlerError()
        elif data['id'] == 'None':
            data['id'] = None
        id = data['id']
        if not 'revision' in data or data['revision'] == 'None':
            data['revision'] = None
        revision = data['revision']
        content = '\n'.join(self.s.ancestors(id, revision))
        ctype = 'application/octet-stream'
        self.send_response(200)
        return content,ctype

    def handle_children(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            raise _HandlerError()
        elif data['id'] == 'None':
            data['id'] = None
        id = data['id']
        if not 'revision' in data or data['revision'] == 'None':
            data['revision'] = None
        revision = data['revision']
        content = '\n'.join(self.s.children(id, revision))
        ctype = 'application/octet-stream'
        self.send_response(200)
        return content,ctype

    def handle_get(self, id, data):
        if not 'revision' in data or data['revision'] == 'None':
            data['revision'] = None
        revision = data['revision']
        content = self.s.get(id, revision=revision)
        be_version = self.s.storage_version(revision)
        ctype = 'application/octet-stream'
        self.send_response(200)
        self.send_header('X-BE-Version', be_version)
        return content,ctype

    def handle_set(self, id, data):
        if not 'value' in data:
            self.send_error(406, 'Missing query key value')
            raise _HandlerError()
        value = data['value']
        self.s.set(id, value)
        self.send_response(200)
        return (None,None)

    def handle_commit(self, data):
        if not 'summary' in data:
            self.send_error(406, 'Missing query key summary')
            raise _HandlerError()
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
            self.s.commit(summary, body, allow_empty)
        except libbe.storage.EmptyCommit, e:
            self.send_error(HTTP_USER_ERROR, 'EmptyCommit')
            raise _HandlerError()
        self.send_response(200)
        return (None,None)

    def handle_revision_id(self, data):
        if not 'index' in data:
            self.send_error(406, 'Missing query key index')
            raise _HandlerError()
        index = int(data['index'])
        content = self.s.revision_id(index)
        ctype = 'application/octet-stream'
        self.send_response(200)
        return content,ctype

    def handle_changed(self, data):
        if not 'revision' in data or data['revision'] == 'None':
            data['revision'] = None
        revision = data['revision']
        add,mod,rem = self.s.changed(revision)
        content = '\n\n'.join(['\n'.join(p) for p in (add,mod,rem)])
        ctype = 'application/octet-stream'
        self.send_response(200)
        return content,ctype

    def handle_version(self, data):
        if not 'revision' in data or data['revision'] == 'None':
            data['revision'] = None
        revision = data['revision']
        content = self.s.storage_version(revision)
        ctype = 'application/octet-stream'
        self.send_response(200)
        return content,ctype

    def parse_path(self, path):
        """Parse a url to path,query,fragment parts."""
        # abandon query parameters
        scheme,netloc,path,query,fragment = urlparse.urlsplit(path)
        path = posixpath.normpath(urllib.unquote(path)).split('/')
        assert path[0] == '', path
        path = path[1:]
        return (path,query,fragment)

    def log_request(self, request):
        print >> self.c.stdout, request, self.path

    def parse_query(self, query):
        if len(query) == 0:
            return {}
        data = parse_qs(
            query, keep_blank_values=True, strict_parsing=True)
        for k,v in data.items():
            if len(v) == 1:
                data[k] = v[0]
        return data

    def parse_post(self, post):
        return self.parse_query(post)

    def read_post_data(self):
        clen = -1
        if 'content-length' in self.headers:
            try:
                clen = int(self.headers['content-length'])
            except ValueError:
                pass
            if MAXLEN > 0 and clen > MAXLEN:
                raise ValueError, 'Maximum content length exceeded'
        post_data = self.rfile.read(clen)
        return post_data
        

class Serve (libbe.command.Command):
    """Serve a Storage backend for the HTTP storage client

    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = List(ui=ui)

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
        global STORAGE, COMMAND
        COMMAND = self
        STORAGE = self._get_storage()
        if params['read-only'] == True:
            writeable = STORAGE.writeable
            STORAGE.writeable = False
        server_class = server.HTTPServer
        handler_class = BERequestHandler
        httpd = server_class(
            (params['host'], params['port']), handler_class)
        sa = httpd.socket.getsockname()
        print >> self.stdout, 'Serving HTTP on', sa[0], 'port', sa[1], '...'
        print >> self.stdout, 'BE repository', STORAGE.repo
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        print >> self.stdout, 'Closing server'
        httpd.server_close()
        if params['read-only'] == True:
            STORAGE.writeable = writeable

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
