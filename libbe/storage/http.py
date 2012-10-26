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

"""Define an HTTP-based :py:class:`~libbe.storage.base.VersionedStorage`
implementation.

See Also
--------
:py:mod:`libbe.command.serve_storage` : the associated server
"""

from __future__ import absolute_import
import sys
import urllib
import urlparse

import libbe
import libbe.version
import libbe.util.http
from libbe.util.http import HTTP_VALID, HTTP_USER_ERROR
from . import base

from libbe import TESTING

if TESTING == True:
    import copy
    import doctest
    import StringIO
    import unittest

    import libbe.bugdir
    import libbe.command.serve_storage
    import libbe.util.http
    import libbe.util.wsgi


class HTTP (base.VersionedStorage):
    """:py:class:`~libbe.storage.base.VersionedStorage` implementation over
    HTTP.

    Uses GET to retrieve information and POST to set information.
    """
    name = 'HTTP'
    user_agent = 'BE-HTTP-Storage'

    def __init__(self, repo, *args, **kwargs):
        repo,self.uname,self.password = self.parse_repo(repo)
        base.VersionedStorage.__init__(self, repo, *args, **kwargs)

    def parse_repo(self, repo):
        """Grab username and password (if any) from the repo URL.

        Examples
        --------

        >>> s = HTTP('http://host.com/path/to/repo')
        >>> s.repo
        'http://host.com/path/to/repo'
        >>> s.uname == None
        True
        >>> s.password == None
        True
        >>> s.parse_repo('http://joe:secret@host.com/path/to/repo')
        ('http://host.com/path/to/repo', 'joe', 'secret')
        """
        scheme,netloc,path,params,query,fragment = urlparse.urlparse(repo)
        parts = netloc.split('@', 1)
        if len(parts) == 2:
            uname,password = parts[0].split(':')
            repo = urlparse.urlunparse(
                (scheme, parts[1], path, params, query, fragment))
        else:
            uname,password = (None, None)
        return (repo, uname, password)

    def get_post_url(self, url, get=True, data_dict=None, headers=[]):
        if self.uname != None and self.password != None:
            headers.append(('Authorization','Basic %s' % \
                ('%s:%s' % (self.uname, self.password)).encode('base64')))
        return libbe.util.http.get_post_url(
            url, get, data_dict=data_dict, headers=headers,
            agent=self.user_agent)

    def storage_version(self, revision=None):
        """Return the storage format for this backend."""
        return libbe.storage.STORAGE_VERSION

    def _init(self):
        """Create a new storage repository."""
        raise base.NotSupported(
            'init', 'Cannot initialize this repository format.')

    def _destroy(self):
        """Remove the storage repository."""
        raise base.NotSupported(
            'destroy', 'Cannot destroy this repository format.')

    def _connect(self):
        self.check_storage_version()

    def _disconnect(self):
        pass

    def _add(self, id, parent=None, directory=False):
        url = urlparse.urljoin(self.repo, 'add')
        page,final_url,info = self.get_post_url(
            url, get=False,
            data_dict={'id':id, 'parent':parent, 'directory':directory})

    def _exists(self, id, revision=None):
        url = urlparse.urljoin(self.repo, 'exists')
        page,final_url,info = self.get_post_url(
            url, get=True,
            data_dict={'id':id, 'revision':revision})
        if page == 'True':
            return True
        return False

    def _remove(self, id):
        url = urlparse.urljoin(self.repo, 'remove')
        page,final_url,info = self.get_post_url(
            url, get=False,
            data_dict={'id':id, 'recursive':False})

    def _recursive_remove(self, id):
        url = urlparse.urljoin(self.repo, 'remove')
        page,final_url,info = self.get_post_url(
            url, get=False,
            data_dict={'id':id, 'recursive':True})

    def _ancestors(self, id=None, revision=None):
        url = urlparse.urljoin(self.repo, 'ancestors')
        page,final_url,info = self.get_post_url(
            url, get=True,
            data_dict={'id':id, 'revision':revision})
        return page.strip('\n').splitlines()

    def _children(self, id=None, revision=None):
        url = urlparse.urljoin(self.repo, 'children')
        page,final_url,info = self.get_post_url(
            url, get=True,
            data_dict={'id':id, 'revision':revision})
        return page.strip('\n').splitlines()

    def _get(self, id, default=base.InvalidObject, revision=None):
        url = urlparse.urljoin(self.repo, '/'.join(['get', id]))
        try:
            page,final_url,info = self.get_post_url(
                url, get=True,
                data_dict={'revision':revision})
        except libbe.util.http.HTTPError, e:
            if not (hasattr(e.error, 'code') and e.error.code in HTTP_VALID):
                raise
            elif default == base.InvalidObject:
                raise base.InvalidID(id)
            return default
        version = info['X-BE-Version']
        if version != libbe.storage.STORAGE_VERSION:
            raise base.InvalidStorageVersion(
                version, libbe.storage.STORAGE_VERSION)
        return page

    def _set(self, id, value):
        url = urlparse.urljoin(self.repo, '/'.join(['set', id]))
        try:
            page,final_url,info = self.get_post_url(
                url, get=False,
                data_dict={'value':value})
        except libbe.util.http.HTTPError, e:
            if not (hasattr(e.error, 'code') and e.error.code in HTTP_VALID):
                raise
            if e.error.code == HTTP_USER_ERROR \
                    and not 'InvalidID' in str(e.error):
                raise base.InvalidDirectory(
                    'Directory %s cannot have data' % id)
            raise base.InvalidID(id)

    def _commit(self, summary, body=None, allow_empty=False):
        url = urlparse.urljoin(self.repo, 'commit')
        try:
            page,final_url,info = self.get_post_url(
                url, get=False,
                data_dict={'summary':summary, 'body':body,
                           'allow_empty':allow_empty})
        except libbe.util.http.HTTPError, e:
            if not (hasattr(e.error, 'code') and e.error.code in HTTP_VALID):
                raise
            if e.error.code == HTTP_USER_ERROR:
                raise base.EmptyCommit
            raise base.InvalidID(id)
        return page.rstrip('\n')

    def revision_id(self, index=None):
        """Return the name of the <index>th revision.

        The choice of which branch to follow when crossing
        branches/merges is not defined.  Revision indices start at 1;
        ID 0 is the blank repository.

        Return None if index==None.

        Raises
        ------
        InvalidRevision
          If the specified revision does not exist.
        """
        if index == None:
            return None
        try:
            if int(index) != index:
                raise base.InvalidRevision(index)
        except ValueError:
            raise base.InvalidRevision(index)
        url = urlparse.urljoin(self.repo, 'revision-id')
        try:
            page,final_url,info = self.get_post_url(
                url, get=True,
                data_dict={'index':index})
        except libbe.util.http.HTTPError, e:
            if not (hasattr(e.error, 'code') and e.error.code in HTTP_VALID):
                raise
            if e.error.code == HTTP_USER_ERROR:
                raise base.InvalidRevision(index)
            raise base.InvalidID(id)
        return page.rstrip('\n')

    def changed(self, revision=None):
        url = urlparse.urljoin(self.repo, 'changed')
        page,final_url,info = self.get_post_url(
            url, get=True,
            data_dict={'revision':revision})
        lines = page.strip('\n')
        new,mod,rem = [p.splitlines() for p in page.split('\n\n')]
        return (new, mod, rem)

    def check_storage_version(self):
        version = self.storage_version()
        if version != libbe.storage.STORAGE_VERSION:
            raise base.InvalidStorageVersion(
                version, libbe.storage.STORAGE_VERSION)

    def storage_version(self, revision=None):
        url = urlparse.urljoin(self.repo, 'version')
        page,final_url,info = self.get_post_url(
            url, get=True, data_dict={'revision':revision})
        return page.rstrip('\n')

