# Copyright (C) 2005-2009 Aaron Bentley and Panometrics, Inc.
#                         Chris Ball <cjb@laptop.org>
#                         Gianluca Montecchi <gian@grys.it>
#                         Marien Zwart <marienz@gentoo.org>
#                         Thomas Gerigk <tgerigk@gmx.de>
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

import libbe
import libbe.command
import libbe.command.util
import libbe.command.depend



class Target (libbe.command.Command):
    """Assorted bug target manipulations and queries

    >>> import os, StringIO, sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Target()
    >>> cmd._storage = bd.storage
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> ret = cmd.run(args=['/a'])
    No target assigned.
    >>> ret = cmd.run(args=['/a', 'tomorrow'])
    >>> ret = cmd.run(args=['/a'])
    tomorrow

    >>> cmd.stdout = StringIO.StringIO()
    >>> ret = cmd.run({'resolve':True}, ['tomorrow'])
    >>> output = cmd.stdout.getvalue().strip()
    >>> target = bd.bug_from_uuid(output)
    >>> print target.summary
    tomorrow
    >>> print target.severity
    target

    >>> cmd.stdout = sys.stdout
    >>> ret = cmd.run(args=['/a', 'none'])
    >>> ret = cmd.run(args=['/a'])
    No target assigned.
    >>> bd.cleanup()
    """
    name = 'target'
    
    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='resolve', short_name='r',
                    help="Print the UUID for the target bug whose summary "
                    "matches TARGET.  If TARGET is not given, print the UUID "
                    "of the current bugdir target."),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='id', metavar='BUG-ID', default=None,
                    optional=True,
                    completion_callback=libbe.command.util.complete_bug_id),
                libbe.command.Argument(
                    name='target', metavar='TARGET', default=None,
                    optional=True,
                    completion_callback=complete_target),
                ])

    def _run(self, **params):
        if params['resolve'] == False:
            if params['id'] == None:
                raise libbe.command.UserError('Please specify a bug id.')
        else:
            if params['target'] != None:
                raise libbe.command.UserError('Too many arguments')
            params['target'] = params.pop('id')
        bugdir = self._get_bugdir()
        if params['resolve'] == True:
            bug = bug_from_target_summary(bugdir, params['target'])
            if bug == None:
                print >> self.stdout, 'No target assigned.'
            else:
                print >> self.stdout, bug.uuid
            return 0
        bug,dummy_comment = libbe.command.util.bug_comment_from_user_id(
            bugdir, params['id'])
        if params['target'] == None:
            target = bug_target(bugdir, bug)
            if target == None:
                print >> self.stdout, 'No target assigned.'
            else:
                print >> self.stdout, target.summary
        else:
            if params['target'] == 'none':
                target = remove_target(bugdir, bug)
            else:
                target = add_target(bugdir, bug, params['target'])
        return 0

    def _usage(self):
        return 'usage: be %(name)s BUG-ID [TARGET]\nor:    be %(name)s --resolve [TARGET]' \
            % vars(self)

    def _long_help(self):
        return """
Assorted bug target manipulations and queries.

If no target is specified, the bug's current target is printed.  If
TARGET is specified, it will be assigned to the bug, creating a new
target bug if necessary.

Targets are free-form; any text may be specified.  They will generally
be milestone names or release numbers.  The value "none" can be used
to unset the target.

In the alternative `be target --resolve TARGET` form, print the UUID
of the target-bug with summary TARGET.  If target is not given, return
use the bugdir's current target (see `be set`).

If you want to list all bugs blocking the current target, try
  $ be depend --status -closed,fixed,wontfix --severity -target \
    $(be target --resolve)

If you want to set the current bugdir target by summary (rather than
by UUID), try
  $ be set target $(be target --resolve SUMMARY)
"""

def bug_from_target_summary(bugdir, summary=None):
    if summary == None:
        if bugdir.target == None:
            return None
        else:
            return bugdir.bug_from_uuid(bugdir.target)
    matched = []
    for uuid in bugdir.uuids():
        bug = bugdir.bug_from_uuid(uuid)
        if bug.severity == 'target' and bug.summary == summary:
            matched.append(bug)
    if len(matched) == 0:
        return None
    if len(matched) > 1:
        raise Exception('Several targets with same summary:  %s'
                        % '\n  '.join([bug.uuid for bug in matched]))
    return matched[0]

def bug_target(bugdir, bug):
    if bug.severity == 'target':
        return bug
    matched = []
    for blocked in libbe.command.depend.get_blocks(bugdir, bug):
        if blocked.severity == 'target':
            matched.append(blocked)
    if len(matched) == 0:
        return None
    if len(matched) > 1:
        raise Exception('This bug (%s) blocks several targets:  %s'
                        % (bug.uuid,
                           '\n  '.join([b.uuid for b in matched])))
    return matched[0]

def remove_target(bugdir, bug):
    target = bug_target(bugdir, bug)
    libbe.command.depend.remove_block(target, bug)
    return target

def add_target(bugdir, bug, summary):
    target = bug_from_target_summary(bugdir, summary)
    if target == None:
        target = bugdir.new_bug(summary=summary)
        target.severity = 'target'
    libbe.command.depend.add_block(target, bug)
    return target

def targets(bugdir):
    bugdir.load_all_bugs()
    for bug in bugdir:
        if bug.severity == 'target':
            yield bug.summary

def complete_target(command, argument, fragment=None):
    """
    List possible command completions for fragment.

    argument argument is not used.
    """
    return targets(command._get_bugdir())
