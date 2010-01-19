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

# For urllib2 information, see
#   urllib2, from urllib2 - The Missing Manual
#   http://www.voidspace.org.uk/python/articles/urllib2.shtml
# 
# A dictionary of response codes is available in
#   httplib.responses

"""
Access bug repository data over HTTP.
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
    import doctest
    import unittest


USER_AGENT = 'BE-HTTP-Storage'
HTTP_OK = 200
HTTP_FOUND = 302
HTTP_TEMP_REDIRECT = 307
HTTP_USER_ERROR = 418
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

def get_post_url(url, get=True, data_dict=None):
    """
    get:        use GET if True, otherwise use POST.
    data_dict:  dict of data to send.
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
    headers = {'User-Agent':USER_AGENT}
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
    """
    This class implements a Storage interface over HTTP, using GET to
    retrieve information and POST to set information.
    """
    name = 'HTTP'

    def __init__(self, *args, **kwargs):
        base.VersionedStorage.__init__(self, *args, **kwargs)

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
        page,final_url,info = get_post_url(
            url, get=False,
            data_dict={'id':id, 'parent':parent, 'directory':directory})

    def _remove(self, id):
        url = urlparse.urljoin(self.repo, 'remove')
        page,final_url,info = get_post_url(
            url, get=False,
            data_dict={'id':id, 'recursive':False})

    def _recursive_remove(self, id):
        url = urlparse.urljoin(self.repo, 'remove')
        page,final_url,info = get_post_url(
            url, get=False,
            data_dict={'id':id, 'recursive':True})

    def _ancestors(self, id=None, revision=None):
        url = urlparse.urljoin(self.repo, 'ancestors')
        page,final_url,info = get_post_url(
            url, get=True,
            data_dict={'id':id, 'revision':revision})
        return page.strip('\n').splitlines()

    def _children(self, id=None, revision=None):
        url = urlparse.urljoin(self.repo, 'children')
        page,final_url,info = get_post_url(
            url, get=True,
            data_dict={'id':id, 'revision':revision})
        return page.strip('\n').splitlines()

    def _get(self, id, default=base.InvalidObject, revision=None):
        url = urlparse.urljoin(self.repo, '/'.join(['get', id]))
        try:
            page,final_url,info = get_post_url(
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
            page,final_url,info = get_post_url(
                url, get=False,
                data_dict={'value':value})
        except InvalidURL, e:
            if not (hasattr(e.error, 'code') and e.error.code in HTTP_VALID):
                raise
            if e.error.code == HTTP_USER_ERROR:
                raise base.InvalidDirectory(
                    'Directory %s cannot have data' % id)
            raise base.InvalidID(id)

    def _commit(self, summary, body=None, allow_empty=False):
        url = urlparse.urljoin(self.repo, 'commit')
        try:
            page,final_url,info = get_post_url(
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
        """
        Return the name of the <index>th revision.  The choice of
        which branch to follow when crossing branches/merges is not
        defined.  Revision indices start at 1; ID 0 is the blank
        repository.

        Return None if index==None.

        If the specified revision does not exist, raise InvalidRevision.
        """
        if index == None:
            return None
        try:
            if int(index) != index:
                raise InvalidRevision(index)
        except ValueError:
            raise InvalidRevision(index)
        url = urlparse.urljoin(self.repo, 'revision-id')
        try:
            page,final_url,info = get_post_url(
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
        page,final_url,info = get_post_url(
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
        page,final_url,info = get_post_url(
            url, get=True, data_dict={'revision':revision})
        return page.rstrip('\n')

if TESTING == True:
    class GetPostUrlTestCase (unittest.TestCase):
        """Test cases for get_post_url()"""
        def test_get(self):
            url = 'http://bugseverywhere.org/be/show/HomePage'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == url,
                'Redirect?\n  Expected: "%s"\n  Got:      "%s"'
                % (url, final_url))
        def test_get_redirect(self):
            url = 'http://bugseverywhere.org'
            expected = 'http://bugseverywhere.org/be/show/HomePage'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == expected,
                'Redirect?\n  Expected: "%s"\n  Got:      "%s"'
                % (expected, final_url))

    #make_storage_testcase_subclasses(VersionedStorage, sys.modules[__name__])

    unitsuite =unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    suite = unittest.TestSuite([unitsuite, doctest.DocTestSuite()])
