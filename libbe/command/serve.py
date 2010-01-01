# Copyright (C) 2005-2010 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
#                         W. Trevor King <wking@drexel.edu>
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

import libbe
import libbe.command
import libbe.command.util
import libbe.version

HTTP_USER_ERROR = 418
STORAGE = None
COMMAND = None

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

        if path == ['children']:
            content,ctype = self.handle_children(data)
        elif len(path) > 1 and path[0] == 'get':
            content,ctype = self.handle_get('/'.join(path[1:]), data)
        elif path == ['revision-id']:
            content,ctype = self.handle_revision_id(data)
        elif path == ['version']:
            content,ctype = self.handle_version(data)
        else:
            self.send_error(400, 'File not found')
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
        post_data = self.rfile.read()
        print 'got post', post_data
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
        if content != None:
            self.send_header('Content-type', ctype)
            self.send_header('Content-Length', len(content))
        self.end_headers()
        if content != None:
            self.wfile.write(content)

    def handle_add(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            return None
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
        self.s.add(id, parent, directory)
        self.send_response(200)
        return (None,None)

    def handle_remove(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            return None
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

    def handle_children(self, data):
        if not 'id' in data:
            self.send_error(406, 'Missing query key id')
            return None
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
        try:
            content = self.s.get(id, revision)
        except libbe.storage.InvalidID, e:
            self.send_error(HTTP_USER_ERROR, 'InvalidID %s' % e)
            return None
        be_version = self.s.storage_version(revision)
        ctype = 'application/octet-stream'
        self.send_response(200)
        self.send_header('X-BE-Version', be_version)
        return content,ctype

    def handle_set(self, id, data):
        if not 'value' in data:
            self.send_error(406, 'Missing query key value')
            return None
        self.s.set(id, value)
        self.send_response(200)
        return None

    def handle_commit(self, data):
        if not 'summary' in data:
            self.send_error(406, 'Missing query key summary')
            return None
        summary = data['summary']
        if not body in data or data['body'] == 'None':
            data['body'] = None
        body = data['body']
        if not allow_empty in data \
                or data['allow_empty'] == 'True':
            allow_empty = True
        else:
            allow_empty = False
        self.s.commit(summary, body, allow_empty)
        self.send_response(200)
        return None

    def handle_revision_id(self, data):
        if not 'index' in data:
            self.send_error(406, 'Missing query key index')
            return None
        index = int(data['index'])
        content = self.s.revision_id(index)
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
        data = urlparse.parse_qs(
            query, keep_blank_values=True, strict_parsing=True)
        for k,v in data.items():
            if len(v) == 1:
                data[k] = v[0]
        return data

    def parse_post(self, post):
        return self.parse_query(post)

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
                ])

    def _run(self, **params):
        global STORAGE, COMMAND
        STORAGE = self._get_storage()
        COMMAND = self
        server_class = server.HTTPServer
        handler_class = BERequestHandler
        server_address = (params['host'], params['port'])
        httpd = server_class(server_address, handler_class)
        sa = httpd.socket.getsockname()
        print >> self.stdout, 'Serving HTTP on', sa[0], 'port', sa[1], '...'
        print >> self.stdout, 'BE repository', STORAGE.repo
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        print >> self.stdout, 'Closing server'
        httpd.server_close()

    def _long_help(self):
        return """
This command lists bugs.  Normally it prints a short string like
  576:om: Allow attachments
Where
  576   the bug id
  o     the bug status is 'open' (first letter)
  m     the bug severity is 'minor' (first letter)
  Allo... the bug summary string

You can optionally (-u) print only the bug ids.

There are several criteria that you can filter by:
  * status
  * severity
  * assigned (who the bug is assigned to)
Allowed values for each criterion may be given in a comma seperated
list.  The special string "all" may be used with any of these options
to match all values of the criterion.  As with the --status and
--severity options for `be depend`, starting the list with a minus
sign makes your selections a blacklist instead of the default
whitelist.

status
  %s
severity
  %s
assigned
  free form, with the string '-' being a shortcut for yourself.

In addition, there are some shortcut options that set boolean flags.
The boolean options are ignored if the matching string option is used.
"""
