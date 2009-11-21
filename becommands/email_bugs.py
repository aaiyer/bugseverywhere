# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
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
"""Email specified bugs in a be-handle-mail compatible format."""

import copy
from cStringIO import StringIO
from email import Message
from email.mime.text import MIMEText
from email.generator import Generator
import sys
import time

from libbe import cmdutil, bugdir
from libbe.subproc import invoke
from libbe.utility import time_to_str
from libbe.vcs import detect_vcs, installed_vcs
import show

__desc__ = __doc__

sendmail='/usr/sbin/sendmail -t'

def execute(args, manipulate_encodings=True):
    """
    >>> import os
    >>> from libbe import bug
    >>> bd = bugdir.SimpleBugDir()
    >>> bd.encoding = 'utf-8'
    >>> os.chdir(bd.root)
    >>> import email.charset as c
    >>> c.add_charset('utf-8', c.SHORTEST, c.QP, 'utf-8')
    >>> execute(["-o", "--to", "a@b.com", "--from", "b@c.edu", "a", "b"],
    ...         manipulate_encodings=False) # doctest: +ELLIPSIS
    Content-Type: text/xml; charset="utf-8"
    MIME-Version: 1.0
    Content-Transfer-Encoding: quoted-printable
    From: b@c.edu
    To: a@b.com
    Date: ...
    Subject: [be-bug:xml] Updates to a, b
    <BLANKLINE>
    <?xml version=3D"1.0" encoding=3D"utf-8" ?>
    <be-xml>
      <version>
        <tag>...</tag>
        <branch-nick>...</branch-nick>
        <revno>...</revno>
        <revision-id>...
      </version>
      <bug>
        <uuid>a</uuid>
        <short-name>a</short-name>
        <severity>minor</severity>
        <status>open</status>
        <creator>John Doe &lt;jdoe@example.com&gt;</creator>
        <created>Thu, 01 Jan 1970 00:00:00 +0000</created>
        <summary>Bug A</summary>
      </bug>
      <bug>
        <uuid>b</uuid>
        <short-name>b</short-name>
        <severity>minor</severity>
        <status>closed</status>
        <creator>Jane Doe &lt;jdoe@example.com&gt;</creator>
        <created>Thu, 01 Jan 1970 00:00:00 +0000</created>
        <summary>Bug B</summary>
      </bug>
    </be-xml>
    >>> bd.cleanup()

    Note that the '=3D' bits in
      <?xml version=3D"1.0" encoding=3D"utf-8" ?>
    are the way quoted-printable escapes '='.
    
    The unclosed <revision-id>... is because revision ids can be long
    enough to cause line wraps, and we want to ensure we match even if
    the closing </revision-id> is split by the wrapping.
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={-1: lambda bug : bug.active==True})
    if len(args) == 0:
        raise cmdutil.UsageError
    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    xml = show.output(args, bd, as_xml=True, with_comments=True)
    subject = options.subject
    if subject == None:
        subject = '[be-bug:xml] Updates to %s' % ', '.join(args)
    submit_email = TextEmail(to_address=options.to_address,
                             from_address=options.from_address,
                             subject=subject,
                             body=xml,
                             encoding=bd.encoding,
                             subtype='xml')
    if options.output == True:
        print submit_email
    else:
        submit_email.send()

def get_parser():
    parser = cmdutil.CmdOptionParser("be email-bugs [options] ID [ID ...]")
    parser.add_option("-t", "--to", metavar="EMAIL", dest="to_address",
                      help="Submission email address (%default)",
                      default="be-devel@bugseverywhere.org")
    parser.add_option("-f", "--from", metavar="EMAIL", dest="from_address",
                      help="Senders email address, overriding auto-generated default",
                      default=None)
    parser.add_option("-s", "--subject", metavar="STRING", dest="subject",
                      help="Subject line, overriding auto-generated default.  If you use this option, remember that be-handle-mail probably want something like '[be-bug:xml] ...'",
                      default=None)
    parser.add_option('-o', '--output', dest='output', action='store_true',
                      help="Don't mail the generated message, print it to stdout instead.  Useful for testing functionality.")
    return parser

longhelp="""
Email specified bugs in a be-handle-mail compatible format.  This is
the prefered method for reporting bugs if you did not install bzr by
branching a bzr repository.

