# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Gianluca Montecchi <gian@grys.it>
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
"""Add a comment to a bug"""
from libbe import cmdutil, bugdir, comment, editor
import os
import sys
__desc__ = __doc__

def execute(args, manipulate_encodings=True):
    """
    >>> import time
    >>> bd = bugdir.SimpleBugDir()
    >>> os.chdir(bd.root)
    >>> execute(["a", "This is a comment about a"], manipulate_encodings=False)
    >>> bd._clear_bugs()
    >>> bug = cmdutil.bug_from_id(bd, "a")
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    This is a comment about a
    <BLANKLINE>
    >>> comment.author == bd.user_id
    True
    >>> comment.time <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True

    >>> if 'EDITOR' in os.environ:
    ...     del os.environ["EDITOR"]
    >>> execute(["b"], manipulate_encodings=False)
    Traceback (most recent call last):
    UserError: No comment supplied, and EDITOR not specified.

    >>> os.environ["EDITOR"] = "echo 'I like cheese' > "
    >>> execute(["b"], manipulate_encodings=False)
    >>> bd._clear_bugs()
    >>> bug = cmdutil.bug_from_id(bd, "b")
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    I like cheese
    <BLANKLINE>
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    complete(options, args, parser)
    if len(args) == 0:
        raise cmdutil.UsageError("Please specify a bug or comment id.")
    if len(args) > 2:
        raise cmdutil.UsageError("Too many arguments.")

    shortname = args[0]

    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    bug, parent = cmdutil.bug_comment_from_id(bd, shortname)

    if len(args) == 1: # try to launch an editor for comment-body entry
        try:
            if parent == bug.comment_root:
                parent_body = bug.summary+"\n"
            else:
                parent_body = parent.body
            estr = "Please enter your comment above\n\n> %s\n" \
                % ("\n> ".join(parent_body.splitlines()))
            body = editor.editor_string(estr)
        except editor.CantFindEditor, e:
            raise cmdutil.UserError, "No comment supplied, and EDITOR not specified."
        if body is None:
            raise cmdutil.UserError("No comment entered.")
    elif args[1] == '-': # read body from stdin
        binary = not (options.content_type == None
                      or options.content_type.startswith("text/"))
        if not binary:
            body = sys.stdin.read()
            if not body.endswith('\n'):
                body+='\n'
        else: # read-in without decoding
            body = sys.__stdin__.read()
    else: # body = arg[1]
        body = args[1]
        if not body.endswith('\n'):
            body+='\n'

    new = parent.new_reply(body=body, content_type=options.content_type)
    if options.author != None:
        new.author = options.author
    if options.alt_id != None:
        new.alt_id = options.alt_id

def get_parser():
    parser = cmdutil.CmdOptionParser("be comment ID [COMMENT]")
    parser.add_option("-a", "--author", metavar="AUTHOR", dest="author",
                      help="Set the comment author", default=None)
    parser.add_option("--alt-id", metavar="ID", dest="alt_id",
                      help="Set an alternate comment ID", default=None)
    parser.add_option("-c", "--content-type", metavar="MIME", dest="content_type",
                      help="Set comment content-type (e.g. text/plain)", default=None)
    return parser

longhelp="""
To add a comment to a bug, use the bug ID as the argument.  To reply
to another comment, specify the comment name (as shown in "be show"
output).  COMMENT, if specified, should be either the text of your
comment or "-", in which case the text will be read from stdin.  If
you do not specify a COMMENT, $EDITOR is used to launch an editor.  If
COMMENT is unspecified and EDITOR is not set, no comment will be
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
                        bug.load_comments(load_full=False)
                        for id,comment in bug.comment_shortnames(shortname):
                            ids.append(id)
                except bugdir.NoBugDir:
                    pass
                raise cmdutil.GetCompletions(ids)
            raise cmdutil.GetCompletions()
