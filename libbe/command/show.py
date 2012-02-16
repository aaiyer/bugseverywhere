# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Thomas Gerigk <tgerigk@gmx.de>
#                         Thomas Habets <thomas@habets.pp.se>
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

import sys

import libbe
import libbe.command
import libbe.command.util
import libbe.util.id
import libbe.version


class Show (libbe.command.Command):
    """Show a particular bug, comment, or combination of both.

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> io.stdout.encoding = 'ascii'
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_bugdir(bd)
    >>> cmd = Show(ui=ui)

    >>> ret = ui.run(cmd, args=['/a',])  # doctest: +ELLIPSIS
              ID : a
      Short name : abc/a
        Severity : minor
          Status : open
        Assigned : 
        Reporter : 
         Creator : John Doe <jdoe@example.com>
         Created : ...
    Bug A
    <BLANKLINE>

    >>> ret = ui.run(cmd, {'xml':True}, ['/a'])  # doctest: +ELLIPSIS
    <?xml version="1.0" encoding="..." ?>
    <be-xml>
      <version>
        <tag>...</tag>
        <committer>...</committer>
        <date>...</date>
        <revision>...</revision>
      </version>
      <bug>
        <uuid>a</uuid>
        <short-name>abc/a</short-name>
        <severity>minor</severity>
        <status>open</status>
        <creator>John Doe &lt;jdoe@example.com&gt;</creator>
        <created>Thu, 01 Jan 1970 00:00:00 +0000</created>
        <summary>Bug A</summary>
      </bug>
    </be-xml>
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'show'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='xml', short_name='x',
                                     help='Dump as XML'),
                libbe.command.Option(name='only-raw-body',
                    help="When printing only a single comment, just print it's"
                  " body.  This allows extraction of non-text content types."),
                libbe.command.Option(name='no-comments', short_name='c',
                    help="Disable comment output.  This is useful if you just "
                         "want more details on a bug's current status."),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='id', metavar='ID', default=None,
                    optional=True, repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_comment_id),
                ])

    def _run(self, **params):
        bugdir = self._get_bugdir()
        if params['only-raw-body'] == True:
            if len(params['id']) != 1:
                raise libbe.command.UserError(
                    'only one ID accepted with --only-raw-body')
            bug,comment = libbe.command.util.bug_comment_from_user_id(
                bugdir, params['id'][0])
            if comment == bug.comment_root:
                raise libbe.command.UserError(
                    "--only-raw-body requires a comment ID, not '%s'"
                    % params['id'][0])
            sys.__stdout__.write(comment.body)
            return 0
        print >> self.stdout, \
            output(bugdir, params['id'], encoding=self.stdout.encoding,
                   as_xml=params['xml'],
                   with_comments=not params['no-comments'])
        return 0

    def _long_help(self):
        return """
Show all information about the bugs or comments whose IDs are given.
If no IDs are given, show the entire repository.

Without the --xml flag set, it's probably not a good idea to mix bug
and comment IDs in a single call, but you're free to do so if you
like.  With the --xml flag set, there will never be any root comments,
so mix and match away (the bug listings for directly requested
comments will be restricted to the bug uuid and the requested
comment(s)).

Directly requested comments will be grouped by their parent bug and
placed at the end of the output, so the ordering may not match the
order of the listed IDs.
"""

def _sort_ids(bugdir, ids, with_comments=True):
    bugs = []
    root_comments = {}
    for id in ids:
        p = libbe.util.id.parse_user(bugdir, id)
        if p['type'] == 'bug':
            bugs.append(p['bug'])
        elif with_comments == True:
            if p['bug'] not in root_comments:
                root_comments[p['bug']] = [p['comment']]
            else:
                root_comments[p['bug']].append(p['comment'])
    for bugname in root_comments.keys():
        assert bugname not in bugs, \
            'specifically requested both #/%s/%s# and #/%s#' \
            % (bugname, root_comments[bugname][0], bugname)
    return (bugs, root_comments)

def _xml_header(encoding):
    lines = ['<?xml version="1.0" encoding="%s" ?>' % encoding,
             '<be-xml>',
             '  <version>',
             '    <tag>%s</tag>' % libbe.version.version()]
    for tag,value in sorted(libbe.version.version_info.items()):
        lines.append('    <%s>%s</%s>' % (tag, value, tag))
    lines.append('  </version>')
    return lines

def _xml_footer():
    return ['</be-xml>']

def output(bd, ids, encoding, as_xml=True, with_comments=True):
    if ids == None or len(ids) == 0:
        bd.load_all_bugs()
        ids = [bug.id.user() for bug in bd]
    bugs,root_comments = _sort_ids(bd, ids, with_comments)
    lines = []
    if as_xml:
        lines.extend(_xml_header(encoding))
    else:
        spaces_left = len(ids) - 1
    for bugname in bugs:
        bug = bd.bug_from_uuid(bugname)
        if as_xml:
            lines.append(bug.xml(indent=2, show_comments=with_comments))
        else:
            lines.append(bug.string(show_comments=with_comments))
            if spaces_left > 0:
                spaces_left -= 1
                lines.append('') # add a blank line between bugs/comments
    for bugname,comments in root_comments.items():
        bug = bd.bug_from_uuid(bugname)
        if as_xml:
            lines.extend(['  <bug>', '    <uuid>%s</uuid>' % bug.uuid])
        for commname in comments:
            try:
                comment = bug.comment_root.comment_from_uuid(commname)
            except KeyError, e:
                raise libbe.command.UserError(e.message)
            if as_xml:
                lines.append(comment.xml(indent=4))
            else:
                lines.append(comment.string())
                if spaces_left > 0:
                    spaces_left -= 1
                    lines.append('') # add a blank line between bugs/comments
        if as_xml:
            lines.append('</bug>')
    if as_xml:
        lines.extend(_xml_footer())
    return '\n'.join(lines)
