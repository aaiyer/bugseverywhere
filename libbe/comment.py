# Bugs Everywhere, a distributed bugtracker
# Copyright (C) 2008-2009 Chris Ball <cjb@laptop.org>
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

class InvalidXML(ValueError):
    def __init__(self, element, comment):
        msg = "Invalid comment xml: %s\n  %s\n" \
            % (comment, ElementTree.tostring(element))
        ValueError.__init__(self, msg)
        self.element = element
        self.comment = comment

class MissingReference(ValueError):
    def __init__(self, comment):
        msg = "Missing reference to %s" % (comment.in_reply_to)
        ValueError.__init__(self, msg)
        self.reference = comment.in_reply_to
        self.comment = comment

INVALID_UUID = "!!~~\n INVALID-UUID \n~~!!"

def list_to_root(comments, bug, root=None,
                 ignore_missing_references=False):
    """
    Convert a raw list of comments to single root comment.  We use a
    dummy root comment by default, because there can be several
    comment threads rooted on the same parent bug.  To simplify
    comment interaction, we condense these threads into a single
    thread with a Comment dummy root.  Can also be used to append
    a list of subcomments to a non-dummy root comment, so long as
    all the new comments are descendants of the root comment.
    
    No Comment method should use the dummy comment.
    """
    root_comments = []
    uuid_map = {}
    for comment in comments:
        assert comment.uuid != None
        uuid_map[comment.uuid] = comment
    for comment in comments:
        if comment.alt_id != None and comment.alt_id not in uuid_map:
            uuid_map[comment.alt_id] = comment
    if root == None:
        root = Comment(bug, uuid=INVALID_UUID)
    else:
        uuid_map[root.uuid] = root
    for comm in comments:
        if comm.in_reply_to == INVALID_UUID:
            comm.in_reply_to = None
        rep = comm.in_reply_to
        if rep == None or rep == bug.uuid:
            root_comments.append(comm)
        else:
            parentUUID = comm.in_reply_to
            try:
                parent = uuid_map[parentUUID]
                parent.add_reply(comm)
            except KeyError, e:
                if ignore_missing_references == True:
                    print >> sys.stderr, \
                        "Ignoring missing reference to %s" % parentUUID
                    comm.in_reply_to = None
                    root_comments.append(comm)
                else:
                    raise MissingReference(comm)
    root.extend(root_comments)
    return root

def loadComments(bug, load_full=False):
    """
    Set load_full=True when you want to load the comment completely
    from disk *now*, rather than waiting and lazy loading as required.
    """
    path = bug.get_path("comments")
    if not os.path.isdir(path):
        return Comment(bug, uuid=INVALID_UUID)
    comments = []
    for uuid in os.listdir(path):
        if uuid.startswith('.'):
            continue
        comm = Comment(bug, uuid, from_disk=True)
        if load_full == True:
            comm.load_settings()
            dummy = comm.body # force the body to load
        comments.append(comm)
    return list_to_root(comments, bug)

