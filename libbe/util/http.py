# Copyright (C) 2012 W. Trevor King <wking@tremily.us>
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
# but it is slow to load.

import urllib
import urllib2

from libbe import TESTING

if TESTING:
    import unittest


HTTP_OK = 200
HTTP_FOUND = 302
HTTP_TEMP_REDIRECT = 307
HTTP_USER_ERROR = 418
"""Status returned to indicate exceptions on the server side.

A BE-specific extension to the HTTP/1.1 protocol (See `RFC 2616`_).

.. _RFC 2616: http://www.w3.org/Protocols/rfc2616/rfc2616-sec6.html#sec6.1.1
"""

HTTP_VALID = [HTTP_OK, HTTP_FOUND, HTTP_TEMP_REDIRECT, HTTP_USER_ERROR]


USER_AGENT = 'BE-agent'


class HTTPError (Exception):
    def __init__(self, error=None, url=None, msg=None):
        Exception.__init__(self, msg)
        self.url = url
        self.error = error
        self.msg = msg

    def __str__(self):
        if self.msg is None:
            if self.error is None:
                return 'Unknown HTTP error: {0}'.format(self.url)
            return str(self.error)
        return self.msg


def get_post_url(url, get=True, data=None, data_dict=None, headers=[],
                 agent=None):
    """Execute a GET or POST transaction.

    Parameters
    ----------
    url : str
      The base URL (query portion added internally, if necessary).
    get : bool
      Use GET if True, otherwise use POST.
    data : str
      Raw data to send by POST (requires POST).
    data_dict : dict
      Data to send, either by URL query (if GET) or by POST (if POST).
      Cannot be given in combination with `data`.
    headers : list
      Extra HTTP headers to add to the request.
    agent : str
      User agent string overriding the BE default.
    """
    if agent is None:
        agent = USER_AGENT
    if data is None:
        if data_dict is None:
            data_dict = {}
        if get is True:
            if data_dict != {}:
                # encode get parameters in the url
                param_string = urllib.urlencode(data_dict)
                url = '{0}?{1}'.format(url, param_string)
        else:
            data = urllib.urlencode(data_dict)
    else:
        assert get is False, (data, get)
        assert data_dict is None, (data, data_dict)
    headers = dict(headers)
    headers['User-Agent'] = agent
    req = urllib2.Request(url, data=data, headers=headers)
    try:
        response = urllib2.urlopen(req)
    except urllib2.HTTPError, e:
        if e.code == HTTP_USER_ERROR:
            lines = ['The server reported a user error (HTTPError)']
        else:
            lines = ['The server reported an error (HTTPError)']
        lines.append('URL: {0}'.format(url))
        if hasattr(e, 'reason'):
            lines.append('Reason: {0}'.format(e.reason))
        lines.append('Error code: {0}'.format(e.code))
        msg = '\n'.join(lines)
        raise HTTPError(error=e, url=url, msg=msg)
    except urllib2.URLError, e:
        msg = ('We failed to connect to the server (URLError).\nURL: {0}\n'
               'Reason: {1}').format(url, e.reason)
        raise HTTPError(error=e, url=url, msg=msg)
    page = response.read()
    final_url = response.geturl()
    info = response.info()
    response.close()
    return (page, final_url, info)


if TESTING:
    class GetPostUrlTestCase (unittest.TestCase):
        """Test cases for get_post_url()"""
        def test_get(self):
            url = 'http://bugseverywhere.org/'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == url,
                'Redirect?\n  Expected: "{0}"\n  Got:      "{1}"'.format(
                    url, final_url))

        def test_get_redirect(self):
            url = 'http://physics.drexel.edu/~wking/code/be/redirect'
            expected = 'http://physics.drexel.edu/~wking/'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == expected,
                'Redirect?\n  Expected: "{0}"\n  Got:      "{1}"'.format(
                    expected, final_url))
