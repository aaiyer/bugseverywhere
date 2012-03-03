# Copyright (C) 2008-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Thomas Habets <thomas@habets.pp.se>
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

"""Define the :class:`Comment` class for representing bug comments.
"""

import base64
import os
import os.path
import sys
import time
import types
try:
    from email.mime.base import MIMEBase
    from email.encoders import encode_base64
except ImportError:
    # adjust to old python 2.4
    from email.MIMEBase import MIMEBase
    from email.Encoders import encode_base64
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
import xml.sax.saxutils

import libbe
import libbe.util.id
from libbe.storage.util.properties import Property, doc_property, \
    local_property, defaulting_property, checked_property, cached_property, \
    primed_property, change_hook_property, settings_property
import libbe.storage.util.settings_object as settings_object
import libbe.storage.util.mapfile as mapfile
from libbe.util.tree import Tree
import libbe.util.utility as utility

if libbe.TESTING == True:
    import doctest


class MissingReference(ValueError):
    def __init__(self, comment):
        msg = "Missing reference to %s" % (comment.in_reply_to)
        ValueError.__init__(self, msg)
        self.reference = comment.in_reply_to
        self.comment = comment

INVALID_UUID = "!!~~\n INVALID-UUID \n~~!!"

def load_comments(bug, load_full=False):
    """
    Set load_full=True when you want to load the comment completely
    from disk *now*, rather than waiting and lazy loading as required.
    """
    uuids = []
    for id in libbe.util.id.child_uuids(
                  bug.storage.children(
                      bug.id.storage())):
        uuids.append(id)
    comments = []
    for uuid in uuids:
        comm = Comment(bug, uuid, from_storage=True)
        if load_full == True:
            comm.load_settings()
            dummy = comm.body # force the body to load
        comments.append(comm)
    bug.comment_root = Comment(bug, uuid=INVALID_UUID)
    bug.add_comments(comments, ignore_missing_references=True)
    return bug.comment_root

def save_comments(bug):
    for comment in bug.comment_root.traverse():
        comment.save()