def saveComments(bug):
    path = bug.get_path("comments")
    bug.rcs.mkdir(path)
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

    @_versioned_property(name="From",
                         doc="The author of the comment")
    def From(): return {}

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
    def time_string(): return {}

    def _get_time(self):
        if self.time_string == None:
            return None
        return utility.str_to_time(self.time_string)
    def _set_time(self, value):
        self.time_string = utility.time_to_str(value)
    time = property(fget=_get_time,
                    fset=_set_time,
                    doc="An integer version of .time_string")

    def _get_comment_body(self):
        if self.rcs != None and self.sync_with_disk == True:
            import rcs
            binary = not self.content_type.startswith("text/")
            return self.rcs.get_file_contents(self.get_path("body"), binary=binary)
    def _set_comment_body(self, old=None, new=None, force=False):
        if (self.rcs != None and self.sync_with_disk == True) or force==True:
            assert new != None, "Can't save empty comment"
            binary = not self.content_type.startswith("text/")
            self.rcs.set_file_contents(self.get_path("body"), new, binary=binary)

    @Property
    @change_hook_property(hook=_set_comment_body)
    @cached_property(generator=_get_comment_body)
    @local_property("body")
    @doc_property(doc="The meat of the comment")
    def body(): return {}

    def _get_rcs(self):
        if hasattr(self.bug, "rcs"):
            return self.bug.rcs

    @Property
    @cached_property(generator=_get_rcs)
    @local_property("rcs")
    @doc_property(doc="A revision control system instance.")
    def rcs(): return {}

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
            if self.rcs != None:
                self.From = self.rcs.get_user_id()
            self.in_reply_to = in_reply_to
            self.body = body

    def traverse(self, *args, **kwargs):
        """Avoid working with the possible dummy root comment"""
        for comment in Tree.traverse(self, *args, **kwargs):
            if comment.uuid == INVALID_UUID:
                continue
            yield comment

    def _setting_attr_string(self, setting):
        value = getattr(self, setting)
        if value in [None, settings_object.EMPTY]:
            return ""
        else:
            return str(value)

    def xml(self, indent=0, shortname=None):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.uuid = "0123"
        >>> comm.time_string = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> print comm.xml(indent=2, shortname="com-1")
          <comment>
            <uuid>0123</uuid>
            <short-name>com-1</short-name>
            <from></from>
            <date>Thu, 01 Jan 1970 00:00:00 +0000</date>
            <content-type>text/plain</content-type>
            <body>Some
        insightful
        remarks</body>
          </comment>
        """
        if shortname == None:
            shortname = self.uuid
        if self.content_type.startswith("text/"):
            body = (self.body or "").rstrip('\n')
        else:
            maintype,subtype = self.content_type.split('/',1)
            msg = email.mime.base.MIMEBase(maintype, subtype)
            msg.set_payload(self.body or "")
            email.encoders.encode_base64(msg)
            body = base64.encodestring(self.body or "")
        info = [("uuid", self.uuid),
                ("alt-id", self.alt_id),
                ("short-name", shortname),
                ("in-reply-to", self.in_reply_to),
                ("from", self._setting_attr_string("From")),
                ("date", self.time_string),
                ("content-type", self.content_type),
                ("body", body)]
        lines = ["<comment>"]
        for (k,v) in info:
            if v != None:
                lines.append('  <%s>%s</%s>' % (k,xml.sax.saxutils.escape(v),k))
        lines.append("</comment>")
        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def from_xml(self, xml_string, verbose=True):
        """
        Note: If alt-id is not given, translates any <uuid> fields to
        <alt-id> fields.
        >>> commA = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> commA.uuid = "0123"
        >>> commA.time_string = "Thu, 01 Jan 1970 00:00:00 +0000"
        >>> xml = commA.xml(shortname="com-1")
        >>> commB = Comment()
        >>> commB.from_xml(xml)
        >>> attrs=['uuid','alt_id','in_reply_to','From','time_string','content_type','body']
        >>> for attr in attrs: # doctest: +ELLIPSIS
        ...     if getattr(commB, attr) != getattr(commA, attr):
        ...         estr = "Mismatch on %s: '%s' should be '%s'"
        ...         args = (attr, getattr(commB, attr), getattr(commA, attr))
        ...         print estr % args
        Mismatch on uuid: '...' should be '0123'
        Mismatch on alt_id: '0123' should be 'None'
        >>> print commB.alt_id
        0123
        >>> commA.From
        >>> commB.From
        """
        if type(xml_string) == types.UnicodeType:
            xml_string = xml_string.strip().encode("unicode_escape")
        comment = ElementTree.XML(xml_string)
        if comment.tag != "comment":
            raise InvalidXML(comment, "root element must be <comment>")
        tags=['uuid','alt-id','in-reply-to','from','date','content-type','body']
        uuid = None
        body = None
        for child in comment.getchildren():
            if child.tag == "short-name":
                pass
            elif child.tag in tags:
                if child.text == None or len(child.text) == 0:
                    text = settings_object.EMPTY
                else:
                    text = xml.sax.saxutils.unescape(child.text)
                    text = unicode(text).decode("unicode_escape").strip()
                if child.tag == "uuid":
                    uuid = text
                    continue # don't set the bug's uuid tag.
                if child.tag == "body":
                    body = text
                    continue # don't set the bug's body yet.
                elif child.tag == 'from':
                    attr_name = "From"
                elif child.tag == 'date':
                    attr_name = 'time_string'
                else:
                    attr_name = child.tag.replace('-','_')
                setattr(self, attr_name, text)
            elif verbose == True:
                print >> sys.stderr, "Ignoring unknown tag %s in %s" \
                    % (child.tag, comment.tag)
        if self.alt_id == None and uuid not in [None, self.uuid]:
            self.alt_id = uuid
        if body != None:
            if self.content_type.startswith("text/"):
                self.body = body+"\n" # restore trailing newline
            else:
                self.body = base64.decodestring(body)

    def string(self, indent=0, shortname=None):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.time_string = "Thu, 01 Jan 1970 00:00:00 +0000"
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
        lines.append("From: %s" % (self._setting_attr_string("From")))
        lines.append("Date: %s" % self.time_string)
        lines.append("")
        if self.content_type.startswith("text/"):
            lines.extend((self.body or "").splitlines())
        else:
            lines.append("Content type %s not printable.  Try XML output instead" % self.content_type)
        
        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def __str__(self):
        """
        >>> comm = Comment(bug=None, body="Some insightful remarks")
        >>> comm.uuid = "com-1"
        >>> comm.time_string = "Thu, 20 Nov 2008 15:55:11 +0000"
        >>> comm.From = "Jane Doe <jdoe@example.com>"
        >>> print comm
        --------- Comment ---------
        Name: com-1
        From: Jane Doe <jdoe@example.com>
        Date: Thu, 20 Nov 2008 15:55:11 +0000
        <BLANKLINE>
        Some insightful remarks
        """
        return self.string()

    def get_path(self, name=None):
        my_dir = os.path.join(self.bug.get_path("comments"), self.uuid)
        if name is None:
            return my_dir
        assert name in ["values", "body"]
        return os.path.join(my_dir, name)

    def load_settings(self):
        self.settings = mapfile.map_load(self.rcs, self.get_path("values"))
        self._setup_saved_settings()

    def save_settings(self):
        parent_dir = os.path.dirname(self.get_path())
        self.rcs.mkdir(parent_dir)
        self.rcs.mkdir(self.get_path())
        path = self.get_path("values")
        mapfile.map_save(self.rcs, path, self._get_saved_settings())

    def save(self):
        assert self.body != None, "Can't save blank comment"
        self.save_settings()
        self._set_comment_body(new=self.body, force=True)

    def remove(self):
        for comment in self.traverse():
            path = comment.get_path()
            self.rcs.recursive_remove(path)

    def add_reply(self, reply, allow_time_inversion=False):
        if self.uuid != INVALID_UUID:
            reply.in_reply_to = self.uuid
        self.append(reply)
        #raise Exception, "adding reply \n%s\n%s" % (self, reply)

    def new_reply(self, body=None):
        """
        >>> comm = Comment(bug=None, body="Some insightful remarks")
        >>> repA = comm.new_reply("Critique original comment")
        >>> repB = repA.new_reply("Begin flamewar :p")
        >>> repB.in_reply_to == repA.uuid
        True
        """
        reply = Comment(self.bug, body=body)
        self.add_reply(reply)
        return reply

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
          comm.sort(key=lambda c : c.From) # your sort
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

    def comment_from_uuid(self, uuid):
        """
        Use a comment shortname to look up a comment.
        >>> a = Comment(bug=None, uuid="a")
        >>> b = a.new_reply()
        >>> b.uuid = "b"
        >>> c = b.new_reply()
        >>> c.uuid = "c"
        >>> d = a.new_reply()
        >>> d.uuid = "d"
        >>> comm = a.comment_from_uuid("d")
        >>> id(comm) == id(d)
        True
        """
        for comment in self.traverse():
            if comment.uuid == uuid:
                return comment
        raise KeyError(uuid)

suite = doctest.DocTestSuite()
