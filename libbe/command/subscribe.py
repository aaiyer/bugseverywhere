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

import copy
import os

import libbe
import libbe.bug
import libbe.command
import libbe.diff
import libbe.command.util
import libbe.util.id
import libbe.util.tree


TAG="SUBSCRIBE:"


class Subscribe (libbe.command.Command):
    """(Un)subscribe to change notification

    >>> import sys
    >>> import libbe.bugdir
    >>> bd = libbe.bugdir.SimpleBugDir(memory=False)
    >>> io = libbe.command.StringInputOutput()
    >>> io.stdout = sys.stdout
    >>> ui = libbe.command.UserInterface(io=io)
    >>> ui.storage_callbacks.set_bugdir(bd)
    >>> cmd = Subscribe(ui=ui)

    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    []
    >>> ret = ui.run(cmd, {'subscriber':'John Doe <j@doe.com>'}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for abc/a:
    John Doe <j@doe.com>    all    *
    >>> bd.flush_reload()
    >>> a = bd.bug_from_uuid('a')
    >>> print a.extra_strings
    ['SUBSCRIBE:John Doe <j@doe.com>\\tall\\t*']
    >>> ret = ui.run(cmd, {'subscriber':'Jane Doe <J@doe.com>', 'servers':'a.com,b.net'}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for abc/a:
    Jane Doe <J@doe.com>    all    a.com,b.net
    John Doe <j@doe.com>    all    *
    >>> ret = ui.run(cmd, {'subscriber':'Jane Doe <J@doe.com>', 'servers':'a.edu'}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for abc/a:
    Jane Doe <J@doe.com>    all    a.com,a.edu,b.net
    John Doe <j@doe.com>    all    *
    >>> ret = ui.run(cmd, {'unsubscribe':True, 'subscriber':'Jane Doe <J@doe.com>', 'servers':'a.com'}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for abc/a:
    Jane Doe <J@doe.com>    all    a.edu,b.net
    John Doe <j@doe.com>    all    *
    >>> ret = ui.run(cmd, {'subscriber':'Jane Doe <J@doe.com>', 'servers':'*'}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for abc/a:
    Jane Doe <J@doe.com>    all    *
    John Doe <j@doe.com>    all    *
    >>> ret = ui.run(cmd, {'unsubscribe':True, 'subscriber':'Jane Doe <J@doe.com>'}, ['/a']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for abc/a:
    John Doe <j@doe.com>    all    *
    >>> ret = ui.run(cmd, {'unsubscribe':True, 'subscriber':'John Doe <j@doe.com>'}, ['/a'])
    >>> ret = ui.run(cmd, {'subscriber':'Jane Doe <J@doe.com>', 'types':'new'}, ['DIR']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for bug directory:
    Jane Doe <J@doe.com>    new    *
    >>> ret = ui.run(cmd, {'subscriber':'Jane Doe <J@doe.com>'}, ['DIR']) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for bug directory:
    Jane Doe <J@doe.com>    all    *
    >>> ui.cleanup()
    >>> bd.cleanup()
    """
    name = 'subscribe'

    def __init__(self, *args, **kwargs):
        libbe.command.Command.__init__(self, *args, **kwargs)
        self.options.extend([
                libbe.command.Option(name='unsubscribe', short_name='u',
                    help='Unsubscribe instead of subscribing'),
                libbe.command.Option(name='list-all', short_name='a',
                    help='List all subscribers (no ID argument, read only action)'),
                libbe.command.Option(name='list', short_name='l',
                    help='List subscribers (read only action).'),
                libbe.command.Option(name='subscriber', short_name='s',
                    help='Email address of the subscriber (defaults to your user id).',
                    arg=libbe.command.Argument(
                        name='subscriber', metavar='EMAIL')),
                libbe.command.Option(name='servers', short_name='S',
                    help='Servers from which you want notification.',
                    arg=libbe.command.Argument(
                        name='servers', metavar='STRING')),
                libbe.command.Option(name='types', short_name='t',
                    help='Types of changes you wish to be notified about.',
                    arg=libbe.command.Argument(
                        name='types', metavar='STRING')),
                ])
        self.args.extend([
                libbe.command.Argument(
                    name='id', metavar='ID', default=tuple(),
                    optional=True, repeatable=True,
                    completion_callback=libbe.command.util.complete_bug_comment_id),
                ])

    def _run(self, **params):
        bugdir = self._get_bugdir()
        if params['list-all'] == True or params['list'] == True:
            writeable = bugdir.storage.writeable
            bugdir.storage.writeable = False
            if params['list-all'] == True:
                assert len(params['id']) == 0, params['id']
        subscriber = params['subscriber']
        if subscriber == None:
            subscriber = self._get_user_id()
        if params['unsubscribe'] == True:
            if params['servers'] == None:
                params['servers'] = 'INVALID'
            if params['types'] == None:
                params['types'] = 'INVALID'
        else:
            if params['servers'] == None:
                params['servers'] = '*'
            if params['types'] == None:
                params['types'] = 'all'
        servers = params['servers'].split(',')
        types = params['types'].split(',')

        if len(params['id']) == 0:
            params['id'] = [libbe.diff.BUGDIR_ID]
        for _id in params['id']:
            if _id == libbe.diff.BUGDIR_ID: # directory-wide subscriptions
                type_root = libbe.diff.BUGDIR_TYPE_ALL
                entity = bugdir
                entity_name = 'bug directory'
            else: # bug-specific subscriptions
                type_root = libbe.diff.BUG_TYPE_ALL
                bug,dummy_comment = libbe.command.util.bug_comment_from_user_id(
                    bugdir, _id)
                entity = bug
                entity_name = bug.id.user()
            if params['list-all'] == True:
                entity_name = 'anything in the bug directory'
            types = [libbe.diff.type_from_name(name, type_root, default=libbe.diff.INVALID_TYPE,
                                         default_ok=params['unsubscribe'])
                     for name in types]
            estrs = entity.extra_strings
            if params['list'] == True or params['list-all'] == True:
                pass
            else: # alter subscriptions
                if params['unsubscribe'] == True:
                    estrs = unsubscribe(estrs, subscriber, types, servers, type_root)
                else: # add the tag
                    estrs = subscribe(estrs, subscriber, types, servers, type_root)
                entity.extra_strings = estrs # reassign to notice change

            if params['list-all'] == True:
                bugdir.load_all_bugs()
                subscriptions = get_bugdir_subscribers(bugdir, servers[0])
            else:
                subscriptions = []
                for estr in entity.extra_strings:
                    if estr.startswith(TAG):
                        subscriptions.append(estr[len(TAG):])

            if len(subscriptions) > 0:
                print >> self.stdout, 'Subscriptions for %s:' % entity_name
                print >> self.stdout, '\n'.join(subscriptions)
        if params['list-all'] == True or params['list'] == True:
            bugdir.storage.writeable = writeable
        return 0

    def _long_help(self):
        return """
ID can be either a bug id, or blank/"DIR", in which case it refers to the
whole bug directory.

SERVERS specifies the servers from which you would like to receive
notification.  Multiple severs may be specified in a comma-separated
list, or you can use "*" to match all servers (the default).  If you
have not selected a server, it should politely refrain from notifying
you of changes, although there is no way to guarantee this behavior.

Available TYPES:
  For bugs:
%s
  For %s:
%s

For unsubscription, any listed SERVERS and TYPES are removed from your
subscription.  Either the catch-all server "*" or type "%s" will
remove SUBSCRIBER entirely from the specified ID.

This command is intended for use primarily by public interfaces, since
if you're just hacking away on your private repository, you'll known
what's changed ;).  This command just (un)sets the appropriate
subscriptions, and leaves it up to each interface to perform the
notification.
""" % (libbe.diff.BUG_TYPE_ALL.string_tree(6), libbe.diff.BUGDIR_ID,
       libbe.diff.BUGDIR_TYPE_ALL.string_tree(6),
       libbe.diff.BUGDIR_TYPE_ALL)


