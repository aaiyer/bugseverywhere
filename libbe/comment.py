# Bugs Everywhere, a distributed bugtracker
# Copyright (C) 2008-2009 Gianluca Montecchi <gian@grys.it>
#                         Thomas Habets <thomas@habets.pp.se>
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

"""
Define the Comment class for representing bug comments.
"""

import base64
import os
import os.path
import sys
import time
import types
try: # import core module, Python >= 2.5
    from xml.etree import ElementTree
except ImportError: # look for non-core module
    from elementtree import ElementTree
import xml.sax.saxutils
import doctest

from beuuid import uuid_gen
from properties import Property, doc_property, local_property, \
    defaulting_property, checked_property, cached_property, \
    primed_property, change_hook_property, settings_property
import settings_object
import mapfile
from tree import Tree
import utility


class InvalidShortname(KeyError):
    def __init__(self, shortname, shortnames):
        msg = "Invalid shortname %s\n%s" % (shortname, shortnames)
        KeyError.__init__(self, msg)
        self.shortname = shortname
        self.shortnames = shortnames

class MissingReference(ValueError):
    def __init__(self, comment):
        msg = "Missing reference to %s" % (comment.in_reply_to)
        ValueError.__init__(self, msg)
        self.reference = comment.in_reply_to
        self.comment = comment

class DiskAccessRequired (Exception):
    def __init__(self, goal):
        msg = "Cannot %s without accessing the disk" % goal
        Exception.__init__(self, msg)

INVALID_UUID = "!!~~\n INVALID-UUID \n~~!!"

def loadComments(bug, load_full=False):
    """
    Set load_full=True when you want to load the comment completely
    from disk *now*, rather than waiting and lazy loading as required.
    """
    if bug.sync_with_disk == False:
        raise DiskAccessRequired("load comments")
    path = bug.get_path("comments")
    if not os.path.exists(path):
        return Comment(bug, uuid=INVALID_UUID)
    comments = []
    for uuid in os.listdir(path):
        if uuid.startswith('.'):
            continue
        comm = Comment(bug, uuid, from_disk=True)
        comm.set_sync_with_disk(bug.sync_with_disk)
        if load_full == True:
            comm.load_settings()
            dummy = comm.body # force the body to load
        comments.append(comm)
    bug.comment_root = Comment(bug, uuid=INVALID_UUID)
    bug.add_comments(comments)
    return bug.comment_root

def saveComments(bug):
    if bug.sync_with_disk == False:
        raise DiskAccessRequired("save comments")
    for comment in bug.comment_root.traverse():
        comment.save()


