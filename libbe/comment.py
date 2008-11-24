# Bugs Everywhere, a distributed bugtracker
# Copyright (C) 2005 Aaron Bentley and Panometrics, Inc.
# <abentley@panoramicfeedback.com>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#    MA 02110-1301, USA
import os
import os.path
import time
import textwrap
import doctest

from beuuid import uuid_gen
import mapfile
from tree import Tree
import utility

INVALID_UUID = "!!~~\n INVALID-UUID \n~~!!"

def _list_to_root(comments, bug):
    """
    Convert a raw list of comments to single (dummy) root comment.  We
    use a dummy root comment, because there can be several comment
    threads rooted on the same parent bug.  To simplify comment
    interaction, we condense these threads into a single thread with a
    Comment dummy root.
    
    No Comment method should use the dummy comment.
    """
    root_comments = []
    uuid_map = {}
    for comment in comments:
        assert comment.uuid != None
        uuid_map[comment.uuid] = comment
    for comm in comments:
        if comm.in_reply_to == None:
            root_comments.append(comm)
        else:
            parentUUID = comm.in_reply_to
            parent = uuid_map[parentUUID]
            parent.add_reply(comm)
    dummy_root = Comment(bug, uuid=INVALID_UUID)
    dummy_root.extend(root_comments)
    return dummy_root

def loadComments(bug):
    path = bug.get_path("comments")
    if not os.path.isdir(path):
        return Comment(bug, uuid=INVALID_UUID)
    comments = []
    for uuid in os.listdir(path):
        if uuid.startswith('.'):
            continue
        comm = Comment(bug, uuid, from_disk=True)
        comments.append(comm)
    return _list_to_root(comments, bug)

def saveComments(bug):
    path = bug.get_path("comments")
    bug.rcs.mkdir(path)
    for comment in bug.comment_root.traverse():
        comment.save()

class Comment(Tree):
    def __init__(self, bug=None, uuid=None, from_disk=False,
                 in_reply_to=None, body=None):
        """
        Set from_disk=True to load an old bug.
        Set from_disk=False to create a new bug.

        The uuid option is required when from_disk==True.
        
        The in_reply_to and body options are only used if
        from_disk==False (the default).  When from_disk==True, they are
        loaded from the bug database.
        
        in_reply_to should be the uuid string of the parent comment.
        """
        Tree.__init__(self)
        self.bug = bug
        if bug != None:
            self.rcs = bug.rcs
        else:
            self.rcs = None
        if from_disk == True: 
            self.uuid = uuid 
            self.load()
        else:
            if uuid != None:
                self.uuid = uuid
            else:
                self.uuid = uuid_gen()
            self.time = time.time()
            if self.rcs != None:
                self.From = self.rcs.get_user_id()
            else:
                self.From = None
            self.in_reply_to = in_reply_to
            self.content_type = "text/plain"
            self.body = body

    def traverse(self, *args, **kwargs):
        """Avoid working with the possible dummy root comment"""
        for comment in Tree.traverse(self, *args, **kwargs):
            if comment.uuid == INVALID_UUID:
                continue
            yield comment

    def _clean_string(self, value):
        """
        >>> comm = Comment()
        >>> comm._clean_string(None)
        ''
        >>> comm._clean_string("abc")
        'abc'
        """
        if value == None:
            return ""
        return value

    def string(self, indent=0, shortname=None):
        """
        >>> comm = Comment(bug=None, body="Some\\ninsightful\\nremarks\\n")
        >>> comm.time = utility.str_to_time("Thu, 20 Nov 2008 15:55:11 +0000")
        >>> print comm.string(indent=2, shortname="com-1")
          --------- Comment ---------
          Name: com-1
          From: 
          Date: Thu, 20 Nov 2008 15:55:11 +0000
        <BLANKLINE>
          Some insightful remarks
        """
        if shortname == None:
            shortname = self.uuid
        lines = []
        lines.append("--------- Comment ---------")
        lines.append("Name: %s" % shortname)
        lines.append("From: %s" % self._clean_string(self.From))
        lines.append("Date: %s" % utility.time_to_str(self.time))
        lines.append("")
        #lines.append(textwrap.fill(self._clean_string(self.body),
        #                           width=(79-indent)))
        lines.append(self._clean_string(self.body))
        # some comments shouldn't be wrapped...
        
        istring = ' '*indent
        sep = '\n' + istring
        return istring + sep.join(lines).rstrip('\n')

    def __str__(self):
        """
        >>> comm = Comment(bug=None, body="Some insightful remarks")
        >>> comm.uuid = "com-1"
        >>> comm.time = utility.str_to_time("Thu, 20 Nov 2008 15:55:11 +0000")
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

    def load(self):
        map = mapfile.map_load(self.rcs, self.get_path("values"))
        self.time = utility.str_to_time(map["Date"])
        self.From = map["From"]
        self.in_reply_to = map.get("In-reply-to")
        self.content_type = map.get("Content-type", "text/plain")
        self.body = self.rcs.get_file_contents(self.get_path("body"))

    def save(self):
        assert self.rcs != None
        map_file = {"Date": utility.time_to_str(self.time)}
        self._add_headers(map_file, ("From", "in_reply_to", "content_type"))
        self.rcs.mkdir(self.get_path())
        mapfile.map_save(self.rcs, self.get_path("values"), map_file)
        self.rcs.set_file_contents(self.get_path("body"), self.body)
 
    def _add_headers(self, map, names):
        map_names = {}
        for name in names:
            map_names[name] = self._pyname_to_header(name)
        self._add_attrs(map, map_names)

    def _pyname_to_header(self, name):
        return name.capitalize().replace('_', '-')

    def _add_attrs(self, map, map_names):
        for name in map_names.keys():
            value = getattr(self, name)
            if value is not None:
                map[map_names[name]] = value

    def remove(self):
        for comment in self.traverse():
            path = comment.get_path()
            self.rcs.recursive_remove(path)

    def add_reply(self, reply):
        if reply.time != None and self.time != None:
            assert reply.time >= self.time
        if self.uuid != INVALID_UUID:
            reply.in_reply_to = self.uuid
        self.append(reply)

    def new_reply(self, body=None):
        """
        >>> comm = Comment(bug=None, body="Some insightful remarks")
        >>> repA = comm.new_reply("Critique original comment")
        >>> repB = repA.new_reply("Begin flamewar :p")
        """
        reply = Comment(self.bug, body=body)
        self.add_reply(reply)
        return reply

    def string_thread(self, name_map={}, indent=0,
                      auto_name_map=False, bug_shortname=None):
        """
        Return a sting displaying a thread of comments.
        bug_shortname is only used if auto_name_map == True.

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
        >>> print a.string_thread()
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
        for depth,comment in self.thread(flatten=True):
            ind = 2*depth+indent
            if comment.uuid in name_map:
                sname = name_map[comment.uuid]
            else:
                sname = None
            stringlist.append(comment.string(indent=ind, shortname=sname))
        return '\n'.join(stringlist)

    def comment_shortnames(self, bug_shortname=""):
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
        raise KeyError(comment_shortname)

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
