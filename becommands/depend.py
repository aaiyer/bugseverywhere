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
"""Add/remove bug dependencies"""
from libbe import cmdutil, bugdir, bug, tree
import os, copy
__desc__ = __doc__

BLOCKS_TAG="BLOCKS:"
BLOCKED_BY_TAG="BLOCKED-BY:"

class BrokenLink (Exception):
    def __init__(self, blocked_bug, blocking_bug, blocks=True):
        if blocks == True:
            msg = "Missing link: %s blocks %s" \
                % (blocking_bug.uuid, blocked_bug.uuid)
        else:
            msg = "Missing link: %s blocked by %s" \
                % (blocked_bug.uuid, blocking_bug.uuid)
        Exception.__init__(self, msg)
        self.blocked_bug = blocked_bug
        self.blocking_bug = blocking_bug


def execute(args, manipulate_encodings=True, restrict_file_access=False):
    """
    >>> from libbe import utility
    >>> bd = bugdir.SimpleBugDir()
    >>> bd.save()
    >>> os.chdir(bd.root)
    >>> execute(["a", "b"], manipulate_encodings=False)
    a blocked by:
    b
    >>> execute(["a"], manipulate_encodings=False)
    a blocked by:
    b
    >>> execute(["--show-status", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    a blocked by:
    b closed
    >>> execute(["b", "a"], manipulate_encodings=False)
    b blocked by:
    a
    b blocks:
    a
    >>> execute(["--show-status", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    a blocked by:
    b closed
    a blocks:
    b closed
    >>> execute(["-r", "b", "a"], manipulate_encodings=False)
    b blocks:
    a
    >>> execute(["-r", "a", "b"], manipulate_encodings=False)
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda _bug : _bug.active==True,
                                         1: lambda _bug : _bug.active==True})

    if options.repair == True:
        if len(args) > 0:
            raise cmdutil.UsageError("No arguments with --repair calls.")
    elif len(args) < 1:
        raise cmdutil.UsageError("Please a bug id.")
    elif len(args) > 2:
        help()
        raise cmdutil.UsageError("Too many arguments.")
    elif len(args) == 2 and options.tree_depth != None:
        raise cmdutil.UsageError("Only one bug id used in tree mode.")

    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)
    if options.repair == True:
        good,fixed,broken = check_dependencies(bd, repair_broken_links=True)
        assert len(broken) == 0, broken
        if len(fixed) > 0:
            print "Fixed the following links:"
            print "\n".join(["%s |-- %s" % (blockee.uuid, blocker.uuid)
                             for blockee,blocker in fixed])
        return 0

    allowed_status_values = _allowed_values(options.limit_status,
                                            bug.status_values)
    allowed_severity_values = _allowed_values(options.limit_severity,
                                              bug.severity_values)
    bugA = cmdutil.bug_from_id(bd, args[0])

    if options.tree_depth != None:
        dtree = DependencyTree(bd, bugA, options.tree_depth,
                               allowed_status_values,
                               allowed_severity_values)
        if len(dtree.blocked_by_tree()) > 0:
            print "%s blocked by:" % bugA.uuid
            for depth,node in dtree.blocked_by_tree().thread():
                if depth == 0: continue
                print "%s%s" % (" "*(depth), node.bug.string(shortlist=True))
        if len(dtree.blocks_tree()) > 0:
            print "%s blocks:" % bugA.uuid
            for depth,node in dtree.blocks_tree().thread():
                if depth == 0: continue
                print "%s%s" % (" "*(depth), node.bug.string(shortlist=True))
        return 0

    if len(args) == 2:
        bugB = cmdutil.bug_from_id(bd, args[1])
        if options.remove == True:
            remove_block(bugA, bugB)
        else: # add the dependency
            add_block(bugA, bugB)

    blocked_by = get_blocked_by(bd, bugA)
    if len(blocked_by) > 0:
        print "%s blocked by:" % bugA.uuid
        if options.show_status == True:
            print '\n'.join(["%s\t%s" % (_bug.uuid, _bug.status)
                             for _bug in blocked_by])
        else:
            print '\n'.join([_bug.uuid for _bug in blocked_by])
    blocks = get_blocks(bd, bugA)
    if len(blocks) > 0:
        print "%s blocks:" % bugA.uuid
        if options.show_status == True:
            print '\n'.join(["%s\t%s" % (_bug.uuid, _bug.status)
                             for _bug in blocks])
        else:
            print '\n'.join([_bug.uuid for _bug in blocks])

def get_parser():
    parser = cmdutil.CmdOptionParser("be depend BUG-ID [BUG-ID]\nor:    be depend --repair")
    parser.add_option("-r", "--remove", action="store_true",
                      dest="remove", default=False,
                      help="Remove dependency (instead of adding it)")
    parser.add_option("-s", "--show-status", action="store_true",
                      dest="show_status", default=False,
                      help="Show status of blocking bugs")
    parser.add_option("--limit-status", dest="limit_status", metavar="STATUS",
                      help="Only show bugs matching the STATUS specifier")
    parser.add_option("--limit-severity", dest="limit_severity",
                      metavar="SEVERITY",
                      help="Only show bugs matching the SEVERITY specifier")
    parser.add_option("-t", "--tree-depth", metavar="DEPTH", default=None,
                      type="int", dest="tree_depth",
                      help="Print dependency tree rooted at BUG-ID with DEPTH levels of both blockers and blockees.  Set DEPTH <= 0 to disable the depth limit.")
    parser.add_option("--repair", action="store_true",
                      dest="repair", default=False,
                      help="Check for and repair one-way links")
    return parser

longhelp="""
Set a dependency with the second bug (B) blocking the first bug (A).
If bug B is not specified, just print a list of bugs blocking (A).