class Comment(Tree, settings_object.SavedSettingsObject):
    """
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
        if self.vcs != None and self.sync_with_disk == True:
            import vcs
            binary = not self.content_type.startswith("text/")
            return self.vcs.get_file_contents(self.get_path("body"), binary=binary)
    def _set_comment_body(self, old=None, new=None, force=False):
        if (self.vcs != None and self.sync_with_disk == True) or force==True:
            assert new != None, "Can't save empty comment"
            binary = not self.content_type.startswith("text/")
            self.vcs.set_file_contents(self.get_path("body"), new, binary=binary)

    @Property
    @change_hook_property(hook=_set_comment_body)
    @cached_property(generator=_get_comment_body)
    @local_property("body")
    @doc_property(doc="The meat of the comment")
    def body(): return {}

    def _get_vcs(self):
        if hasattr(self.bug, "vcs"):
            return self.bug.vcs

    @Property
    @cached_property(generator=_get_vcs)
    @local_property("vcs")
    @doc_property(doc="A revision control system instance.")
    def vcs(): return {}

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

    def __init__(self, bug=None, uuid=None, from_disk=False,
                 in_reply_to=None, body=None):
        """
        Set from_disk=True to load an old comment.
        Set from_disk=False to create a new comment.

        The uuid option is required when from_disk==True.
        
        The in_reply_to and body options are only used if
        from_disk==False (the default).  When from_disk==True, they are
        loaded from the bug database.
        
        in_reply_to should be the uuid string of the parent comment.
        """
        Tree.__init__(self)
        settings_object.SavedSettingsObject.__init__(self)
        self.bug = bug
        self.uuid = uuid 
        if from_disk == True: 
            self.sync_with_disk = True
        else:
            self.sync_with_disk = False
            if uuid == None:
                self.uuid = uuid_gen()
            self.time = int(time.time()) # only save to second precision
            if self.vcs != None:
                self.author = self.vcs.get_user_id()
            self.in_reply_to = in_reply_to
            self.body = body

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
        Name: com-1
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

    def xml(self, indent=0, shortname=None):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.uuid = "0123"
        >>> comm.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> print comm.xml(indent=2, shortname="com-1")
          <comment>
            <uuid>0123</uuid>
            <short-name>com-1</short-name>
            <author></author>
            <date>Thu, 01 Jan 1970 00:00:00 +0000</date>
            <content-type>text/plain</content-type>
            <body>Some
        insightful
        remarks</body>
          </comment>
        """
        if shortname == None:
            shortname = self.uuid
        if self.content_type.startswith('text/'):
            body = (self.body or '').rstrip('\n')
        else:
            maintype,subtype = self.content_type.split('/',1)
            msg = email.mime.base.MIMEBase(maintype, subtype)
            msg.set_payload(self.body or '')
            email.encoders.encode_base64(msg)
            body = base64.encodestring(self.body or '')
        info = [('uuid', self.uuid),
                ('alt-id', self.alt_id),
                ('short-name', shortname),
                ('in-reply-to', self.in_reply_to),
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

    def from_xml(self, xml_string, verbose=True):
        """
        Note: If alt-id is not given, translates any <uuid> fields to
        <alt-id> fields.
        >>> commA = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> commA.uuid = "0123"
        >>> commA.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> commA.author = u'Fran\xe7ois'
        >>> commA.extra_strings += ['TAG: very helpful']
        >>> xml = commA.xml(shortname="com-1")
        >>> commB = Comment()
        >>> commB.from_xml(xml, verbose=True)
        >>> commB.explicit_attrs
        ['author', 'date', 'content_type', 'body', 'alt_id']
        >>> commB.xml(shortname="com-1") == xml
        False
        >>> commB.uuid = commB.alt_id
        >>> commB.alt_id = None
        >>> commB.xml(shortname="com-1") == xml
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
                    text = text.decode('unicode_escape').strip()
                if child.tag == 'uuid':
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
        if self.alt_id == None:
            self.explicit_attrs.append('alt_id')
            self.alt_id = uuid
        if body != None:
            if self.content_type.startswith('text/'):
                self.body = body+'\n' # restore trailing newline
            else:
                self.body = base64.decodestring(body)
        self.extra_strings = estrs

    def merge(self, other, allow_changes=True):
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
        >>> commA.merge(commB, allow_changes=False)
        Traceback (most recent call last):
          ...
        ValueError: Merge would change author "Frank"->"John" for comment 0123
        >>> commA.merge(commB)
        >>> print commA.xml()
        <comment>
          <uuid>0123</uuid>
          <short-name>0123</short-name>
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
                if allow_changes == True:
                    setattr(self, attr, new)
                else:
                    raise ValueError, \
                        'Merge would change %s "%s"->"%s" for comment %s' \
                        % (attr, old, new, self.uuid)
        if allow_changes == False and len(other.extra_strings) > 0:
            raise ValueError, \
                'Merge would change extra_strings for comment %s' % self.uuid
        for estr in other.extra_strings:
            if not estr in self.extra_strings:
                self.extra_strings.append(estr)

    def string(self, indent=0, shortname=None):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.date = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> print comm.string(indent=2, shortname="com-1")
          --------- Comment ---------
          Name: com-1
          From: 
          Date: Thu, 01 Jan 1970 00:00:00 +0000
        <BLANKLINE>
          Some
          insightful
          remarks
        """
        if shortname == None:
            shortname = self.uuid
        lines = []
        lines.append("--------- Comment ---------")
        lines.append("Name: %s" % shortname)
        lines.append("From: %s" % (self._setting_attr_string("author")))
        lines.append("Date: %s" % self.date)
        lines.append("")
        if self.content_type.startswith("text/"):
            lines.extend((self.body or "").splitlines())
        else:
            lines.append("Content type %s not printable.  Try XML output instead" % self.content_type)
        
        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def string_thread(self, string_method_name="string", name_map={},
                      indent=0, flatten=True,
                      auto_name_map=False, bug_shortname=None):
        """
        Return a string displaying a thread of comments.
        bug_shortname is only used if auto_name_map == True.
        
        string_method_name (defaults to "string") is the name of the
        Comment method used to generate the output string for each
        Comment in the thread.  The method must take the arguments
        indent and shortname.
        
        SIDE-EFFECT: if auto_name_map==True, calls comment_shortnames()
        which will sort the tree by comment.time.  Avoid by calling
          name_map = {}
          for shortname,comment in comm.comment_shortnames(bug_shortname):
              name_map[comment.uuid] = shortname
          comm.sort(key=lambda c : c.author) # your sort
          comm.string_thread(name_map=name_map)

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
        Name: a
        From: 
        Date: Thu, 20 Nov 2008 01:00:00 +0000
        <BLANKLINE>
        Insightful remarks
          --------- Comment ---------
          Name: b
          From: 
          Date: Thu, 20 Nov 2008 02:00:00 +0000
        <BLANKLINE>
          Critique original comment
          --------- Comment ---------
          Name: c
          From: 
          Date: Thu, 20 Nov 2008 03:00:00 +0000
        <BLANKLINE>
          Begin flamewar :p
        --------- Comment ---------
        Name: d
        From: 
        Date: Thu, 20 Nov 2008 04:00:00 +0000
        <BLANKLINE>
        Useful examples
        >>> print a.string_thread(auto_name_map=True, bug_shortname="bug-1")
        --------- Comment ---------
        Name: bug-1:1
        From: 
        Date: Thu, 20 Nov 2008 01:00:00 +0000
        <BLANKLINE>
        Insightful remarks
          --------- Comment ---------
          Name: bug-1:2
          From: 
          Date: Thu, 20 Nov 2008 02:00:00 +0000
        <BLANKLINE>
          Critique original comment
          --------- Comment ---------
          Name: bug-1:3
          From: 
          Date: Thu, 20 Nov 2008 03:00:00 +0000
        <BLANKLINE>
          Begin flamewar :p
        --------- Comment ---------
        Name: bug-1:4
        From: 
        Date: Thu, 20 Nov 2008 04:00:00 +0000
        <BLANKLINE>
        Useful examples
        """
        if auto_name_map == True:
            name_map = {}
            for shortname,comment in self.comment_shortnames(bug_shortname):
                name_map[comment.uuid] = shortname
        stringlist = []
        for depth,comment in self.thread(flatten=flatten):
            ind = 2*depth+indent
            if comment.uuid in name_map:
                sname = name_map[comment.uuid]
            else:
                sname = None
            string_fn = getattr(comment, string_method_name)
            stringlist.append(string_fn(indent=ind, shortname=sname))
        return '\n'.join(stringlist)

    def xml_thread(self, name_map={}, indent=0,
                   auto_name_map=False, bug_shortname=None):
        return self.string_thread(string_method_name="xml", name_map=name_map,
                                  indent=indent, auto_name_map=auto_name_map,
                                  bug_shortname=bug_shortname)

    # methods for saving/loading/acessing settings and properties.

    def get_path(self, *args):
        dir = os.path.join(self.bug.get_path("comments"), self.uuid)
        if len(args) == 0:
            return dir
        assert args[0] in ["values", "body"], str(args)
        return os.path.join(dir, *args)

    def set_sync_with_disk(self, value):
        self.sync_with_disk = value

    def load_settings(self):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("load settings")
        self.settings = mapfile.map_load(self.vcs, self.get_path("values"))
        self._setup_saved_settings()

    def save_settings(self):
        if self.sync_with_disk == False:
            raise DiskAccessRequired("save settings")
        self.vcs.mkdir(self.get_path())
        path = self.get_path("values")
        mapfile.map_save(self.vcs, path, self._get_saved_settings())

    def save(self):
        """
        Save any loaded contents to disk.
        
        However, if self.sync_with_disk = True, then any changes are
        automatically written to disk as soon as they happen, so
        calling this method will just waste time (unless something
        else has been messing with your on-disk files).
        """
        sync_with_disk = self.sync_with_disk
        if sync_with_disk == False:
            self.set_sync_with_disk(True)
        assert self.body != None, "Can't save blank comment"
        self.save_settings()
        self._set_comment_body(new=self.body, force=True)
        if sync_with_disk == False:
            self.set_sync_with_disk(False)

    def remove(self):
        if self.sync_with_disk == False and self.uuid != INVALID_UUID:
            raise DiskAccessRequired("remove")
        for comment in self.traverse():
            path = comment.get_path()
            self.vcs.recursive_remove(path)

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
        reply = Comment(self.bug, body=body)
        if content_type != None: # set before saving body to decide binary format
            reply.content_type = content_type
        if self.bug != None:
            reply.set_sync_with_disk(self.bug.sync_with_disk)
        if reply.sync_with_disk == True:
            reply.save()
        self.add_reply(reply)
        return reply

    def comment_shortnames(self, bug_shortname=None):
        """
        Iterate through (id, comment) pairs, in time order.
        (This is a user-friendly id, not the comment uuid).

        SIDE-EFFECT : will sort the comment tree by comment.time

        >>> a = Comment(bug=None, uuid="a")
        >>> b = a.new_reply()
        >>> b.uuid = "b"
        >>> c = b.new_reply()
        >>> c.uuid = "c"
        >>> d = a.new_reply()
        >>> d.uuid = "d"
        >>> for id,name in a.comment_shortnames("bug-1"):
        ...     print id, name.uuid
        bug-1:1 a
        bug-1:2 b
        bug-1:3 c
        bug-1:4 d
        >>> for id,name in a.comment_shortnames():
        ...     print id, name.uuid
        :1 a
        :2 b
        :3 c
        :4 d
        """
        if bug_shortname == None:
            bug_shortname = ""
        self.sort(key=lambda comm : comm.time)
        for num,comment in enumerate(self.traverse()):
            yield ("%s:%d" % (bug_shortname, num+1), comment)

    def comment_from_shortname(self, comment_shortname, *args, **kwargs):
        """
        Use a comment shortname to look up a comment.
        >>> a = Comment(bug=None, uuid="a")
        >>> b = a.new_reply()
        >>> b.uuid = "b"
        >>> c = b.new_reply()
        >>> c.uuid = "c"
        >>> d = a.new_reply()
        >>> d.uuid = "d"
        >>> comm = a.comment_from_shortname("bug-1:3", bug_shortname="bug-1")
        >>> id(comm) == id(c)
        True
        """
        for cur_name, comment in self.comment_shortnames(*args, **kwargs):
            if comment_shortname == cur_name:
                return comment
        raise InvalidShortname(comment_shortname,
                               list(self.comment_shortnames(*args, **kwargs)))

    def comment_from_uuid(self, uuid, match_alt_id=True):
        """
        Use a comment shortname to look up a comment.
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

suite = doctest.DocTestSuite()
