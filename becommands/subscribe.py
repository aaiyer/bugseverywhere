# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
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
"""(Un)subscribe to change notification"""
from libbe import cmdutil, bugdir, tree
import os, copy
__desc__ = __doc__

TAG="SUBSCRIBE:"

class SubscriptionType (tree.Tree):
    """
    Trees of subscription types to allow users to select exactly what
    notifications they want to subscribe to.
    """
    def __init__(self, type_name, *args, **kwargs):
        tree.Tree.__init__(self, *args, **kwargs)
        self.type = type_name
    def __str__(self):
        return self.type
    def __repr__(self):
        return "<SubscriptionType: %s>" % str(self)
    def string_tree(self, indent=0):
        lines = []
        for depth,node in self.thread():
            lines.append("%s%s" % (" "*(indent+2*depth), node))
        return "\n".join(lines)

BUGDIR_TYPE_NEW = SubscriptionType("new")
BUGDIR_TYPE_ALL = SubscriptionType("all", [BUGDIR_TYPE_NEW])

# same name as BUGDIR_TYPE_ALL for consistency
BUG_TYPE_ALL = SubscriptionType(str(BUGDIR_TYPE_ALL))

INVALID_TYPE = SubscriptionType("INVALID")

class InvalidType (ValueError):
    def __init__(self, type_name, type_root):
        msg = "Invalid type %s for tree:\n%s" \
            % (type_name, type_root.string_tree(4))
        ValueError.__init__(self, msg)
        self.type_name = type_name
        self.type_root = type_root


