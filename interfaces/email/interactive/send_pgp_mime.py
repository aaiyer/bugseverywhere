#!/usr/bin/python
#
# Copyright (C) 2009-2011 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         W. Trevor King <wking@drexel.edu>
#
# This file is part of Bugs Everywhere.
#
# Bugs Everywhere is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 2 of the License, or (at your
# option) any later version.
#
# Bugs Everywhere is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Bugs Everywhere.  If not, see <http://www.gnu.org/licenses/>.
"""
Python module and command line tool for sending pgp/mime email.

Mostly uses subprocess to call gpg and a sendmail-compatible mailer.
If you lack gpg, either don't use the encryption functions or adjust
the pgp_* commands.  You may need to adjust the sendmail command to
point to whichever sendmail-compatible mailer you have on your system.
"""

from cStringIO import StringIO
import os
import re
#import GnuPGInterface # Maybe should use this instead of subprocess
import smtplib
import subprocess
import sys
import tempfile
import types

try:
    from email import Message
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    from email.mime.application import MIMEApplication
    from email.encoders import encode_7or8bit
    from email.generator import Generator
    from email.parser import Parser
    from email.utils import getaddress
except ImportError:
    # adjust to old python 2.4
    from email import Message
    from email.MIMEText import MIMEText
    from email.MIMEMultipart import MIMEMultipart
    from email.MIMENonMultipart import MIMENonMultipart
    from email.Encoders import encode_7or8bit
    from email.Generator import Generator
    from email.Parser import Parser
    from email.Utils import getaddresses

    getaddress = getaddresses
    class MIMEApplication (MIMENonMultipart):
        def __init__(self, _data, _subtype, _encoder, **params):
            MIMENonMultipart.__init__(self, 'application', _subtype, **params)
            self.set_payload(_data)
            _encoder(self)

usage="""usage: %prog [options]

Scriptable PGP MIME email using gpg.

You can use gpg-agent for passphrase caching if your key requires a
passphrase (it better!).  Example usage would be to install gpg-agent,
and then run
  export GPG_TTY=`tty`
  eval $(gpg-agent --daemon)
in your shell before invoking this script.  See gpg-agent(1) for more
details.  Alternatively, you can send your passphrase in on stdin
  echo 'passphrase' | %prog [options]
or use the --passphrase-file option
  %prog [options] --passphrase-file FILE [more options]
Both of these alternatives are much less secure than gpg-agent.  You
have been warned.
"""

verboseInvoke = False
PGP_SIGN_AS = None
PASSPHRASE = None

# The following commands are adapted from my .mutt/pgp configuration
#
# Printf-like sequences:
#   %a The value of PGP_SIGN_AS.
#   %f Expands to the name of a file with text to be signed/encrypted.
#   %p Expands to the passphrase argument.
#   %R A string with some number (0 on up) of pgp_reciepient_arg
#      strings.
#   %r One key ID (e.g. recipient email address) to build a
#      pgp_reciepient_arg string.
#
# The above sequences can be used to optionally print a string if
# their length is nonzero. For example, you may only want to pass the
# -u/--local-user argument to gpg if PGP_SIGN_AS is defined.  To
# optionally print a string based upon one of the above sequences, the
# following construct is used
#   %?<sequence_char>?<optional_string>?
# where sequence_char is a character from the table above, and
# optional_string is the string you would like printed if status_char
# is nonzero. optional_string may contain other sequence as well as
# normal text, but it may not contain any question marks.
#
# see http://codesorcery.net/old/mutt/mutt-gnupg-howto
#     http://www.mutt.org/doc/manual/manual-6.html#pgp_autosign
#     http://tldp.org/HOWTO/Mutt-GnuPG-PGP-HOWTO-8.html
# for more details

pgp_recipient_arg='-r "%r"'
pgp_stdin_passphrase_arg='--passphrase-fd 0'
pgp_sign_command='/usr/bin/gpg --no-verbose --quiet --batch %p --output - --detach-sign --armor --textmode %?a?-u "%a"? %f'
pgp_encrypt_only_command='/usr/bin/gpg --no-verbose --quiet --batch --output - --encrypt --armor --textmode --always-trust --encrypt-to "%a" %R -- %f'
pgp_encrypt_sign_command='/usr/bin/gpg --no-verbose --quiet --batch %p --output - --encrypt --sign %?a?-u "%a"? --armor --textmode --always-trust --encrypt-to "%a" %R -- %f'
sendmail='/usr/sbin/sendmail -t'

