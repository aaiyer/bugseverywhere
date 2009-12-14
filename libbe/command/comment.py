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

import os
import sys

import libbe
import libbe.command
import libbe.command.util
import libbe.comment
import libbe.ui.util.editor
import libbe.util.id


class Comment (libbe.command.Command):
    """Add a comment to a bug

    >>> import time
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Comment()
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> cmd.run(bd.storage, bd, {'user-id':u'Fran\\xe7ois'},
    ...         ['/a', 'This is a comment about a'])
    >>> bd.flush_reload()
    >>> bug = bd.bug_from_uuid('a')
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> comment.id.storage() == comment.uuid
    True
    >>> print comment.body
    This is a comment about a
    <BLANKLINE>
    >>> comment.author
    u'Fran\\xe7ois'
    >>> comment.time <= int(time.time())
    True
    >>> comment.in_reply_to is None
    True

    >>> if 'EDITOR' in os.environ:
    ...     del os.environ['EDITOR']
    >>> cmd.run(bd.storage, bd, {'user-id':u'Frank'}, ['/b'])
    Traceback (most recent call last):
    UserError: No comment supplied, and EDITOR not specified.

    >>> os.environ['EDITOR'] = "echo 'I like cheese' > "
    >>> cmd.run(bd.storage, bd, {'user-id':u'Frank'}, ['/b'])
    >>> bd.flush_reload()
    >>> bug = bd.bug_from_uuid('b')
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    I like cheese
    <BLANKLINE>
    >>> bd.cleanup()
    """
    name = 'comment'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.requires_bugdir = True
        self.options.extend([
                libbe.command.Option(name='author', short_name='a',
                    help='Set the comment author',
                    arg=libbe.command.Argument(
                        name='author', metavar='AUTHOR')),
                libbe.command.Option(name='alt-id',
                    help='Set an alternate comment ID',
                    arg=libbe.command.Argument(
                        name='alt-id', metavar='ID')),
                libbe.command.Option(name='content-type', short_name='c',
                    help='Set comment content-type (e.g. text/plain)',
                    arg=libbe.command.Argument(name='content-type',
                        metavar='MIME')),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='id', metavar='ID', default=None,
                    completion_callback=libbe.command.util.complete_bug_comment_id),
                libbe.command.Argument(
                    name='comment', metavar='COMMENT', default=None,
                    optional=True,
                    completion_callback=libbe.command.util.complete_assigned),
                ])
    def _run(self, storage, bugdir, **params):
        bug,parent = \
            libbe.command.util.bug_comment_from_user_id(bugdir, params['id'])
        if params['comment'] == None:
            # try to launch an editor for comment-body entry
            try:
                if parent == bug.comment_root:
                    parent_body = bug.summary+'\n'
                else:
                    parent_body = parent.body
                estr = 'Please enter your comment above\n\n> %s\n' \
                    % ('\n> '.join(parent_body.splitlines()))
                body = libbe.ui.util.editor.editor_string(estr)
            except libbe.ui.util.editor.CantFindEditor, e:
                raise libbe.command.UserError(
                    'No comment supplied, and EDITOR not specified.')
            if body is None:
                raise libbe.command.UserError('No comment entered.')
        elif params['comment'] == '-': # read body from stdin
            binary = not (params['content-type'] == None
                          or params['content-type'].startswith("text/"))
            if not binary:
                body = self.stdin.read()
                if not body.endswith('\n'):
                    body += '\n'
            else: # read-in without decoding
                body = sys.stdin.read()
        else: # body given on command line
            body = params['comment']
            if not body.endswith('\n'):
                body+='\n'
        if params['author'] == None:
            params['author'] = params['user-id']

        new = parent.new_reply(body=body)
        for key in ['alt-id', 'author', 'content-type']:
            if params[key] != None:
                setattr(new, key, params[key])

    def _long_help(self):
        return """
To add a comment to a bug, use the bug ID as the argument.  To reply
to another comment, specify the comment name (as shown in "be show"
output).  COMMENT, if specified, should be either the text of your
comment or "-", in which case the text will be read from stdin.  If
you do not specify a COMMENT, $EDITOR is used to launch an editor.  If
COMMENT is unspecified and EDITOR is not set, no comment will be
created.
"""