class Comment (Tree, settings_object.SavedSettingsObject):
    """Comments are a notes that attach to :class:`~libbe.bug.Bug`\s in
    threaded trees.  In mailing-list terms, a comment is analogous to
    a single part of an email.

    >>> c = Comment()
    >>> c.uuid != None
    True
    >>> c.uuid = "some-UUID"
    >>> print c.content_type
    text/plain
    """

    settings_properties = []
    required_saved_properties = []
    _prop_save_settings = settings_object.prop_save_settings
    _prop_load_settings = settings_object.prop_load_settings
    def _versioned_property(settings_properties=settings_properties,
                            required_saved_properties=required_saved_properties,
                            **kwargs):
        if "settings_properties" not in kwargs:
            kwargs["settings_properties"] = settings_properties
        if "required_saved_properties" not in kwargs:
            kwargs["required_saved_properties"]=required_saved_properties
        return settings_object.versioned_property(**kwargs)

    @_versioned_property(name="Alt-id",
                         doc="Alternate ID for linking imported comments.  Internally comments are linked (via In-reply-to) to the parent's UUID.  However, these UUIDs are generated internally, so Alt-id is provided as a user-controlled linking target.")
    def alt_id(): return {}

    @_versioned_property(name="Author",
                         doc="The author of the comment")
    def author(): return {}

    @_versioned_property(name="In-reply-to",
                         doc="UUID for parent comment or bug")
    def in_reply_to(): return {}

    @_versioned_property(name="Content-type",
                         doc="Mime type for comment body",
                         default="text/plain",
                         require_save=True)
    def content_type(): return {}

    @_versioned_property(name="Date",
                         doc="An RFC 2822 timestamp for comment creation")
    def date(): return {}

    def _get_time(self):
        if self.date == None:
            return None
        return utility.str_to_time(self.date)
    def _set_time(self, value):
        self.date = utility.time_to_str(value)
    time = property(fget=_get_time,
                    fset=_set_time,
                    doc="An integer version of .date")

    def _get_comment_body(self):
        if self.storage != None and self.storage.is_readable() \
                and self.uuid != INVALID_UUID:
            return self.storage.get(self.id.storage("body"),
                decode=self.content_type.startswith("text/"))
    def _set_comment_body(self, old=None, new=None, force=False):
        assert self.uuid != INVALID_UUID, self
        if self.content_type.startswith('text/') \
                and self.bug != None and self.bug.bugdir != None:
            new = libbe.util.id.short_to_long_text([self.bug.bugdir], new)
        if (self.storage != None and self.storage.writeable == True) \
                or force==True:
            assert new != None, "Can't save empty comment"
            self.storage.set(self.id.storage("body"), new)

    @Property
    @change_hook_property(hook=_set_comment_body)
    @cached_property(generator=_get_comment_body)
    @local_property("body")
    @doc_property(doc="The meat of the comment")
    def body(): return {}

    def _extra_strings_check_fn(value):
        return utility.iterable_full_of_strings(value, \
                         alternative=settings_object.EMPTY)
    def _extra_strings_change_hook(self, old, new):
        self.extra_strings.sort() # to make merging easier
        self._prop_save_settings(old, new)
    @_versioned_property(name="extra_strings",
                         doc="Space for an array of extra strings.  Useful for storing state for functionality implemented purely in becommands/<some_function>.py.",
                         default=[],
                         check_fn=_extra_strings_check_fn,
                         change_hook=_extra_strings_change_hook,
                         mutable=True)
    def extra_strings(): return {}

    def __init__(self, bug=None, uuid=None, from_storage=False,
                 in_reply_to=None, body=None, content_type=None):
        """
        Set ``from_storage=True`` to load an old comment.
        Set ``from_storage=False`` to create a new comment.

        The ``uuid`` option is required when ``from_storage==True``.

        The in_reply_to, body, and content_type options are only used
        if ``from_storage==False`` (the default).  When
        ``from_storage==True``, they are loaded from the bug database.
        ``content_type`` decides if the body should be run through
        :func:`util.id.short_to_long_text` before saving.  See
        :meth:`_set_comment_body` for details.

        ``in_reply_to`` should be the uuid string of the parent comment.
        """
        Tree.__init__(self)
        settings_object.SavedSettingsObject.__init__(self)
        self.bug = bug
        self.storage = None
        self.uuid = uuid
        self.id = libbe.util.id.ID(self, 'comment')
        if from_storage == False:
            if uuid == None:
                self.uuid = libbe.util.id.uuid_gen()
            self.time = int(time.time()) # only save to second precision
            self.in_reply_to = in_reply_to
            if content_type != None:
                self.content_type = content_type
            self.body = body
        if self.bug != None:
            self.storage = self.bug.storage
        if from_storage == False:
            if self.storage != None and self.storage.is_writeable():
                self.save()

    def __cmp__(self, other):
        return cmp_full(self, other)

    def __str__(self):
        """
        >>> comm = Comment(bug=None, body="Some insightful remarks")
        >>> comm.uuid = "com-1"
        >>> comm.date = "Thu, 20 Nov 2008 15:55:11 +0000"
        >>> comm.author = "Jane Doe <jdoe@example.com>"
        >>> print comm
        --------- Comment ---------
        Name: //com
        From: Jane Doe <jdoe@example.com>
        Date: Thu, 20 Nov 2008 15:55:11 +0000
        <BLANKLINE>
        Some insightful remarks
        """
        return self.string()

    def traverse(self, *args, **kwargs):
        """Avoid working with the possible dummy root comment"""
        for comment in Tree.traverse(self, *args, **kwargs):
            if comment.uuid == INVALID_UUID:
                continue
            yield comment

    # serializing methods

    def _setting_attr_string(self, setting):
        value = getattr(self, setting)
        if value == None:
            return ""
        if type(value) not in types.StringTypes:
            return str(value)
        return value

    def safe_in_reply_to(self):
        """
        Return self.in_reply_to, except...

          * if no comment matches that id, in which case return None.
          * if that id matches another comments .alt_id, in which case
            return the matching comments .uuid.
        """
        if self.in_reply_to == None:
            return None
        else:
            try:
                irt_comment = self.bug.comment_from_uuid(
                    self.in_reply_to, match_alt_id=True)
                return irt_comment.uuid
            except KeyError:
                return None

    def xml(self, indent=0):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.uuid = "0123"
        >>> comm.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> print comm.xml(indent=2)
          <comment>
            <uuid>0123</uuid>
            <short-name>//012</short-name>
            <author></author>
            <date>Thu, 01 Jan 1970 00:00:00 +0000</date>
            <content-type>text/plain</content-type>
            <body>Some
        insightful
        remarks</body>
          </comment>
        >>> comm.content_type = 'image/png'
        >>> print comm.xml()
        <comment>
          <uuid>0123</uuid>
          <short-name>//012</short-name>
          <author></author>
          <date>Thu, 01 Jan 1970 00:00:00 +0000</date>
          <content-type>image/png</content-type>
          <body>U29tZQppbnNpZ2h0ZnVsCnJlbWFya3MK
        </body>
        </comment>
        """
        if self.content_type.startswith('text/'):
            body = (self.body or '').rstrip('\n')
        else:
            maintype,subtype = self.content_type.split('/',1)
            msg = MIMEBase(maintype, subtype)
            msg.set_payload(self.body or '')
            encode_base64(msg)
            body = base64.encodestring(self.body or '')
        info = [('uuid', self.uuid),
                ('alt-id', self.alt_id),
                ('short-name', self.id.user()),
                ('in-reply-to', self.safe_in_reply_to()),
                ('author', self._setting_attr_string('author')),
                ('date', self.date),
                ('content-type', self.content_type),
                ('body', body)]
        lines = ['<comment>']
        for (k,v) in info:
            if v != None:
                lines.append('  <%s>%s</%s>' % (k,xml.sax.saxutils.escape(v),k))
        for estr in self.extra_strings:
            lines.append('  <extra-string>%s</extra-string>' % estr)
        lines.append('</comment>')
        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def from_xml(self, xml_string, preserve_uuids=False, verbose=True):
        u"""
        Note: If alt-id is not given, translates any <uuid> fields to
        <alt-id> fields.
        >>> commA = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> commA.uuid = "0123"
        >>> commA.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> commA.author = u'Fran\xe7ois'
        >>> commA.extra_strings += ['TAG: very helpful']
        >>> xml = commA.xml()
        >>> commB = Comment()
        >>> commB.from_xml(xml, verbose=True)
        >>> commB.explicit_attrs
        ['author', 'date', 'content_type', 'body', 'alt_id']
        >>> commB.xml() == xml
        False
        >>> commB.uuid = commB.alt_id
        >>> commB.alt_id = None
        >>> commB.xml() == xml
        True
        >>> commC = Comment()
        >>> commC.from_xml(xml, preserve_uuids=True)
        >>> commC.uuid == commA.uuid
        True
        """
        if type(xml_string) == types.UnicodeType:
            xml_string = xml_string.strip().encode('unicode_escape')
        if hasattr(xml_string, 'getchildren'): # already an ElementTree Element
            comment = xml_string
        else:
            comment = ElementTree.XML(xml_string)
        if comment.tag != 'comment':
            raise utility.InvalidXML( \
                'comment', comment, 'root element must be <comment>')
        tags=['uuid','alt-id','in-reply-to','author','date','content-type',
              'body','extra-string']
        self.explicit_attrs = []
        uuid = None
        body = None
        estrs = []
        for child in comment.getchildren():
            if child.tag == 'short-name':
                pass
            elif child.tag in tags:
                if child.text == None or len(child.text) == 0:
                    text = settings_object.EMPTY
                else:
                    text = xml.sax.saxutils.unescape(child.text)
                    # Sometimes saxutils returns unicode
                    if not isinstance(text, unicode):
                        text = text.decode('unicode_escape')
                    text = text.strip()
                if child.tag == 'uuid' and not preserve_uuids:
                    uuid = text
                    continue # don't set the comment's uuid tag.
                elif child.tag == 'body':
                    body = text
                    self.explicit_attrs.append(child.tag)
                    continue # don't set the comment's body yet.
                elif child.tag == 'extra-string':
                    estrs.append(text)
                    continue # don't set the comment's extra_string yet.
                attr_name = child.tag.replace('-','_')
                self.explicit_attrs.append(attr_name)
                setattr(self, attr_name, text)
            elif verbose == True:
                print >> sys.stderr, 'Ignoring unknown tag %s in %s' \
                    % (child.tag, comment.tag)
        if uuid != self.uuid and self.alt_id == None:
            self.explicit_attrs.append('alt_id')
            self.alt_id = uuid
        if body != None:
            if self.content_type.startswith('text/'):
                self.body = body+'\n' # restore trailing newline
            else:
                self.body = base64.decodestring(body)
        self.extra_strings = estrs

    def merge(self, other, accept_changes=True,
              accept_extra_strings=True, change_exception=False):
        """
        Merge info from other into this comment.  Overrides any
        attributes in self that are listed in other.explicit_attrs.

        >>> commA = Comment(bug=None, body='Some insightful remarks')
        >>> commA.uuid = '0123'
        >>> commA.date = 'Thu, 01 Jan 1970 00:00:00 +0000'
        >>> commA.author = 'Frank'
        >>> commA.extra_strings += ['TAG: very helpful']
        >>> commA.extra_strings += ['TAG: favorite']
        >>> commB = Comment(bug=None, body='More insightful remarks')
        >>> commB.uuid = '3210'
        >>> commB.date = 'Fri, 02 Jan 1970 00:00:00 +0000'
        >>> commB.author = 'John'
        >>> commB.explicit_attrs = ['author', 'body']
        >>> commB.extra_strings += ['TAG: very helpful']
        >>> commB.extra_strings += ['TAG: useful']
        >>> commA.merge(commB, accept_changes=False,
        ...             accept_extra_strings=False, change_exception=False)
        >>> commA.merge(commB, accept_changes=False,
        ...             accept_extra_strings=False, change_exception=True)
        Traceback (most recent call last):
          ...
        ValueError: Merge would change author "Frank"->"John" for comment 0123
        >>> commA.merge(commB, accept_changes=True,
        ...             accept_extra_strings=False, change_exception=True)
        Traceback (most recent call last):
          ...
        ValueError: Merge would add extra string "TAG: useful" to comment 0123
        >>> print commA.author
        John
        >>> print commA.extra_strings
        ['TAG: favorite', 'TAG: very helpful']
        >>> commA.merge(commB, accept_changes=True,
        ...             accept_extra_strings=True, change_exception=True)
        >>> print commA.extra_strings
        ['TAG: favorite', 'TAG: useful', 'TAG: very helpful']
        >>> print commA.xml()
        <comment>
          <uuid>0123</uuid>
          <short-name>//012</short-name>
          <author>John</author>
          <date>Thu, 01 Jan 1970 00:00:00 +0000</date>
          <content-type>text/plain</content-type>
          <body>More insightful remarks</body>
          <extra-string>TAG: favorite</extra-string>
          <extra-string>TAG: useful</extra-string>
          <extra-string>TAG: very helpful</extra-string>
        </comment>
        """
        for attr in other.explicit_attrs:
            old = getattr(self, attr)
            new = getattr(other, attr)
            if old != new:
                if accept_changes == True:
                    setattr(self, attr, new)
                elif change_exception == True:
                    raise ValueError, \
                        'Merge would change %s "%s"->"%s" for comment %s' \
                        % (attr, old, new, self.uuid)
        if self.alt_id == self.uuid:
            self.alt_id = None
        for estr in other.extra_strings:
            if not estr in self.extra_strings:
                if accept_extra_strings == True:
                    self.extra_strings.append(estr)
                elif change_exception == True:
                    raise ValueError, \
                        'Merge would add extra string "%s" to comment %s' \
                        % (estr, self.uuid)

    def string(self, indent=0):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.uuid = 'abcdef'
        >>> comm.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> print comm.string(indent=2)
          --------- Comment ---------
          Name: //abc
          From: 
          Date: Thu, 01 Jan 1970 00:00:00 +0000
        <BLANKLINE>
          Some
          insightful
          remarks
        """
        lines = []
        lines.append("--------- Comment ---------")
        lines.append("Name: %s" % self.id.user())
        lines.append("From: %s" % (self._setting_attr_string("author")))
        lines.append("Date: %s" % self.date)
        lines.append("")
        if self.content_type.startswith("text/"):
            body = (self.body or "")
            if self.bug != None and self.bug.bugdir != None:
                body = libbe.util.id.long_to_short_text([self.bug.bugdir], body)
            lines.extend(body.splitlines())
        else:
            lines.append("Content type %s not printable.  Try XML output instead" % self.content_type)

        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def string_thread(self, string_method_name="string",
                      indent=0, flatten=True):
        """
        Return a string displaying a thread of comments.
        bug_shortname is only used if auto_name_map == True.

        string_method_name (defaults to "string") is the name of the
        Comment method used to generate the output string for each
        Comment in the thread.  The method must take the arguments
        indent and shortname.

        >>> a = Comment(bug=None, uuid="a", body="Insightful remarks")
        >>> a.time = utility.str_to_time("Thu, 20 Nov 2008 01:00:00 +0000")
        >>> b = a.new_reply("Critique original comment")
        >>> b.uuid = "b"
        >>> b.time = utility.str_to_time("Thu, 20 Nov 2008 02:00:00 +0000")
        >>> c = b.new_reply("Begin flamewar :p")
        >>> c.uuid = "c"
        >>> c.time = utility.str_to_time("Thu, 20 Nov 2008 03:00:00 +0000")
        >>> d = a.new_reply("Useful examples")
        >>> d.uuid = "d"
        >>> d.time = utility.str_to_time("Thu, 20 Nov 2008 04:00:00 +0000")
        >>> a.sort(key=lambda comm : comm.time)
        >>> print a.string_thread(flatten=True)
        --------- Comment ---------
        Name: //a
        From: 
        Date: Thu, 20 Nov 2008 01:00:00 +0000
        <BLANKLINE>
        Insightful remarks
          --------- Comment ---------
          Name: //b
          From: 
          Date: Thu, 20 Nov 2008 02:00:00 +0000
        <BLANKLINE>
          Critique original comment
          --------- Comment ---------
          Name: //c
          From: 
          Date: Thu, 20 Nov 2008 03:00:00 +0000
        <BLANKLINE>
          Begin flamewar :p
        --------- Comment ---------
        Name: //d
        From: 
        Date: Thu, 20 Nov 2008 04:00:00 +0000
        <BLANKLINE>
        Useful examples
        >>> print a.string_thread()
        --------- Comment ---------
        Name: //a
        From: 
        Date: Thu, 20 Nov 2008 01:00:00 +0000
        <BLANKLINE>
        Insightful remarks
          --------- Comment ---------
          Name: //b
          From: 
          Date: Thu, 20 Nov 2008 02:00:00 +0000
        <BLANKLINE>
          Critique original comment
          --------- Comment ---------
          Name: //c
          From: 
          Date: Thu, 20 Nov 2008 03:00:00 +0000
        <BLANKLINE>
          Begin flamewar :p
        --------- Comment ---------
        Name: //d
        From: 
        Date: Thu, 20 Nov 2008 04:00:00 +0000
        <BLANKLINE>
        Useful examples
        """
        stringlist = []
        for depth,comment in self.thread(flatten=flatten):
            ind = 2*depth+indent
            string_fn = getattr(comment, string_method_name)
            stringlist.append(string_fn(indent=ind))
        return '\n'.join(stringlist)

    def xml_thread(self, indent=0):
        return self.string_thread(string_method_name="xml", indent=indent)

    # methods for saving/loading/acessing settings and properties.

    def load_settings(self, settings_mapfile=None):
        if self.uuid == INVALID_UUID:
            return
        if settings_mapfile == None:
            settings_mapfile = self.storage.get(
                self.id.storage('values'), '\n')
        try:
            settings = mapfile.parse(settings_mapfile)
        except mapfile.InvalidMapfileContents, e:
            raise Exception('Invalid settings file for comment %s\n'
                            '(BE version missmatch?)' % self.id.user())
        self._setup_saved_settings(settings)

    def save_settings(self):
        if self.uuid == INVALID_UUID:
            return
        mf = mapfile.generate(self._get_saved_settings())
        self.storage.set(self.id.storage("values"), mf)

    def save(self):
        """
        Save any loaded contents to storage.

        However, if ``self.storage.is_writeable() == True``, then any
        changes are automatically written to storage as soon as they
        happen, so calling this method will just waste time (unless
        something else has been messing with your stored files).
        """
        if self.uuid == INVALID_UUID:
            return
        assert self.storage != None, "Can't save without storage"
        assert self.body != None, "Can't save blank comment"
        if self.bug != None:
            parent = self.bug.id.storage()
        else:
            parent = None
        self.storage.add(self.id.storage(), parent=parent, directory=True)
        self.storage.add(self.id.storage('values'), parent=self.id.storage(),
                         directory=False)
        self.storage.add(self.id.storage('body'), parent=self.id.storage(),
                         directory=False)
        self.save_settings()
        self._set_comment_body(new=self.body, force=True)

    def remove(self):
        for comment in self:
            comment.remove()
        if self.uuid != INVALID_UUID:
            self.storage.recursive_remove(self.id.storage())

    def add_reply(self, reply, allow_time_inversion=False):
        if self.uuid != INVALID_UUID:
            reply.in_reply_to = self.uuid
        self.append(reply)

    def new_reply(self, body=None, content_type=None):
        """
        >>> comm = Comment(bug=None, body="Some insightful remarks")
        >>> repA = comm.new_reply("Critique original comment")
        >>> repB = repA.new_reply("Begin flamewar :p")
        >>> repB.in_reply_to == repA.uuid
        True
        """
        reply = Comment(self.bug, body=body, content_type=content_type)
        self.add_reply(reply)
        return reply

    def comment_from_uuid(self, uuid, match_alt_id=True):
        """Use a uuid to look up a comment.

        >>> a = Comment(bug=None, uuid="a")
        >>> b = a.new_reply()
        >>> b.uuid = "b"
        >>> c = b.new_reply()
        >>> c.uuid = "c"
        >>> d = a.new_reply()
        >>> d.uuid = "d"
        >>> d.alt_id = "d-alt"
        >>> comm = a.comment_from_uuid("d")
        >>> id(comm) == id(d)
        True
        >>> comm = a.comment_from_uuid("d-alt")
        >>> id(comm) == id(d)
        True
        >>> comm = a.comment_from_uuid(None, match_alt_id=False)
        Traceback (most recent call last):
          ...
        KeyError: None
        """
        for comment in self.traverse():
            if comment.uuid == uuid:
                return comment
            if match_alt_id == True and uuid != None \
                    and comment.alt_id == uuid:
                return comment
        raise KeyError(uuid)

    # methods for id generation

    def sibling_uuids(self):
        if self.bug != None:
            return self.bug.uuids()
        return []