def mail(msg, sendmail=None):
    """
    Send an email Message instance on its merry way.

    We can shell out to the user specified sendmail in case
    the local host doesn't have an SMTP server set up
    for easy smtplib usage.
    """
    if sendmail != None:
        execute(sendmail, stdin=flatten(msg))
        return None
    s = smtplib.SMTP()
    s.connect()
    s.sendmail(from_addr=source_email(msg),
               to_addrs=target_emails(msg),
               msg=flatten(msg))
    s.close()

def header_from_text(text, encoding="us-ascii"):
    """
    Simple wrapper for instantiating an email.Message from text.
    >>> header = header_from_text('\\n'.join(['From: me@big.edu','To: you@big.edu','Subject: testing']))
    >>> print flatten(header)
    From: me@big.edu
    To: you@big.edu
    Subject: testing
    <BLANKLINE>
    <BLANKLINE>
    """
    text = text.strip()
    if type(text) == types.UnicodeType:
        text = text.encode(encoding)
    # assume StringType arguments are already encoded
    p = Parser()
    return p.parsestr(text, headersonly=True)

def guess_encoding(text):
    if type(text) == types.StringType:
        encoding = "us-ascii"
    elif type(text) == types.UnicodeType:
        for encoding in ["us-ascii", "iso-8859-1", "utf-8"]:
            try:
                text.encode(encoding)
            except UnicodeError:
                pass
            else:
                break
        assert encoding != None
    return encoding

def encodedMIMEText(body, encoding=None):
    if encoding == None:
        encoding = guess_encoding(body)
    if encoding == "us-ascii":
        return MIMEText(body)
    else:
        # Create the message ('plain' stands for Content-Type: text/plain)
        return MIMEText(body.encode(encoding), 'plain', encoding)

def append_text(text_part, new_text):
    original_payload = text_part.get_payload(decode=True)
    new_payload = u"%s%s" % (original_payload, new_text)
    new_encoding = guess_encoding(new_payload)
    text_part.set_payload(new_payload.encode(new_encoding), new_encoding)

def attach_root(header, root_part):
    """
    Attach the email.Message root_part to the email.Message header
    without generating a multi-part message.
    """
    for k,v in header.items():
        root_part[k] = v
    return root_part    

def execute(args, stdin=None, expect=(0,)):
    """
    Execute a command (allows us to drive gpg).
    """
    if verboseInvoke == True:
        print >> sys.stderr, '$ '+args
    try:
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, close_fds=True)
    except OSError, e:
        strerror = '%s\nwhile executing %s' % (e.args[1], args)
        raise Exception, strerror
    output, error = p.communicate(input=stdin)
    status = p.wait()
    if verboseInvoke == True:
        print >> sys.stderr, '(status: %d)\n%s%s' % (status, output, error)
    if status not in expect:
        strerror = '%s\nwhile executing %s\n%s\n%d' % (args[1], args, error, status)
        raise Exception, strerror
    return status, output, error

def replace(template, format_char, replacement_text):
    """
    >>> replace('--textmode %?a?-u %a? %f', 'f', 'file.in')
    '--textmode %?a?-u %a? file.in'
    >>> replace('--textmode %?a?-u %a? %f', 'a', '0xHEXKEY')
    '--textmode -u 0xHEXKEY %f'
    >>> replace('--textmode %?a?-u %a? %f', 'a', '')
    '--textmode  %f'
    """
    if replacement_text == None:
        replacement_text = ""
    regexp = re.compile('%[?]'+format_char+'[?]([^?]*)[?]')
    if len(replacement_text) > 0:
        str = regexp.sub('\g<1>', template)
    else:
        str = regexp.sub('', template)
    regexp = re.compile('%'+format_char)
    str = regexp.sub(replacement_text, str)
    return str