if TESTING == True:
    class TestingHTTP (HTTP):
        name = 'TestingHTTP'
        def __init__(self, repo, *args, **kwargs):
            self._storage_backend = base.VersionedStorage(repo)
            app = libbe.command.serve_storage.ServerApp(
                storage=self._storage_backend)
            self.app = libbe.util.wsgi.BEExceptionApp(app=app)
            HTTP.__init__(self, repo='http://localhost:8000/', *args, **kwargs)
            self.intitialized = False
            # duplicated from libbe.util.wsgi.WSGITestCase
            self.default_environ = {
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
            # duplicated from libbe.util.wsgi.WSGITestCase
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
            try:
                result = app(env, self.start_response)
            except libbe.util.wsgi.HandlerError as e:
                raise libbe.util.http.HTTPError(error=e, url=path, msg=str(e))
            return ''.join(result)
        def start_response(self, status, response_headers, exc_info=None):
            self.status = status
            self.response_headers = response_headers
            self.exc_info = exc_info
        def get_post_url(self, url, get=True, data_dict=None, headers=[]):
            if get == True:
                method = 'GET'
            else:
                method = 'POST'
            scheme,netloc,path,params,query,fragment = urlparse.urlparse(url)
            environ = {}
            for header_name,header_value in headers:
                environ['HTTP_%s' % header_name] = header_value
            output = self.getURL(
                self.app, path, method, data_dict, scheme, environ)
            if self.status != '200 OK':
                class __estr (object):
                    def __init__(self, string):
                        self.string = string
                        self.code = int(string.split()[0])
                    def __str__(self):
                        return self.string
                error = __estr(self.status)
                raise libbe.util.http.HTTPError(
                    error=error, url=url, msg=output)
            info = dict(self.response_headers)
            return (output, url, info)
        def _init(self):
            try:
                HTTP._init(self)
                raise AssertionError
            except base.NotSupported:
                pass
            self._storage_backend._init()
        def _destroy(self):
            try:
                HTTP._destroy(self)
                raise AssertionError
            except base.NotSupported:
                pass
            self._storage_backend._destroy()
        def _connect(self):
            self._storage_backend._connect()
            HTTP._connect(self)
        def _disconnect(self):
            HTTP._disconnect(self)
            self._storage_backend._disconnect()


    base.make_versioned_storage_testcase_subclasses(
        TestingHTTP, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
