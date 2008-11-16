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
from libbe import cmdutil, names, utility
from libbe.bug import new_comment
import os
__desc__ = __doc__

def execute(args):
    """
    >>> from libbe import tests, names
    >>> import os, time
    >>> dir = tests.simple_bug_dir()
    >>> os.chdir(dir.dir)
    >>> execute(["a", "This is a comment about a"])
    >>> comment = dir.get_bug("a").list_comments()[0]
    >>> comment.body
    u'This is a comment about a\\n'
    >>> comment.From == names.creator()
    True
    >>> comment.time <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True
    >>> if 'EDITOR' in os.environ:
    ...     del os.environ["EDITOR"]
    >>> execute(["b"])
    Traceback (most recent call last):
    UserError: No comment supplied, and EDITOR not specified.
    >>> os.environ["EDITOR"] = "echo 'I like cheese' > "
    >>> execute(["b"])
    >>> dir.get_bug("b").list_comments()[0].body
    u'I like cheese\\n'
    >>> tests.clean_up()
    """
    options, args = get_parser().parse_args(args)
    if len(args) < 1:
        raise cmdutil.UsageError()
    bug, parent_comment = cmdutil.get_bug_and_comment(args[0])
    if len(args) == 1:
        try:
            body = utility.editor_string("Please enter your comment above")
        except utility.CantFindEditor:
            raise cmdutil.UserError(
                "No comment supplied, and EDITOR not specified.")
        if body is None:
            raise cmdutil.UserError("No comment entered.")
        body = body.decode('utf-8')
    else:
        body = args[1]
        if not body.endswith('\n'):
            body+='\n'

    comment = new_comment(bug, body)
    if parent_comment is not None:
        comment.in_reply_to = parent_comment.uuid
    comment.save()


def get_parser():
    parser = cmdutil.CmdOptionParser("be comment ID COMMENT")
    return parser

longhelp="""
To add a comment to a bug, use the bug ID as the argument.  To reply to another
comment, specify the comment name (as shown in "be show" output).

$EDITOR is used to launch an editor.  If unspecified, no comment will be
created.)
"""

def help():
    return get_parser().help_str() + longhelp