def flatten(msg, to_unicode=False):
    """
    Produce flat text output from an email Message instance.
    """
    assert msg != None
    fp = StringIO()
    g = Generator(fp, mangle_from_=False)
    g.flatten(msg)
    text = fp.getvalue()
    if to_unicode == True:
        encoding = msg.get_content_charset() or "utf-8"
        text = unicode(text, encoding=encoding)
    return text

def source_email(msg, return_realname=False):
    """
    Search the header of an email Message instance to find the
    sender's email address.
    """
    froms = msg.get_all('from', [])
    from_tuples = getaddresses(froms) # [(realname, email_address), ...]
    assert len(from_tuples) == 1
    if return_realname == True:
        return from_tuples[0] # (realname, email_address)
    return from_tuples[0][1]  # email_address

def target_emails(msg):
    """
    Search the header of an email Message instance to find a
    list of recipient's email addresses.
    """
    tos = msg.get_all('to', [])
    ccs = msg.get_all('cc', [])
    bccs = msg.get_all('bcc', [])
    resent_tos = msg.get_all('resent-to', [])
    resent_ccs = msg.get_all('resent-cc', [])
    resent_bccs = msg.get_all('resent-bcc', [])
    all_recipients = getaddresses(tos + ccs + bccs + resent_tos
                                  + resent_ccs + resent_bccs)
    return [addr[1] for addr in all_recipients]

