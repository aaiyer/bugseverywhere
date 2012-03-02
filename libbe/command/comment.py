# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Robert Lehmann <mail@robertlehmann.de>
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
    >>> import libbe.util.id
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = Comment(ui=ui)

    >>> uuid_gen = libbe.util.id.uuid_gen
    >>> libbe.util.id.uuid_gen = lambda: 'X'
    >>> ui._user_id = u'Fran\\xe7ois'
    >>> ret = ui.run(cmd, args=['/a', 'This is a comment about a'])
    Created comment with ID abc/a/X
    >>> libbe.util.id.uuid_gen = uuid_gen
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
    >>> if 'VISUAL' in os.environ:
    ...     del os.environ['VISUAL']
    >>> ui._user_id = u'Frank'
    >>> ret = ui.run(cmd, args=['/b'])
    Traceback (most recent call last):
    UserError: No comment supplied, and EDITOR not specified.

    >>> os.environ['EDITOR'] = "echo 'I like cheese' > "
    >>> libbe.util.id.uuid_gen = lambda: 'Y'
    >>> ret = ui.run(cmd, args=['/b'])
    Created comment with ID abc/b/Y
    >>> libbe.util.id.uuid_gen = uuid_gen
    >>> bd.flush_reload()
    >>> bug = bd.bug_from_uuid('b')
    >>> bug.load_comments(load_full=False)
    >>> comment = bug.comment_root[0]
    >>> print comment.body
    I like cheese
    <BLANKLINE>
    >>> ui.cleanup()
    >>> bd.cleanup()
    >>> del os.environ["EDITOR"]
    """
    name = 'comment'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
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

    def _run(self, **params):
        bugdir = self._get_bugdir()
        bug,parent = \
            libbe.command.util.bug_comment_from_user_id(bugdir, params['id'])
        if params['comment'] == None:
            # try to launch an editor for comment-body entry
            try:
                if parent == bug.comment_root:
                    header = "Subject: %s" % bug.summary
                    parent_body = parent.string_thread() or "No comments"
                else:
                    header = "From: %s\nTo: %s" % (parent.author, bug)
                    parent_body = parent.body
                estr = 'Please enter your comment above\n\n%s\n\n> %s\n' \
                    % (header, '\n> '.join(parent_body.splitlines()))
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
            params['author'] = self._get_user_id()

        new = parent.new_reply(body=body, content_type=params['content-type'])
        for key in ['alt-id', 'author']:
            if params[key] != None:
                setattr(new, new._setting_name_to_attr_name(key), params[key])
        print >> self.stdout, 'Created comment with ID %s (%s)' % (new.id.user(), new.id.long_user())
        return 0

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
