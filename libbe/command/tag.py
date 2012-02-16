# Copyright (C) 2009-2012 Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
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

import libbe
import libbe.command
import libbe.command.util


TAG_TAG = 'TAG:'


class Tag (libbe.command.Command):
    __doc__ = """Tag a bug, or search bugs for tags

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_bugdir(bd)
    >>> cmd = Tag(ui=ui)

    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    []
    >>> ret = ui.run(cmd, args=['/a', 'GUI'])
    Tags for abc/a:
    GUI
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    ['%(tag_tag)sGUI']
    >>> ret = ui.run(cmd, args=['/a', 'later'])
    Tags for abc/a:
    GUI
    later
    >>> ret = ui.run(cmd, args=['/a'])
    Tags for abc/a:
    GUI
    later
    >>> ret = ui.run(cmd, {'list':True})
    GUI
    later
    >>> ret = ui.run(cmd, args=['/a', 'Alphabetically first'])
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
    >>> ret = ui.run(cmd, args=['/a'])
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    []
    >>> ret = ui.run(cmd, args=['/a', 'Alphabetically first'])
    Tags for abc/a:
    Alphabetically first
    >>> ret = ui.run(cmd, {'remove':True}, ['/a', 'Alphabetically first'])
    >>> ui.cleanup()
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
            tags = get_all_tags(bugdir)
            tags.sort()
            if len(tags) > 0:
                print >> self.stdout, '\n'.join(tags)
            return 0

        bug,dummy_comment = libbe.command.util.bug_comment_from_user_id(
            bugdir, params['id'])
        if len(params['tag']) > 0:
            tags = get_tags(bug)
            for tag in params['tag']:
                if params['remove'] == True:
                    tags.remove(tag)
                else: # add the tag
                    tags.append(tag)
            set_tags(bug, tags)

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

# functions exposed to other modules

def get_all_tags(bugdir):
    bugdir.load_all_bugs()
    tags = []
    for bug in bugdir:
        for tag in get_tags(bug):
            if tag not in tags:
                tags.append(tag)
    return tags

def get_tags(bug):
    tags = []
    for estr in bug.extra_strings:
        if estr.startswith(TAG_TAG):
            tag = estr[len(TAG_TAG):]
            if tag not in tags:
                tags.append(tag)
    return tags

def set_tags(bug, tags):
    estrs = bug.extra_strings
    new_estrs = []
    for estr in estrs:
        if not estr.startswith(TAG_TAG):
            new_estrs.append(estr)
    for tag in tags:
        new_estrs.append('%s%s' % (TAG_TAG, tag))
    bug.extra_strings = new_estrs # reassign to notice change

def append_tag(bug, tag):
    estrs = bug.extra_strings
    estrs.append('%s%s' % (TAG_TAG, tag))
    bug.extra_strings = estrs # reassign to notice change

def remove_tag(bug, tag):
    estrs = bug.extra_strings
    estrs.remove('%s%s' % (TAG_TAG, tag))
    bug.extra_strings = estrs # reassign to notice change
