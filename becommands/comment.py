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
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Add a comment to a bug"""
from libbe import cmdutil, bugdir, editor
import os
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> import time
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> execute(["a", "This is a comment about a"], test=True)
    >>> bd._clear_bugs()
    >>> bug = bd.bug_from_shortname("a")
    >>> bug.load_comments()
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    This is a comment about a
    <BLANKLINE>
    >>> comment.From == bd.user_id
    True
    >>> comment.time <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True

    >>> if 'EDITOR' in os.environ:
    ...     del os.environ["EDITOR"]
    >>> execute(["b"], test=True)
    Traceback (most recent call last):
    UserError: No comment supplied, and EDITOR not specified.

    >>> os.environ["EDITOR"] = "echo 'I like cheese' > "
    >>> execute(["b"], test=True)
    >>> bd._clear_bugs()
    >>> bug = bd.bug_from_shortname("b")
    >>> bug.load_comments()
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    I like cheese
    <BLANKLINE>
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) == 0:
        raise cmdutil.UsageError("Please specify a bug or comment id.")
    if len(args) > 2:
        raise cmdutil.UsageError("Too many arguments.")
    
    shortname = args[0]
    if shortname.count(':') > 1:
        raise cmdutil.UserError("Invalid id '%s'." % shortname)        
    elif shortname.count(':') == 1:
        # Split shortname generated by Comment.comment_shortnames()
        bugname = shortname.split(':')[0]
        is_reply = True
    else:
        bugname = shortname
        is_reply = False
    
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    bug = bd.bug_from_shortname(bugname)
    bug.load_comments()
    if is_reply:
        parent = bug.comment_root.comment_from_shortname(shortname,
                                                         bug_shortname=bugname)
    else:
        parent = bug.comment_root
    
    if len(args) == 1:
        try:
            body = editor.editor_string("Please enter your comment above")
        except editor.CantFindEditor, e:
            raise cmdutil.UserError, "No comment supplied, and EDITOR not specified."
        if body is None:
            raise cmdutil.UserError("No comment entered.")
        body = body.decode('utf-8')
    else:
        body = args[1]
        if not body.endswith('\n'):
            body+='\n'
    
    comment = parent.new_reply(body=body)
    bd.save()

def get_parser():
    parser = cmdutil.CmdOptionParser("be comment ID COMMENT")
    return parser

longhelp="""
To add a comment to a bug, use the bug ID as the argument.  To reply to another
comment, specify the comment name (as shown in "be show" output).

$EDITOR is used to launch an editor.  If unspecified, no comment will be
created.
"""

def help():
    return get_parser().help_str() + longhelp

def complete(options, args, parser):
    for option,value in cmdutil.option_value_pairs(options, parser):
        if value == "--complete":
            # no argument-options at the moment, so this is future-proofing
            raise cmdutil.GetCompletions()
    for pos,value in enumerate(args):
        if value == "--complete":
            if pos == 0: # fist positional argument is a bug or comment id
                if len(args) >= 2:
                    partial = args[1].split(':')[0] # take only bugid portion
                else:
                    partial = ""
                ids = []
                try:
                    bd = bugdir.BugDir(from_disk=True,
                                       manipulate_encodings=False)
                    bugs = []
                    for uuid in bd.list_uuids():
                        if uuid.startswith(partial):
                            bug = bd.bug_from_uuid(uuid)
                            if bug.active == True:
                                bugs.append(bug)
                    for bug in bugs:
                        shortname = bd.bug_shortname(bug)
                        ids.append(shortname)
                        bug.load_comments()
                        for id,comment in bug.comment_shortnames(shortname):
                            ids.append(id)
                except bugdir.NoBugDir:
                    pass
                raise cmdutil.GetCompletions(ids)
            raise cmdutil.GetCompletions()
