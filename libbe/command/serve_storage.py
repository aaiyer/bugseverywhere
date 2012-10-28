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

"""Define the :py:class:`Serve` serving BE Storage over HTTP.

See Also
--------
:py:mod:`libbe.storage.http` : the associated client
"""

import logging
import os.path

import libbe
import libbe.command
import libbe.command.util
import libbe.util.http
import libbe.util.subproc
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
    import libbe.util.wsgi


class ServerApp (libbe.util.wsgi.WSGI_AppObject,
                 libbe.util.wsgi.WSGI_DataObject):
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
    server_version = 'BE-storage-server/' + libbe.version.version()

    def __init__(self, storage=None, notify=False, **kwargs):
        super(ServerApp, self).__init__(
            urls=[
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
                ],
            **kwargs)
        self.storage = storage
        self.notify = notify

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
            raise libbe.util.wsgi.HandlerError(404, 'Not Found')
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
            raise libbe.util.wsgi.HandlerError(404, 'Not Found')
        if not 'value' in data:
            raise libbe.util.wsgi.HandlerError(406, 'Missing query key value')
        value = data['value']
        self.storage.set(id, value)
        if self.notify:
            self._notify(environ, 'set', id, [('value', value)])
        return self.ok_response(environ, start_response, None)

    def commit(self, environ, start_response):
        self.check_login(environ)
        data = self.post_data(environ)
        if not 'summary' in data:
            raise libbe.util.wsgi.HandlerError(
                406, 'Missing query key summary')
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
            raise libbe.util.wsgi.HandlerError(
                libbe.util.http.HTTP_USER_ERROR, 'EmptyCommit')
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
            data, 'index', default=libbe.util.wsgi.HandlerError,
            source=source))
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
        if user is not None:  # we're running under AuthenticationApp
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


class ServeStorage (libbe.util.wsgi.ServerCommand):
    """Serve bug directory storage over HTTP.

    This allows you to run local `be` commands interfacing with remote
    data, transmitting file reads/writes/etc. over the network.

    :py:class:`~libbe.command.base.Command` wrapper around
    :py:class:`ServerApp`.
    """

    name = 'serve-storage'

    def _get_app(self, logger, storage, **kwargs):
        return ServerApp(
            logger=logger, storage=storage, notify=kwargs.get('notify', False))

    def _long_help(self):
        return """
Example usage::

    $ be serve-storage

And in another terminal (or after backgrounding the server)::

    $ be --repo http://localhost:8000/ list

If you bind your server to a public interface, take a look at the
``--read-only`` option or the combined ``--ssl --auth FILE``
options so other people can't mess with your repository.  If you do use
authentication, you'll need to send in your username and password::

    $ be --repo http://username:password@localhost:8000/ list
"""


# alias for libbe.command.base.get_command_class()
Serve_storage = ServeStorage


if libbe.TESTING:
    class ServerAppTestCase (libbe.util.wsgi.WSGITestCase):
        def setUp(self):
            super(ServerAppTestCase, self).setUp()
            self.bd = libbe.bugdir.SimpleBugDir(memory=False)
            self.app = ServerApp(self.bd.storage, logger=self.logger)

        def tearDown(self):
            self.bd.cleanup()
            super(ServerAppTestCase, self).tearDown()

        def test_add_get(self):
            try:
                self.getURL(self.app, '/add/', method='GET')
            except libbe.util.wsgi.HandlerError as e:
                self.failUnless(e.code == 404, e)
            else:
                self.fail('GET /add/ did not raise 404')

        def test_add_post(self):
            self.getURL(self.app, '/add/', method='POST',
                        data_dict={'id':'123456', 'parent':'abc123',
                                   'directory':'True'})
            self.failUnless(self.status == '200 OK', self.status)
            self.failUnless(self.response_headers == [],
                            self.response_headers)
            self.failUnless(self.exc_info is None, self.exc_info)
        # Note: other methods tested in libbe.storage.http

        # TODO: integration tests on Serve?

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