# internal helper functions

def _generate_string(subscriber, types, servers):
    types = sorted([str(t) for t in types])
    servers = sorted(servers)
    return "%s%s\t%s\t%s" % (TAG,subscriber,",".join(types),",".join(servers))

def _parse_string(string, type_root):
    assert string.startswith(TAG), string
    string = string[len(TAG):]
    subscriber,types,servers = string.split("\t")
    types = [libbe.diff.type_from_name(name, type_root) for name in types.split(",")]
    return (subscriber,types,servers.split(","))

def _get_subscriber(extra_strings, subscriber, type_root):
    for i,string in enumerate(extra_strings):
        if string.startswith(TAG):
            s,ts,srvs = _parse_string(string, type_root)
            if s == subscriber:
                return i,s,ts,srvs # match!
    return None # no match

# functions exposed to other modules

def subscribe(extra_strings, subscriber, types, servers, type_root):
    args = _get_subscriber(extra_strings, subscriber, type_root)
    if args == None: # no match
        extra_strings.append(_generate_string(subscriber, types, servers))
        return extra_strings
    # Alter matched string
    i,s,ts,srvs = args
    for t in types:
        if t not in ts:
            ts.append(t)
    # remove descendant types
    all_ts = copy.copy(ts)
    for t in all_ts:
        for tt in all_ts:
            if tt in ts and t.has_descendant(tt):
                ts.remove(tt)
    if "*" in servers+srvs:
        srvs = ["*"]
    else:
        srvs = list(set(servers+srvs))
    extra_strings[i] = _generate_string(subscriber, ts, srvs)
    return extra_strings

