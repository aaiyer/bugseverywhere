# Copyright (C) 2009 Gianluca Montecchi <gian@grys.it>
#                    W. Trevor King <wking@drexel.edu>
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

import libbe
import libbe.command
import libbe.command.util
import libbe.util.utility


TAG_TAG = 'TAG:'


import os, copy

class Tag (libbe.command.Command):
    __doc__ = """Tag a bug, or search bugs for tags

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Tag()
    >>> cmd._bugdir = bd
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    []
    >>> ret = cmd.run(args=['/a', 'GUI'])
    Tags for abc/a:
    GUI
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    ['%(tag_tag)sGUI']
    >>> ret = cmd.run(args=['/a', 'later'])
    Tags for abc/a:
    GUI
    later
    >>> ret = cmd.run(args=['/a'])
    Tags for abc/a:
    GUI
    later
    >>> ret = cmd.run({'list':True})
    GUI
    later
    >>> ret = cmd.run(args=['/a', 'Alphabetically first'])
    Tags for abc/a:
    Alphabetically first
    GUI
    later
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    ['%(tag_tag)sAlphabetically first', '%(tag_tag)sGUI', '%(tag_tag)slater']
    >>> a.extra_strings = []
    >>> print a.extra_strings
    []
    >>> ret = cmd.run(args=['/a'])
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    []
    >>> ret = cmd.run(args=['/a', 'Alphabetically first'])
    Tags for abc/a:
    Alphabetically first
    >>> ret = cmd.run({'remove':True}, ['/a', 'Alphabetically first'])
    >>> bd.cleanup()
    """ % {'tag_tag':TAG_TAG}
    name = 'tag'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='remove', short_name='r',
                    help='Remove TAG (instead of adding it)'),
                libbe.command.Option(name='list', short_name='l',
                    help='List all available tags and exit'),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='id', metavar='BUG-ID', optional=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                libbe.command.Argument(
                    name='tag', metavar='TAG', default=tuple(),
                    optional=True, repeatable=True),
                ])

    def _run(self, **params):
        if params['id'] == None and params['list'] == False:
            raise libbe.command.UserError('Please specify a bug id.')
        if params['id'] != None and params['list'] == True:
            raise libbe.command.UserError(
                'Do not specify a bug id with the --list option.')
        bugdir = self._get_bugdir()
        if params['list'] == True:
            bugdir.load_all_bugs()
            tags = []
            for bug in bugdir:
                for estr in bug.extra_strings:
                    if estr.startswith(TAG_TAG):
                        tag = estr[len(TAG_TAG):]
                        if tag not in tags:
                            tags.append(tag)
            tags.sort()
            if len(tags) > 0:
                print >> self.stdout, '\n'.join(tags)
            return 0

        bug,dummy_comment = libbe.command.util.bug_comment_from_user_id(
            bugdir, params['id'])
        if len(params['tag']) > 0:
            estrs = bug.extra_strings
            for tag in params['tag']:
                tag_string = '%s%s' % (TAG_TAG, tag)
                if params['remove'] == True:
                    estrs.remove(tag_string)
                else: # add the tag
                    estrs.append(tag_string)
            bug.extra_strings = estrs # reassign to notice change

        tags = []
        for estr in bug.extra_strings:
            if estr.startswith(TAG_TAG):
                tags.append(estr[len(TAG_TAG):])
    
        if len(tags) > 0:
            print "Tags for %s:" % bug.id.user()
            print '\n'.join(tags)
        return 0

    def _long_help(self):
        return """
If TAG is given, add TAG to BUG-ID.  If it is not specified, just
print the tags for BUG-ID.

To search for bugs with a particular tag, try
  $ be list --extra-strings %s<your-tag>
""" % TAG_TAG
