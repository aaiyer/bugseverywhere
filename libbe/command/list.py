# Copyright (C) 2005-2012 Aaron Bentley <abentley@panoramicfeedback.com>
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Oleg Romanyshyn <oromanyshyn@panoramicfeedback.com>
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
import re

import libbe
import libbe.bug
import libbe.command
import libbe.command.depend
from libbe.command.depend import Filter, parse_status, parse_severity
import libbe.command.tag
import libbe.command.target
import libbe.command.util

# get a list of * for cmp_*() comparing two bugs.
AVAILABLE_CMPS = [fn[4:] for fn in dir(libbe.bug) if fn[:4] == 'cmp_']
AVAILABLE_CMPS.remove('attr') # a cmp_* template.

class List (libbe.command.Command):
    """List bugs

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_storage(bd.storage)
    >>> cmd = List(ui=ui)

    >>> ret = ui.run(cmd)
    abc/a:om: Bug A
    >>> ret = ui.run(cmd, {'status':'closed'})
    abc/b:cm: Bug B
    >>> ret = ui.run(cmd, {'status':'all', 'sort':'time'})
    abc/a:om: Bug A
    abc/b:cm: Bug B
    >>> bd.storage.writeable
    True
    >>> ui.cleanup()
    >>> bd.cleanup()
    """

    name = 'list'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='status',
                    help='Only show bugs matching the STATUS specifier',
                    arg=libbe.command.Argument(
                        name='status', metavar='STATUS', default='active',
                        completion_callback=libbe.command.util.complete_status)),
                libbe.command.Option(name='severity',
                    help='Only show bugs matching the SEVERITY specifier',
                    arg=libbe.command.Argument(
                        name='severity', metavar='SEVERITY', default='all',
                        completion_callback=libbe.command.util.complete_severity)),
                libbe.command.Option(name='important',
                    help='List bugs with >= "serious" severity'),
                libbe.command.Option(name='assigned', short_name='a',
                    help='Only show bugs matching ASSIGNED',
                    arg=libbe.command.Argument(
                        name='assigned', metavar='ASSIGNED', default=None,
                        completion_callback=libbe.command.util.complete_assigned)),
                libbe.command.Option(name='mine', short_name='m',
                    help='List bugs assigned to you'),
                libbe.command.Option(name='extra-strings', short_name='e',
                    help='Only show bugs matching STRINGS, e.g. --extra-strings'
                         ' TAG:working,TAG:xml',
                    arg=libbe.command.Argument(
                        name='extra-strings', metavar='STRINGS', default=None,
                        completion_callback=libbe.command.util.complete_extra_strings)),
                libbe.command.Option(name='sort', short_name='S',
                    help='Adjust bug-sort criteria with comma-separated list '
                         'SORT.  e.g. "--sort creator,time".  '
                         'Available criteria: %s' % ','.join(AVAILABLE_CMPS),
                    arg=libbe.command.Argument(
                        name='sort', metavar='SORT', default=None,
                        completion_callback=libbe.command.util.Completer(AVAILABLE_CMPS))),
                libbe.command.Option(name='tags', short_name='t',
                    help='Add TAGS: field to standard listing format.'),
                libbe.command.Option(name='ids', short_name='i',
                    help='Only print the bug IDS'),
                libbe.command.Option(name='xml', short_name='x',
                    help='Dump output in XML format'),
                ])