def cmp_attr(comment_1, comment_2, attr, invert=False):
    """
    Compare a general attribute between two comments using the conventional
    comparison rule for that attribute type.  If invert == True, sort
    *against* that convention.

    >>> attr="author"
    >>> commentA = Comment()
    >>> commentB = Comment()
    >>> commentA.author = "John Doe"
    >>> commentB.author = "Jane Doe"
    >>> cmp_attr(commentA, commentB, attr) > 0
    True
    >>> cmp_attr(commentA, commentB, attr, invert=True) < 0
    True
    >>> commentB.author = "John Doe"
    >>> cmp_attr(commentA, commentB, attr) == 0
    True
    """
    if not hasattr(comment_2, attr) :
        return 1
    val_1 = getattr(comment_1, attr)
    val_2 = getattr(comment_2, attr)
    if val_1 == None: val_1 = None
    if val_2 == None: val_2 = None

    if invert == True :
        return -cmp(val_1, val_2)
    else :
        return cmp(val_1, val_2)

# alphabetical rankings (a < z)
cmp_uuid = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "uuid")
cmp_author = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "author")
cmp_in_reply_to = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "in_reply_to")
cmp_content_type = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "content_type")
cmp_body = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "body")
cmp_extra_strings = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "extra_strings")
# chronological rankings (newer < older)
cmp_time = lambda comment_1, comment_2 : cmp_attr(comment_1, comment_2, "time", invert=True)


DEFAULT_CMP_FULL_CMP_LIST = \
    (cmp_time, cmp_author, cmp_content_type, cmp_body, cmp_in_reply_to,
     cmp_uuid, cmp_extra_strings)

class CommentCompoundComparator (object):
    def __init__(self, cmp_list=DEFAULT_CMP_FULL_CMP_LIST):
        self.cmp_list = cmp_list
    def __call__(self, comment_1, comment_2):
        for comparison in self.cmp_list :
            val = comparison(comment_1, comment_2)
            if val != 0 :
                return val
        return 0

cmp_full = CommentCompoundComparator()

if libbe.TESTING == True:
    suite = doctest.DocTestSuite()
