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

import libbe
import libbe.bug
import libbe.command
import libbe.command.util
import libbe.storage

import libbe.diff

class Diff (libbe.command.Command):
    __doc__ = """Compare bug reports with older tree

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> cmd = Subscribe()
    >>> cmd._storage = bd.storage
    >>> cmd._setup_io = lambda i_enc,o_enc : None
    >>> cmd.stdout = sys.stdout

    >>> original = bd.storage.commit('Original status')
    >>> bug = bd.bug_from_uuid('a')
    >>> bug.status = 'closed'
    >>> changed = bd.vcs.commit('Closed bug a')
    >>> if bd.vcs.versioned == True:
    ...     ret = cmd.run(args=[original])
    ... else:
    ...     print 'Modified bugs:\\n  a:cm: Bug A\\n    Changed bug settings:\\n      status: open -> closed'
    Modified bugs:
      a:cm: Bug A
        Changed bug settings:
          status: open -> closed
    >>> if bd.vcs.versioned == True:
    ...     ret = cmd.run({'subscribe':'%(bugdir_id)s:mod', 'uuids':True}, [original])
    ... else:
    ...     print 'a'
    a
    >>> if bd.vcs.versioned == False:
    ...     ret = cmd.run(args=[original])
    ... else:
    ...     raise libbe.command.UserError('This repository not revision-controlled.')
    Traceback (most recent call last):
      ...
    UserError: This repository is not revision-controlled.
    >>> bd.cleanup()
    """ % {'bugdir_id':libbe.diff.BUGDIR_ID}
    name = 'diff'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='repo', short_name='r',
                    help='Compare with repository in REPO instead'
                         ' of the current repository.',
                    arg=libbe.command.Argument(
                        name='repo', metavar='REPO',
                        completion_callback=libbe.command.util.complete_path)),
                libbe.command.Option(name='subscribe', short_name='s',
                    help='Only print changes matching SUBSCRIPTION, '
                    'subscription is a comma-separ\ated list of ID:TYPE '
                    'tuples.  See `be subscribe --help` for descriptions '
                    'of ID and TYPE.',
                    arg=libbe.command.Argument(
                        name='subscribe', metavar='SUBSCRIPTION')),
                libbe.command.Option(name='uuids', short_name='u',
                    help='Only print the changed bug UUIDS.'),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='revision', metavar='REVISION', default=None,
                    optional=True)
                ])

    def _run(self, **params):
        try:
            subscriptions = libbe.diff.subscriptions_from_string(
                params['subscribe'])
        except ValueError, e:
            raise libbe.command.UserError(e.msg)
        bugdir = self._get_bugdir()
        if bugdir.storage.versioned == False:
            raise libbe.command.UserError(
                'This repository is not revision-controlled.')
        if params['repo'] == None:
            if params['revision'] == None: # get the most recent revision
                params['revision'] = bugdir.storage.revision_id(-1)
            old_bd = bugdir.duplicate_bugdir(params['revision']) # TODO
        else:
            old_storage = libbe.storage.get_storage(params['repo'])
            old_storage.connect()
            old_bd_current = bugdir.BugDir(old_storage, from_disk=True)
            if params['revision'] == None: # use the current working state
                old_bd = old_bd_current
            else:
                if old_bd_current.storage.versioned == False:
                    raise libbe.command.UserError(
                        '%s is not revision-controlled.'
                        % storage.repo)
                old_bd = old_bd_current.duplicate_bugdir(revision) # TODO
        d = libbe.diff.Diff(old_bd, bugir)
        tree = d.report_tree(subscriptions)

        if params['uuids'] == True:
            uuids = []
            bugs = tree.child_by_path('/bugs')
            for bug_type in bugs:
                uuids.extend([bug.name for bug in bug_type])
            print >> self.stdout, '\n'.join(uuids)
        else :
            rep = tree.report_string()
            if rep != None:
                print >> self.stdout, rep
        return 0

    def _long_help(self):
        return """
Uses the VCS to compare the current tree with a previous tree, and
prints a pretty report.  If REVISION is given, it is a specifier for
the particular previous tree to use.  Specifiers are specific to their
VCS.

For Arch your specifier must be a fully-qualified revision name.

Besides the standard summary output, you can use the options to output
UUIDS for the different categories.  This output can be used as the
input to 'be show' to get an understanding of the current status.
"""