If you _did_ install bzr by branching a bzr repository, we suggest you
commit any new bug information with
  bzr commit --message "Reported bug in demuxulizer"
and then email a bzr merge directive with
  bzr send --mail-to "be-devel@bugseverywhere.org"
rather than using this command.
"""

def help():
    return get_parser().help_str() + longhelp

class TextEmail (object):
    """
    Make it very easy to compose and send single-part text emails.
    >>> msg = TextEmail(to_address='Monty <monty@a.com>',
    ...                 from_address='Python <python@b.edu>',
    ...                 subject='Parrots',
    ...                 header={'x-special-header':'your info here'},
    ...                 body="Remarkable bird, id'nit, squire?\\nLovely plumage!")
    >>> print msg # doctest: +ELLIPSIS
    Content-Type: text/plain; charset="utf-8"
    MIME-Version: 1.0
    Content-Transfer-Encoding: base64
    From: Python <python@b.edu>
    To: Monty <monty@a.com>
    Date: ...
    Subject: Parrots
    x-special-header: your info here
    <BLANKLINE>
    UmVtYXJrYWJsZSBiaXJkLCBpZCduaXQsIHNxdWlyZT8KTG92ZWx5IHBsdW1hZ2Uh
    <BLANKLINE>
    >>> import email.charset as c
    >>> c.add_charset('utf-8', c.SHORTEST, c.QP, 'utf-8')
    >>> print msg # doctest: +ELLIPSIS
    Content-Type: text/plain; charset="utf-8"
    MIME-Version: 1.0
    Content-Transfer-Encoding: quoted-printable
    From: Python <python@b.edu>
    To: Monty <monty@a.com>
    Date: ...
    Subject: Parrots
    x-special-header: your info here
    <BLANKLINE>
    Remarkable bird, id'nit, squire?
    Lovely plumage!
    """
    def __init__(self, to_address, from_address=None, subject=None,
                 header=None, body=None, encoding='utf-8', subtype='plain'):
        self.to_address = to_address
        self.from_address = from_address
        if self.from_address == None:
            self.from_address = self._guess_from_address()
        self.subject = subject
        self.header = header
        if self.header == None:
            self.header = {}
        self.body = body
        self.encoding = encoding
        self.subtype = subtype
    def _guess_from_address(self):
        vcs = detect_vcs('.')
        if vcs.name == "None":
            vcs = installed_vcs()
        return vcs.get_user_id()
    def encoded_MIME_body(self):
        return MIMEText(self.body.encode(self.encoding),
                        self.subtype,
                        self.encoding)
    def message(self):
        response = self.encoded_MIME_body()
        response['From'] = self.from_address
        response['To'] = self.to_address
        response['Date'] = time_to_str(time.time())
        response['Subject'] = self.subject
        for k,v in self.header.items():
            response[k] = v
        return response
    def flatten(self, to_unicode=False):
        """
        This is a simplified version of send_pgp_mime.flatten().        
        """
        fp = StringIO()
        g = Generator(fp, mangle_from_=False)
        g.flatten(self.message())
        text = fp.getvalue()
        if to_unicode == True:
            encoding = msg.get_content_charset() or "utf-8"
            text = unicode(text, encoding=encoding)
        return text
    def __str__(self):
        return self.flatten()
    def __unicode__(self):
        return self.flatten(to_unicode=True)        
    def send(self, sendmail=None):
        """
        This is a simplified version of send_pgp_mime.mail().
    
        Send an email Message instance on its merry way by shelling
        out to the user specified sendmail.
        """
        if sendmail == None:
            sendmail = SENDMAIL
        invoke(sendmail, stdin=self.flatten())