class PGPMimeMessageFactory (object):
    """
    See http://www.ietf.org/rfc/rfc3156.txt for specification details.
    >>> from_addr = "me@big.edu"
    >>> to_addr = "you@you.edu"
    >>> header = header_from_text('\\n'.join(['From: %s'%from_addr,'To: %s'%to_addr,'Subject: testing']))
    >>> source_email(header) == from_addr
    True
    >>> target_emails(header) == [to_addr]
    True
    >>> m = PGPMimeMessageFactory('check 1 2\\ncheck 1 2\\n')
    >>> print flatten(m.clearBodyPart())
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Disposition: inline
    <BLANKLINE>
    check 1 2
    check 1 2
    <BLANKLINE>
    >>> print flatten(m.plain())
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    <BLANKLINE>
    check 1 2
    check 1 2
    <BLANKLINE>
    >>> signed = m.sign(header)
    >>> signed.set_boundary('boundsep')
    >>> print flatten(signed).replace('\\t', ' '*4) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    Content-Type: multipart/signed; protocol="application/pgp-signature";
        micalg="pgp-sha1"; boundary="boundsep"
    MIME-Version: 1.0
    Content-Disposition: inline
    <BLANKLINE>
    --boundsep
    Content-Type: text/plain; charset="us-ascii"
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Disposition: inline
    <BLANKLINE>
    check 1 2
    check 1 2
    <BLANKLINE>
    --boundsep
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Description: signature
    Content-Type: application/pgp-signature; name="signature.asc";
        charset="us-ascii"
    <BLANKLINE>
    -----BEGIN PGP SIGNATURE-----
    ...
    -----END PGP SIGNATURE-----
    <BLANKLINE>
    --boundsep--
    >>> encrypted = m.encrypt(header)
    >>> encrypted.set_boundary('boundsep')
    >>> print flatten(encrypted).replace('\\t', ' '*4) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    Content-Type: multipart/encrypted;
        protocol="application/pgp-encrypted";
        micalg="pgp-sha1"; boundary="boundsep"
    MIME-Version: 1.0
    Content-Disposition: inline
    <BLANKLINE>
    --boundsep
    Content-Type: application/pgp-encrypted
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    <BLANKLINE>
    Version: 1
    <BLANKLINE>
    --boundsep
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Type: application/octet-stream; charset="us-ascii"
    <BLANKLINE>
    -----BEGIN PGP MESSAGE-----
    ...
    -----END PGP MESSAGE-----
    <BLANKLINE>
    --boundsep--
    >>> signedAndEncrypted = m.signAndEncrypt(header)
    >>> signedAndEncrypted.set_boundary('boundsep')
    >>> print flatten(signedAndEncrypted).replace('\\t', ' '*4) # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    Content-Type: multipart/encrypted;
        protocol="application/pgp-encrypted";
        micalg="pgp-sha1"; boundary="boundsep"
    MIME-Version: 1.0
    Content-Disposition: inline
    <BLANKLINE>
    --boundsep
    Content-Type: application/pgp-encrypted
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    <BLANKLINE>
    Version: 1
    <BLANKLINE>
    --boundsep
    MIME-Version: 1.0
    Content-Transfer-Encoding: 7bit
    Content-Type: application/octet-stream; charset="us-ascii"
    <BLANKLINE>
    -----BEGIN PGP MESSAGE-----
    ...
    -----END PGP MESSAGE-----
    <BLANKLINE>
    --boundsep--
    """
    def __init__(self, body):
        self.body = body
    def clearBodyPart(self):
        body = encodedMIMEText(self.body)
        body.add_header('Content-Disposition', 'inline')
        return body
    def passphrase_arg(self, passphrase=None):
        if passphrase == None and PASSPHRASE != None:
            passphrase = PASSPHRASE
        if passphrase == None:
            return (None,'')
        return (passphrase, pgp_stdin_passphrase_arg)
    def plain(self):
        """
        text/plain
        """
        return encodedMIMEText(self.body)
    def sign(self, header, passphrase=None):
        """
        multipart/signed
          +-> text/plain                 (body)
          +-> application/pgp-signature  (signature)
        """
        passphrase,pass_arg = self.passphrase_arg(passphrase)
        body = self.clearBodyPart()
        bfile = tempfile.NamedTemporaryFile()
        bfile.write(flatten(body))
        bfile.flush()

        args = replace(pgp_sign_command, 'f', bfile.name)
        if PGP_SIGN_AS == None:
            pgp_sign_as = '<%s>' % source_email(header)
        else:
            pgp_sign_as = PGP_SIGN_AS
        args = replace(args, 'a', pgp_sign_as)
        args = replace(args, 'p', pass_arg)
        status,output,error = execute(args, stdin=passphrase)
        signature = output

        sig = MIMEApplication(_data=signature,
                              _subtype='pgp-signature; name="signature.asc"',
                              _encoder=encode_7or8bit)
        sig['Content-Description'] = 'signature'
        sig.set_charset('us-ascii')

        msg = MIMEMultipart('signed', micalg='pgp-sha1',
                            protocol='application/pgp-signature')
        msg.attach(body)
        msg.attach(sig)

        msg['Content-Disposition'] = 'inline'
        return msg
    def encrypt(self, header, passphrase=None):
        """
        multipart/encrypted
         +-> application/pgp-encrypted  (control information)
         +-> application/octet-stream   (body)
        """
        body = self.clearBodyPart()
        bfile = tempfile.NamedTemporaryFile()
        bfile.write(flatten(body))
        bfile.flush()

        recipients = [replace(pgp_recipient_arg, 'r', recipient)
                      for recipient in target_emails(header)]
        recipient_string = ' '.join(recipients)
        args = replace(pgp_encrypt_only_command, 'R', recipient_string)
        args = replace(args, 'f', bfile.name)
        if PGP_SIGN_AS == None:
            pgp_sign_as = '<%s>' % source_email(header)
        else:
            pgp_sign_as = PGP_SIGN_AS
        args = replace(args, 'a', pgp_sign_as)
        status,output,error = execute(args)
        encrypted = output

        enc = MIMEApplication(_data=encrypted, _subtype='octet-stream',
                              _encoder=encode_7or8bit)
        enc.set_charset('us-ascii')

        control = MIMEApplication(_data='Version: 1\n', _subtype='pgp-encrypted',
                                  _encoder=encode_7or8bit)

        msg = MIMEMultipart('encrypted', micalg='pgp-sha1',
                            protocol='application/pgp-encrypted')
        msg.attach(control)
        msg.attach(enc)

        msg['Content-Disposition'] = 'inline'
        return msg
    def signAndEncrypt(self, header, passphrase=None):
        """
        multipart/encrypted
         +-> application/pgp-encrypted  (control information)
         +-> application/octet-stream   (body)
        """
        passphrase,pass_arg = self.passphrase_arg(passphrase)
        body = self.sign(header, passphrase)
        body.__delitem__('Bcc')
        bfile = tempfile.NamedTemporaryFile()
        bfile.write(flatten(body))
        bfile.flush()

        recipients = [replace(pgp_recipient_arg, 'r', recipient)
                      for recipient in target_emails(header)]
        recipient_string = ' '.join(recipients)
        args = replace(pgp_encrypt_only_command, 'R', recipient_string)
        args = replace(args, 'f', bfile.name)
        if PGP_SIGN_AS == None:
            pgp_sign_as = '<%s>' % source_email(header)
        else:
            pgp_sign_as = PGP_SIGN_AS
        args = replace(args, 'a', pgp_sign_as)
        args = replace(args, 'p', pass_arg)
        status,output,error = execute(args, stdin=passphrase)
        encrypted = output

        enc = MIMEApplication(_data=encrypted, _subtype='octet-stream',
                              _encoder=encode_7or8bit)
        enc.set_charset('us-ascii')

        control = MIMEApplication(_data='Version: 1\n',
                                  _subtype='pgp-encrypted',
                                  _encoder=encode_7or8bit)

        msg = MIMEMultipart('encrypted', micalg='pgp-sha1',
                            protocol='application/pgp-encrypted')
        msg.attach(control)
        msg.attach(enc)

        msg['Content-Disposition'] = 'inline'
        return msg