def execute(args, manipulate_encodings=True):
    """
    >>> bd = bugdir.SimpleBugDir()
    >>> bd.set_sync_with_disk(True)
    >>> os.chdir(bd.root)
    >>> a = bd.bug_from_shortname("a")
    >>> print a.extra_strings
    []
    >>> execute(["-s","John Doe <j@doe.com>", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for a:
    John Doe <j@doe.com>    all    *
    >>> bd._clear_bugs() # resync our copy of bug
    >>> a = bd.bug_from_shortname("a")
    >>> print a.extra_strings
    ['SUBSCRIBE:John Doe <j@doe.com>\\tall\\t*']
    >>> execute(["-s","Jane Doe <J@doe.com>", "-S", "a.com,b.net", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for a:
    Jane Doe <J@doe.com>    all    a.com,b.net
    John Doe <j@doe.com>    all    *
    >>> execute(["-s","Jane Doe <J@doe.com>", "-S", "a.edu", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for a:
    Jane Doe <J@doe.com>    all    a.com,a.edu,b.net
    John Doe <j@doe.com>    all    *
    >>> execute(["-u", "-s","Jane Doe <J@doe.com>", "-S", "a.com", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for a:
    Jane Doe <J@doe.com>    all    a.edu,b.net
    John Doe <j@doe.com>    all    *
    >>> execute(["-s","Jane Doe <J@doe.com>", "-S", "*", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for a:
    Jane Doe <J@doe.com>    all    *
    John Doe <j@doe.com>    all    *
    >>> execute(["-u", "-s","Jane Doe <J@doe.com>", "a"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for a:
    John Doe <j@doe.com>    all    *
    >>> execute(["-u", "-s","John Doe <j@doe.com>", "a"], manipulate_encodings=False)
    >>> execute(["-s","Jane Doe <J@doe.com>", "-t", "new", "DIR"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for bug directory:
    Jane Doe <J@doe.com>    new    *
    >>> execute(["-s","Jane Doe <J@doe.com>", "DIR"], manipulate_encodings=False) # doctest: +NORMALIZE_WHITESPACE
    Subscriptions for bug directory:
    Jane Doe <J@doe.com>    all    *
    >>> bd.cleanup()
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})

    if len(args) > 1:
        help()
        raise cmdutil.UsageError("Too many arguments.")

    bd = bugdir.BugDir(from_disk=True,
                       manipulate_encodings=manipulate_encodings)

    subscriber = options.subscriber
    if subscriber == None:
        subscriber = bd.user_id
    if options.unsubscribe == True:
        if options.servers == None:
            options.servers = "INVALID"
        if options.types == None:
            options.types = "INVALID"
    else:
        if options.servers == None:
            options.servers = "*"
        if options.types == None:
            options.types = "all"
    servers = options.servers.split(",")
    types = options.types.split(",")

    if len(args) == 0 or args[0] == "DIR": # directory-wide subscriptions
        type_root = BUGDIR_TYPE_ALL
        entity = bd
        entity_name = "bug directory"
    else: # bug-specific subscriptions
        type_root = BUG_TYPE_ALL
        bug = bd.bug_from_shortname(args[0])
        entity = bug
        entity_name = bug.uuid
    if options.list_all == True:
        entity_name = "anything in the bug directory"

    types = [type_from_name(name, type_root, default=INVALID_TYPE,
                            default_ok=options.unsubscribe)
             for name in types]
    estrs = entity.extra_strings
    if options.list == True or options.list_all == True:
        pass
    else: # alter subscriptions
        if options.unsubscribe == True:
            estrs = unsubscribe(estrs, subscriber, types, servers, type_root)
        else: # add the tag
            estrs = subscribe(estrs, subscriber, types, servers, type_root)
        entity.extra_strings = estrs # reassign to notice change

    if options.list_all == True:
        bd.load_all_bugs()
        subscriptions = get_bugdir_subscribers(bd, servers[0])
    else:
        subscriptions = []
        for estr in entity.extra_strings:
            if estr.startswith(TAG):
                subscriptions.append(estr[len(TAG):])

    if len(subscriptions) > 0:
        print "Subscriptions for %s:" % entity_name
        print '\n'.join(subscriptions)


def get_parser():
    parser = cmdutil.CmdOptionParser("be subscribe ID")
    parser.add_option("-u", "--unsubscribe", action="store_true",
                      dest="unsubscribe", default=False,
                      help="Unsubscribe instead of subscribing.")
    parser.add_option("-a", "--list-all", action="store_true",
                      dest="list_all", default=False,
                      help="List all subscribers (no ID argument, read only action).")
    parser.add_option("-l", "--list", action="store_true",
                      dest="list", default=False,
                      help="List subscribers (read only action).")
    parser.add_option("-s", "--subscriber", dest="subscriber",
                      metavar="SUBSCRIBER",
                      help="Email address of the subscriber (defaults to bugdir.user_id).")
    parser.add_option("-S", "--servers", dest="servers", metavar="SERVERS",
                      help="Servers from which you want notification.")
    parser.add_option("-t", "--type", dest="types", metavar="TYPES",
                      help="Types of changes you wish to be notified about.")
    return parser

longhelp="""
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
  For DIR :
%s

For unsubscription, any listed SERVERS and TYPES are removed from your
subscription.  Either the catch-all server "*" or type "%s" will
remove SUBSCRIBER entirely from the specified ID.

