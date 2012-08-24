# Copyright

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
                return 'Unknown HTTP error: {}'.format(self.url)
            return str(self.error)
        return self.msg


def get_post_url(url, get=True, data_dict=None, headers=[], agent=None):
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
    agent : str
      User agent string overriding the BE default.
    """
    if data_dict is None:
        data_dict = {}
    if agent is None:
        agent = USER_AGENT
    if get is True:
        if data_dict != {}:
            # encode get parameters in the url
            param_string = urllib.urlencode(data_dict)
            url = '{}?{}'.format(url, param_string)
        data = None
    else:
        data = urllib.urlencode(data_dict)
    headers = dict(headers)
    headers['User-Agent'] = agent
    req = urllib2.Request(url, data=data, headers=headers)
    try:
        response = urllib2.urlopen(req)
    except urllib2.HTTPError, e:
        if hasattr(e, 'reason'):
            msg = ('We failed to connect to the server.\nURL: {}\n'
                   'Reason: {}').format(url, e.reason)
        elif hasattr(e, 'code'):
            msg = ("The server couldn't fulfill the request.\nURL: {}\n"
                   'Error code: {}').format(url, e.code)
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
                'Redirect?\n  Expected: "{}"\n  Got:      "{}"'.format(
                    url, final_url))

        def test_get_redirect(self):
            url = 'http://physics.drexel.edu/~wking/code/be/redirect'
            expected = 'http://physics.drexel.edu/~wking/'
            page,final_url,info = get_post_url(url=url)
            self.failUnless(final_url == expected,
                'Redirect?\n  Expected: "{}"\n  Got:      "{}"'.format(
                    expected, final_url))