#    parser.add_option("-S", "--sort", metavar="SORT-BY", dest="sort_by",
#                      help="Adjust bug-sort criteria with comma-separated list SORT-BY.  e.g. \"--sort creator,time\".  Available criteria: %s" % ','.join(AVAILABLE_CMPS), default=None)
#    # boolean options.  All but ids and xml are special cases of long forms
#             ("w", "wishlist", "List bugs with 'wishlist' severity"),
#             ("A", "active", "List all active bugs"),
#             ("U", "unconfirmed", "List unconfirmed bugs"),
#             ("o", "open", "List open bugs"),
#             ("T", "test", "List bugs in testing"),
#    for s in bools:
#        attr = s[1].replace('-','_')
#        short = "-%c" % s[0]
#        long = "--%s" % s[1]
#        help = s[2]
#        parser.add_option(short, long, action="store_true",
#                          dest=attr, help=help, default=False)
#    return parser
#
#                ])

    def _run(self, **params):
        bugdir = self._get_bugdir()
        writeable = bugdir.storage.writeable
        bugdir.storage.writeable = False
        cmp_list, status, severity, assigned, extra_strings_regexps = \
            self._parse_params(bugdir, params)
        filter = Filter(status, severity, assigned,
                        extra_strings_regexps=extra_strings_regexps)
        bugs = [bugdir.bug_from_uuid(uuid) for uuid in bugdir.uuids()]
        bugs = [b for b in bugs if filter(bugdir, b) == True]
        self.result = bugs
        if len(bugs) == 0 and params['xml'] == False:
            print >> self.stdout, 'No matching bugs found'

        # sort bugs
        bugs = self._sort_bugs(bugs, cmp_list)

        # print list of bugs
        if params['ids'] == True:
            for bug in bugs:
                print >> self.stdout, bug.id.user()
        else:
            self._list_bugs(bugs, show_tags=params['tags'], xml=params['xml'])
        bugdir.storage.writeable = writeable
        return 0

    def _parse_params(self, bugdir, params):
        cmp_list = []
        if params['sort'] != None:
            for cmp in params['sort'].split(','):
                if cmp not in AVAILABLE_CMPS:
                    raise libbe.command.UserError(
                        'Invalid sort on "%s".\nValid sorts:\n  %s'
                    % (cmp, '\n  '.join(AVAILABLE_CMPS)))
                cmp_list.append(getattr(libbe.bug, 'cmp_%s' % cmp))
        status = parse_status(params['status'])
        severity = parse_severity(params['severity'],
                                  important=params['important'])
        # select assigned
        if params['assigned'] == None:
            if params['mine'] == True:
                assigned = [self._get_user_id()]
            else:
                assigned = 'all'
        else:
            assigned = libbe.command.util.select_values(
                params['assigned'], libbe.command.util.assignees(bugdir))
        for i in range(len(assigned)):
            if assigned[i] == '-':
                assigned[i] = params['user-id']
        if params['extra-strings'] == None:
            extra_strings_regexps = []
        else:
            extra_strings_regexps = [re.compile(x)
                                     for x in params['extra-strings'].split(',')]
        return (cmp_list, status, severity, assigned, extra_strings_regexps)

    def _sort_bugs(self, bugs, cmp_list=None):
        if cmp_list is None:
            cmp_list = []
        cmp_list.extend(libbe.bug.DEFAULT_CMP_FULL_CMP_LIST)
        cmp_fn = libbe.bug.BugCompoundComparator(cmp_list=cmp_list)
        bugs.sort(cmp_fn)
        return bugs

    def _list_bugs(self, bugs, show_tags=False, xml=False):
        if xml == True:
            print >> self.stdout, \
                '<?xml version="1.0" encoding="%s" ?>' % self.stdout.encoding
            print >> self.stdout, '<be-xml>'
        if len(bugs) > 0:
            for bug in bugs:
                if xml == True:
                    print >> self.stdout, bug.xml(show_comments=True)
                else:
                    bug_string = bug.string(shortlist=True)
                    if show_tags == True:
                        attrs,summary = bug_string.split(' ', 1)
                        bug_string = (
                            '%s%s: %s'
                            % (attrs,
                               ','.join(libbe.command.tag.get_tags(bug)),
                               summary))
                    print >> self.stdout, bug_string
        if xml == True:
            print >> self.stdout, '</be-xml>'

    def _long_help(self):
        return """
This command lists bugs.  Normally it prints a short string like
  bea/576:om:[TAGS:] Allow attachments
Where
  bea/576   the bug id
  o         the bug status is 'open' (first letter)
  m         the bug severity is 'minor' (first letter)
  TAGS      comma-separated list of bug tags (if --tags is set)
  Allo...   the bug summary string

You can optionally (-u) print only the bug ids.

There are several criteria that you can filter by:
  * status
  * severity
  * assigned (who the bug is assigned to)
Allowed values for each criterion may be given in a comma seperated
list.  The special string "all" may be used with any of these options
to match all values of the criterion.  As with the --status and
--severity options for `be depend`, starting the list with a minus
sign makes your selections a blacklist instead of the default
whitelist.

status
  %s
severity
  %s
assigned
  free form, with the string '-' being a shortcut for yourself.

In addition, there are some shortcut options that set boolean flags.
The boolean options are ignored if the matching string option is used.
""" % (','.join(libbe.bug.status_values),
       ','.join(libbe.bug.severity_values))