def test():
    import doctest
    doctest.testmod()


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage=usage)
    parser.add_option('-t', '--test', dest='test', action='store_true',
                      help='Run doctests and exit')

    parser.add_option('-H', '--header-file', dest='header_filename',
                      help='file containing email header', metavar='FILE')
    parser.add_option('-B', '--body-file', dest='body_filename',
                      help='file containing email body', metavar='FILE')

    parser.add_option('-P', '--passphrase-file', dest='passphrase_file',
                      help='file containing gpg passphrase', metavar='FILE')
    parser.add_option('-p', '--passphrase-fd', dest='passphrase_fd',
                      help='file descriptor from which to read gpg passphrase (0 for stdin)',
                      type="int", metavar='DESCRIPTOR')

    parser.add_option('--mode', dest='mode', default='sign',
                      help="One of 'sign', 'encrypt', 'sign-encrypt', or 'plain'.  Defaults to %default.",
                      metavar='MODE')

    parser.add_option('-a', '--sign-as', dest='sign_as',
                      help="The gpg key to sign with (gpg's -u/--local-user)",
                      metavar='KEY')

    parser.add_option('--output', dest='output', action='store_true',
                      help="Don't mail the generated message, print it to stdout instead.")

    (options, args) = parser.parse_args()

    stdin_used = False

    if options.passphrase_file != None:
        PASSPHRASE = file(options.passphrase_file, 'r').read()
    elif options.passphrase_fd != None:
        if options.passphrase_fd == 0:
            stdin_used = True
            PASSPHRASE = sys.stdin.read()
        else:
            PASSPHRASE = os.read(options.passphrase_fd)

    if options.sign_as:
        PGP_SIGN_AS = options.sign_as

    if options.test == True:
        test()
        sys.exit(0)

    header = None
    if options.header_filename != None:
        if options.header_filename == '-':
            assert stdin_used == False
            stdin_used = True
            header = sys.stdin.read()
        else:
            header = file(options.header_filename, 'r').read()
    if header == None:
        raise Exception, "missing header"
    headermsg = header_from_text(header)
    body = None
    if options.body_filename != None:
        if options.body_filename == '-':
            assert stdin_used == False
            stdin_used = True
            body = sys.stdin.read()
        else:
            body = file(options.body_filename, 'r').read()
    if body == None:
        raise Exception, "missing body"

    m = PGPMimeMessageFactory(body)
    if options.mode == "sign":
        bodymsg = m.sign(header)
    elif options.mode == "encrypt":
        bodymsg = m.encrypt(header)
    elif options.mode == "sign-encrypt":
        bodymsg = m.signAndEncrypt(header)
    elif options.mode == "plain":
        bodymsg = m.plain()
    else:
        print "Unrecognized mode '%s'" % options.mode

    message = attach_root(headermsg, bodymsg)
    if options.output == True:
        message = flatten(message)
        print message
    else:
        mail(message, sendmail)