To search for bugs blocked by a particular bug, try
  $ be list --extra-strings BLOCKED-BY:<your-bug-uuid>

The --limit-* options allow you to either blacklist or whitelist
values, for example
  $ be list --limit-status open,assigned
will only follow and print dependencies with open or assigned status.
You select blacklist mode by starting the list with a minus sign, for
example
  $ be list --limit-severity -target
which will only follow and print dependencies with non-target severity.

In repair mode, add the missing direction to any one-way links.

The "|--" symbol in the repair-mode output is inspired by the
"negative feedback" arrow common in biochemistry.  See, for example
  http://www.nature.com/nature/journal/v456/n7223/images/nature07513-f5.0.jpg
"""

def help():
    return get_parser().help_str() + longhelp

# internal helper functions

def _allowed_values(limit_string, possible_values, name="unkown"):
    """
    >>> _allowed_values(None, ['abc', 'def', 'hij'])
    ['abc', 'def', 'hij']
    >>> _allowed_values('-abc,hij', ['abc', 'def', 'hij'])
    ['def']
    >>> _allowed_values('abc,hij', ['abc', 'def', 'hij'])
    ['abc', 'hij']
    >>> _allowed_values('-xyz,hij', ['abc', 'def', 'hij'], name="value")
    Traceback (most recent call last):
      ...
    UserError: Invalid value xyz
      ['abc', 'def', 'hij']
    >>> _allowed_values('xyz,hij', ['abc', 'def', 'hij'], name="value")
    Traceback (most recent call last):
      ...
    UserError: Invalid value xyz
      ['abc', 'def', 'hij']
    """
    possible_values = list(possible_values) # don't alter the original
    if limit_string == None:
        pass
    elif limit_string.startswith('-'):
        blacklisted_values = set(limit_string[1:].split(','))
        for value in blacklisted_values:
            if value not in possible_values:
                raise cmdutil.UserError('Invalid %s %s\n  %s'
                                        % (name, value, possible_values))
            possible_values.remove(value)
    else:
        whitelisted_values = limit_string.split(',')
        for value in whitelisted_values:
            if value not in possible_values:
                raise cmdutil.UserError('Invalid %s %s\n  %s'
                                        % (name, value, possible_values))
        possible_values = whitelisted_values
    return possible_values

def _generate_blocks_string(blocked_bug):
    return "%s%s" % (BLOCKS_TAG, blocked_bug.uuid)

def _generate_blocked_by_string(blocking_bug):
    return "%s%s" % (BLOCKED_BY_TAG, blocking_bug.uuid)

def _parse_blocks_string(string):
    assert string.startswith(BLOCKS_TAG)
    return string[len(BLOCKS_TAG):]

def _parse_blocked_by_string(string):
    assert string.startswith(BLOCKED_BY_TAG)
    return string[len(BLOCKED_BY_TAG):]

def _add_remove_extra_string(bug, string, add):
    estrs = bug.extra_strings
    if add == True:
        estrs.append(string)
    else: # remove the string
        estrs.remove(string)
    bug.extra_strings = estrs # reassign to notice change

def _get_blocks(bug):
    uuids = []
    for line in bug.extra_strings:
        if line.startswith(BLOCKS_TAG):
            uuids.append(_parse_blocks_string(line))
    return uuids

def _get_blocked_by(bug):
    uuids = []
    for line in bug.extra_strings:
        if line.startswith(BLOCKED_BY_TAG):
            uuids.append(_parse_blocked_by_string(line))
    return uuids

def _repair_one_way_link(blocked_bug, blocking_bug, blocks=None):
    if blocks == True: # add blocks link
        blocks_string = _generate_blocks_string(blocked_bug)
        _add_remove_extra_string(blocking_bug, blocks_string, add=True)
    else: # add blocked by link
        blocked_by_string = _generate_blocked_by_string(blocking_bug)
        _add_remove_extra_string(blocked_bug, blocked_by_string, add=True)

# functions exposed to other modules

def add_block(blocked_bug, blocking_bug):
    blocked_by_string = _generate_blocked_by_string(blocking_bug)
    _add_remove_extra_string(blocked_bug, blocked_by_string, add=True)
    blocks_string = _generate_blocks_string(blocked_bug)
    _add_remove_extra_string(blocking_bug, blocks_string, add=True)

def remove_block(blocked_bug, blocking_bug):
    blocked_by_string = _generate_blocked_by_string(blocking_bug)
    _add_remove_extra_string(blocked_bug, blocked_by_string, add=False)
    blocks_string = _generate_blocks_string(blocked_bug)
    _add_remove_extra_string(blocking_bug, blocks_string, add=False)

def get_blocks(bugdir, bug):
    """
    Return a list of bugs that the given bug blocks.
    """
    blocks = []
    for uuid in _get_blocks(bug):
        blocks.append(bugdir.bug_from_uuid(uuid))
    return blocks

def get_blocked_by(bugdir, bug):
    """
    Return a list of bugs blocking the given bug blocks.
    """
    blocked_by = []
    for uuid in _get_blocked_by(bug):
        blocked_by.append(bugdir.bug_from_uuid(uuid))
    return blocked_by

def check_dependencies(bugdir, repair_broken_links=False):
    """
    Check that links are bi-directional for all bugs in bugdir.

    >>> bd = bugdir.SimpleBugDir(sync_with_disk=False)
    >>> a = bd.bug_from_uuid("a")
    >>> b = bd.bug_from_uuid("b")
    >>> blocked_by_string = _generate_blocked_by_string(b)
    >>> _add_remove_extra_string(a, blocked_by_string, add=True)
    >>> good,repaired,broken = check_dependencies(bd, repair_broken_links=False)
    >>> good
    []
    >>> repaired
    []
    >>> broken
    [(Bug(uuid='a'), Bug(uuid='b'))]
    >>> _get_blocks(b)
    []
    >>> good,repaired,broken = check_dependencies(bd, repair_broken_links=True)
    >>> _get_blocks(b)
    ['a']
    >>> good
    []
    >>> repaired
    [(Bug(uuid='a'), Bug(uuid='b'))]
    >>> broken
    []
    """
    if bugdir.sync_with_disk == True:
        bugdir.load_all_bugs()
    good_links = []
    fixed_links = []
    broken_links = []
    for bug in bugdir:
        for blocker in get_blocked_by(bugdir, bug):
            blocks = get_blocks(bugdir, blocker)
            if (bug, blocks) in good_links+fixed_links+broken_links:
                continue # already checked that link
            if bug not in blocks:
                if repair_broken_links == True:
                    _repair_one_way_link(bug, blocker, blocks=True)
                    fixed_links.append((bug, blocker))
                else:
                    broken_links.append((bug, blocker))
            else:
                good_links.append((bug, blocker))
        for blockee in get_blocks(bugdir, bug):
            blocked_by = get_blocked_by(bugdir, blockee)
            if (blockee, bug) in good_links+fixed_links+broken_links:
                continue # already checked that link
            if bug not in blocked_by:
                if repair_broken_links == True:
                    _repair_one_way_link(blockee, bug, blocks=False)
                    fixed_links.append((blockee, bug))
                else:
                    broken_links.append((blockee, bug))
            else:
                good_links.append((blockee, bug))
    return (good_links, fixed_links, broken_links)

class DependencyTree (object):
    """
    Note: should probably be DependencyDiGraph.
    """
    def __init__(self, bugdir, root_bug, depth_limit=0,
                 allowed_status_values=None,
                 allowed_severity_values=None):
        self.bugdir = bugdir
        self.root_bug = root_bug
        self.depth_limit = depth_limit
        self.allowed_status_values = allowed_status_values
        self.allowed_severity_values = allowed_severity_values
    def _build_tree(self, child_fn):
        root = tree.Tree()
        root.bug = self.root_bug
        root.depth = 0
        stack = [root]
        while len(stack) > 0:
            node = stack.pop()
            if self.depth_limit > 0 and node.depth == self.depth_limit:
                continue
            for bug in child_fn(self.bugdir, node.bug):
                if self.allowed_status_values != None \
                        and not bug.status in self.allowed_status_values:
                    continue
                if self.allowed_severity_values != None \
                        and not bug.severity in self.allowed_severity_values:
                    continue
                child = tree.Tree()
                child.bug = bug
                child.depth = node.depth+1
                node.append(child)
                stack.append(child)
        return root
    def blocks_tree(self):
        if not hasattr(self, "_blocks_tree"):
            self._blocks_tree = self._build_tree(get_blocks)
        return self._blocks_tree
    def blocked_by_tree(self):
        if not hasattr(self, "_blocked_by_tree"):
            self._blocked_by_tree = self._build_tree(get_blocked_by)
        return self._blocked_by_tree