def unsubscribe(extra_strings, subscriber, types, servers, type_root):
    args = _get_subscriber(extra_strings, subscriber, type_root)
    if args == None: # no match
        return extra_strings # pass
    # Remove matched string
    i,s,ts,srvs = args
    all_ts = copy.copy(ts)
    for t in types:
        for tt in all_ts:
            if tt in ts and t.has_descendant(tt):
                ts.remove(tt)
    if "*" in servers+srvs:
        srvs = []
    else:
        for srv in servers:
            if srv in srvs:
                srvs.remove(srv)
    if len(ts) == 0 or len(srvs) == 0:
        extra_strings.pop(i)
    else:
        extra_strings[i] = _generate_string(subscriber, ts, srvs)
    return extra_strings

def get_subscribers(extra_strings, type, server, type_root,
                    match_ancestor_types=False,
                    match_descendant_types=False):
    """
    Set match_ancestor_types=True if you want to find eveyone who
    cares about your particular type.

    Set match_descendant_types=True if you want to find subscribers
    who may only care about some subset of your type.  This is useful
    for generating lists of all the subscribers in a given set of
    extra_strings.

    >>> def sgs(*args, **kwargs):
    ...     return sorted(get_subscribers(*args, **kwargs))
    >>> es = []
    >>> es = subscribe(es, "John Doe <j@doe.com>", [libbe.diff.BUGDIR_TYPE_ALL],
    ...                ["a.com"], libbe.diff.BUGDIR_TYPE_ALL)
    >>> es = subscribe(es, "Jane Doe <J@doe.com>", [libbe.diff.BUGDIR_TYPE_NEW],
    ...                ["*"], libbe.diff.BUGDIR_TYPE_ALL)
    >>> sgs(es, libbe.diff.BUGDIR_TYPE_ALL, "a.com", libbe.diff.BUGDIR_TYPE_ALL)
    ['John Doe <j@doe.com>']
    >>> sgs(es, libbe.diff.BUGDIR_TYPE_ALL, "a.com", libbe.diff.BUGDIR_TYPE_ALL,
    ...     match_descendant_types=True)
    ['Jane Doe <J@doe.com>', 'John Doe <j@doe.com>']
    >>> sgs(es, libbe.diff.BUGDIR_TYPE_ALL, "b.net", libbe.diff.BUGDIR_TYPE_ALL,
    ...     match_descendant_types=True)
    ['Jane Doe <J@doe.com>']
    >>> sgs(es, libbe.diff.BUGDIR_TYPE_NEW, "a.com", libbe.diff.BUGDIR_TYPE_ALL)
    ['Jane Doe <J@doe.com>']
    >>> sgs(es, libbe.diff.BUGDIR_TYPE_NEW, "a.com", libbe.diff.BUGDIR_TYPE_ALL,
    ... match_ancestor_types=True)
    ['Jane Doe <J@doe.com>', 'John Doe <j@doe.com>']
    """
    for string in extra_strings:
        if not string.startswith(TAG):
            continue
        subscriber,types,servers = _parse_string(string, type_root)
        type_match = False
        if type in types:
            type_match = True
        if type_match == False and match_ancestor_types == True:
            for t in types:
                if t.has_descendant(type):
                    type_match = True
                    break
        if type_match == False and match_descendant_types == True:
            for t in types:
                if type.has_descendant(t):
                    type_match = True
                    break
        server_match = False
        if server in servers or servers == ["*"] or server == "*":
            server_match = True
        if type_match == True and server_match == True:
            yield subscriber

