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

# For urllib2 information, see
#   urllib2, from urllib2 - The Missing Manual
#   http://www.voidspace.org.uk/python/articles/urllib2.shtml
# 
# A dictionary of response codes is available in
#   httplib.responses

"""Define an HTTP-based :class:`~libbe.storage.base.VersionedStorage`
implementation.

See Also
--------
:mod:`libbe.command.serve` : the associated server

"""

import sys
import urllib
import urllib2
import urlparse

import libbe
import libbe.version
import base
from libbe import TESTING

if TESTING == True:
    import copy
    import doctest
    import StringIO
    import unittest

    import libbe.bugdir
    import libbe.command.serve


USER_AGENT = 'BE-HTTP-Storage'
HTTP_OK = 200
HTTP_FOUND = 302
HTTP_TEMP_REDIRECT = 307
HTTP_USER_ERROR = 418
"""Status returned to indicate exceptions on the server side.

A BE-specific extension to the HTTP/1.1 protocol (See `RFC 2616`_).

.. _RFC 2616: http://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html#sec6.1.1
"""

HTTP_VALID = [HTTP_OK, HTTP_FOUND, HTTP_TEMP_REDIRECT, HTTP_USER_ERROR]

class InvalidURL (Exception):
    def __init__(self, error=None, url=None, msg=None):
        Exception.__init__(self, msg)
        self.url = url
        self.error = error
        self.msg = msg
    def __str__(self):
        if self.msg == None:
            if self.error == None:
                return "Unknown URL error: %s" % self.url
            return self.error.__str__()
        return self.msg

def get_post_url(url, get=True, data_dict=None, headers=[]):
    """Execute a GET or POST transaction.

    Parameters
    ----------
    url : str
      The base URL (query portion added internally, if necessary).
    get : bool
      Use GET if True, otherwise use POST.
    data_dict : dict
      Data to send, either by URL query (if GET) or by POST (if POST).
    headers : list
      Extra HTTP headers to add to the request.
    """
    if data_dict == None:
        data_dict = {}
    if get == True:
        if data_dict != {}:
            # encode get parameters in the url
            param_string = urllib.urlencode(data_dict)
            url = "%s?%s" % (url, param_string)
        data = None
    else:
        data = urllib.urlencode(data_dict)
    headers = dict(headers)
    headers['User-Agent'] = USER_AGENT
    req = urllib2.Request(url, data=data, headers=headers)
    try:
        response = urllib2.urlopen(req)
    except urllib2.HTTPError, e:
        if hasattr(e, 'reason'):
            msg = 'We failed to reach a server.\nURL: %s\nReason: %s' \
                % (url, e.reason)
        elif hasattr(e, 'code'):
            msg = "The server couldn't fulfill the request.\nURL: %s\nError code: %s" \
                % (url, e.code)
        raise InvalidURL(error=e, url=url, msg=msg)
    page = response.read()
    final_url = response.geturl()
    info = response.info()
    response.close()
    return (page, final_url, info)


class HTTP (base.VersionedStorage):
    """:class:`~libbe.storage.base.VersionedStorage` implementation over
    HTTP.

    Uses GET to retrieve information and POST to set information.
    """
    name = 'HTTP'

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
        return get_post_url(url, get, data_dict, headers)

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
        except InvalidURL, e:
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
        except InvalidURL, e:
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
        except InvalidURL, e:
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
        except InvalidURL, e:
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
    class GetPostUrlTestCase (unittest.TestCase):
        """Test cases for get_post_url()"""
        def test_get(self):
            url = 'http://bugseverywhere.org/'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == url,
                'Redirect?\n  Expected: "%s"\n  Got:      "%s"'
                % (url, final_url))
        def test_get_redirect(self):
            url = 'http://physics.drexel.edu/~wking/code/be/redirect'
            expected = 'http://physics.drexel.edu/~wking/'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == expected,
                'Redirect?\n  Expected: "%s"\n  Got:      "%s"'
                % (expected, final_url))

    class TestingHTTP (HTTP):
        name = 'TestingHTTP'
        def __init__(self, repo, *args, **kwargs):
            self._storage_backend = base.VersionedStorage(repo)
            self.app = libbe.command.serve.ServerApp(
                storage=self._storage_backend)
            HTTP.__init__(self, repo='http://localhost:8000/', *args, **kwargs)
            self.intitialized = False
            # duplicated from libbe.command.serve.WSGITestCase
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
            # duplicated from libbe.command.serve.WSGITestCase
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
                raise InvalidURL(error=error, url=url, msg=output)
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