This command is intended for use primarily by public interfaces, since
if you're just hacking away on your private repository, you'll known
what's changed ;).  This command just (un)sets the appropriate
subscriptions, and leaves it up to each interface to perform the
notification.
""" % (BUG_TYPE_ALL.string_tree(6), BUGDIR_TYPE_ALL.string_tree(6),
       BUGDIR_TYPE_ALL)

def help():
    return get_parser().help_str() + longhelp

# internal helper functions

def _generate_string(subscriber, types, servers):
    types = sorted([str(t) for t in types])
    servers = sorted(servers)
    return "%s%s\t%s\t%s" % (TAG,subscriber,",".join(types),",".join(servers))

def _parse_string(string, type_root):
    assert string.startswith(TAG), string
    string = string[len(TAG):]
    subscriber,types,servers = string.split("\t")
    types = [type_from_name(name, type_root) for name in types.split(",")]
    return (subscriber,types,servers.split(","))

def _get_subscriber(extra_strings, subscriber, type_root):
    for i,string in enumerate(extra_strings):
        if string.startswith(TAG):
            s,ts,srvs = _parse_string(string, type_root)
            if s == subscriber:
                return i,s,ts,srvs # match!
    return None # no match

# functions exposed to other modules

def type_from_name(name, type_root, default=None, default_ok=False):
    if name == str(type_root):
        return type_root
    for t in type_root.traverse():
        if name == str(t):
            return t
    if default_ok:
        return default
    raise InvalidType(name, type_root)

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
    >>> es = subscribe(es, "John Doe <j@doe.com>", [BUGDIR_TYPE_ALL], ["a.com"], BUGDIR_TYPE_ALL)
    >>> es = subscribe(es, "Jane Doe <J@doe.com>", [BUGDIR_TYPE_NEW], ["*"], BUGDIR_TYPE_ALL)
    >>> sgs(es, BUGDIR_TYPE_ALL, "a.com", BUGDIR_TYPE_ALL)
    ['John Doe <j@doe.com>']
    >>> sgs(es, BUGDIR_TYPE_ALL, "a.com", BUGDIR_TYPE_ALL, match_descendant_types=True)
    ['Jane Doe <J@doe.com>', 'John Doe <j@doe.com>']
    >>> sgs(es, BUGDIR_TYPE_ALL, "b.net", BUGDIR_TYPE_ALL, match_descendant_types=True)
    ['Jane Doe <J@doe.com>']
    >>> sgs(es, BUGDIR_TYPE_NEW, "a.com", BUGDIR_TYPE_ALL)
    ['Jane Doe <J@doe.com>']
    >>> sgs(es, BUGDIR_TYPE_NEW, "a.com", BUGDIR_TYPE_ALL, match_ancestor_types=True)
    ['Jane Doe <J@doe.com>', 'John Doe <j@doe.com>']
    """
    for string in extra_strings:
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
    or "DIR" (in the case of a bugdir subscription).

    Only checks bugs that are currently in memory, so you might want
    to call bugdir.load_all_bugs() first.

    >>> bd = bugdir.SimpleBugDir(sync_with_disk=False)
    >>> a = bd.bug_from_shortname("a")
    >>> bd.extra_strings = subscribe(bd.extra_strings, "John Doe <j@doe.com>", [BUGDIR_TYPE_ALL], ["a.com"], BUGDIR_TYPE_ALL)
    >>> bd.extra_strings = subscribe(bd.extra_strings, "Jane Doe <J@doe.com>", [BUGDIR_TYPE_NEW], ["*"], BUGDIR_TYPE_ALL)
    >>> a.extra_strings = subscribe(a.extra_strings, "John Doe <j@doe.com>", [BUG_TYPE_ALL], ["a.com"], BUG_TYPE_ALL)
    >>> subscribers = get_bugdir_subscribers(bd, "a.com")
    >>> subscribers["Jane Doe <J@doe.com>"]["DIR"]
    [<SubscriptionType: new>]
    >>> subscribers["John Doe <j@doe.com>"]["DIR"]
    [<SubscriptionType: all>]
    >>> subscribers["John Doe <j@doe.com>"]["a"]
    [<SubscriptionType: all>]
    >>> get_bugdir_subscribers(bd, "b.net")
    {'Jane Doe <J@doe.com>': {'DIR': [<SubscriptionType: new>]}}
    >>> bd.cleanup()
    """
    subscribers = {}
    for sub in get_subscribers(bugdir.extra_strings, BUGDIR_TYPE_ALL, server,
                               BUGDIR_TYPE_ALL, match_descendant_types=True):
        i,s,ts,srvs = _get_subscriber(bugdir.extra_strings,sub,BUGDIR_TYPE_ALL)
        subscribers[sub] = {"DIR":ts}
    for bug in bugdir:
        for sub in get_subscribers(bug.extra_strings, BUG_TYPE_ALL, server,
                                   BUG_TYPE_ALL, match_descendant_types=True):
            i,s,ts,srvs = _get_subscriber(bug.extra_strings,sub,BUG_TYPE_ALL)
            if sub in subscribers:
                subscribers[sub][bug.uuid] = ts
            else:
                subscribers[sub] = {bug.uuid:ts}
    return subscribers