def get_bugdir_subscribers(bugdir, server):
    """
    I have a bugdir.  Who cares about it, and what do they care about?
    Returns a dict of dicts:
      subscribers[user][id] = types
    where id is either a bug.uuid (in the case of a bug subscription)
    or "%(bugdir_id)s" (in the case of a bugdir subscription).

    Only checks bugs that are currently in memory, so you might want
    to call bugdir.load_all_bugs() first.

    >>> bd = bugdir.SimpleBugDir(sync_with_disk=False)
    >>> a = bd.bug_from_shortname("a")
    >>> bd.extra_strings = subscribe(bd.extra_strings, "John Doe <j@doe.com>",
    ...                [libbe.diff.BUGDIR_TYPE_ALL], ["a.com"], libbe.diff.BUGDIR_TYPE_ALL)
    >>> bd.extra_strings = subscribe(bd.extra_strings, "Jane Doe <J@doe.com>",
    ...                [libbe.diff.BUGDIR_TYPE_NEW], ["*"], libbe.diff.BUGDIR_TYPE_ALL)
    >>> a.extra_strings = subscribe(a.extra_strings, "John Doe <j@doe.com>",
    ...                [libbe.diff.BUG_TYPE_ALL], ["a.com"], libbe.diff.BUG_TYPE_ALL)
    >>> subscribers = get_bugdir_subscribers(bd, "a.com")
    >>> subscribers["Jane Doe <J@doe.com>"]["%(bugdir_id)s"]
    [<SubscriptionType: new>]
    >>> subscribers["John Doe <j@doe.com>"]["%(bugdir_id)s"]
    [<SubscriptionType: all>]
    >>> subscribers["John Doe <j@doe.com>"]["a"]
    [<SubscriptionType: all>]
    >>> get_bugdir_subscribers(bd, "b.net")
    {'Jane Doe <J@doe.com>': {'%(bugdir_id)s': [<SubscriptionType: new>]}}
    >>> bd.cleanup()
    """ % {'bugdir_id':libbe.diff.BUGDIR_ID}
    subscribers = {}
    for sub in get_subscribers(bugdir.extra_strings, libbe.diff.BUGDIR_TYPE_ALL,
                               server, libbe.diff.BUGDIR_TYPE_ALL,
                               match_descendant_types=True):
        i,s,ts,srvs = _get_subscriber(bugdir.extra_strings, sub,
                                      libbe.diff.BUGDIR_TYPE_ALL)
        subscribers[sub] = {"DIR":ts}
    for bug in bugdir:
        for sub in get_subscribers(bug.extra_strings, libbe.diff.BUG_TYPE_ALL,
                                   server, libbe.diff.BUG_TYPE_ALL,
                                   match_descendant_types=True):
            i,s,ts,srvs = _get_subscriber(bug.extra_strings, sub,
                                          libbe.diff.BUG_TYPE_ALL)
            if sub in subscribers:
                subscribers[sub][bug.uuid] = ts
            else:
                subscribers[sub] = {bug.uuid:ts}
    return subscribers
