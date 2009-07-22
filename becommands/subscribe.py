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
from libbe import cmdutil, bugdir
import os, copy
__desc__ = __doc__

TAG="SUBSCRIBE:"

def execute(args, manipulate_encodings=True):
    """
    >>> from libbe import utility
    >>> bd = bugdir.simple_bug_dir()
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
        if options.unsubscribe == False:
            for t in types:
                assert t in ["all","new"], t
        entity = bd
        entity_name = "bug directory"
    else: # bug-specific subscriptions
        if options.unsubscribe == False:
            assert types == ["all"], types
        bug = bd.bug_from_shortname(args[0])
        entity = bug
        entity_name = bug.uuid

    estrs = entity.extra_strings
    if options.unsubscribe == True:
        estrs = unsubscribe(estrs, subscriber, types, servers)
    else: # add the tag
        estrs = subscribe(estrs, subscriber, types, servers)
    entity.extra_strings = estrs # reassign to notice change

    subscriptions = []
    for estr in entity.extra_strings:
        if estr.startswith(TAG):
            subscriptions.append(estr[len(TAG):])

    if len(subscriptions) > 0:
        print "Subscriptions for %s:" % entity_name
        print '\n'.join(subscriptions)

def generate_string(subscriber, types, servers):
    return "%s%s\t%s\t%s" % (TAG,subscriber,",".join(types),",".join(servers))

def parse_string(string):
    assert string.startswith(TAG), string
    string = string[len(TAG):]
    subscriber,types,servers = string.split("\t")
    return (subscriber,types.split(","),servers.split(","))

def get_subscribers(extra_strings, type, server):
    for string in extra_strings:
        subscriber,types,servers = parse_string(string)
        type_match = False
        if type in types or types == ["all"]:
            type_match = True
        server_match = False
        if server in servers or servers == ["*"]:
            server_match = True
        if type_match == True and server_match == True: 
            yield subscriber

def get_matching_string(extra_strings, subscriber, types, servers):
    for i,string in enumerate(extra_strings):
        if string.startswith(TAG):
            s,ts,srvs = parse_string(string)
            if s == subscriber:
                return i,s,ts,srvs # match!
    return None # no match

def subscribe(extra_strings, subscriber, types, servers):
    args = get_matching_string(extra_strings, subscriber, types, servers)
    if args == None: # no match
        extra_strings.append(generate_string(subscriber, types, servers))
        return extra_strings
    # Alter matched string
    i,s,ts,srvs = args
    if "all" in types+ts:
        ts = ["all"]
    else:
        ts = list(set(types+ts))
        ts.sort()
    if "*" in servers+srvs:
        srvs = ["*"]
    else:
        srvs = list(set(servers+srvs))
        srvs.sort()
    extra_strings[i] = generate_string(subscriber, ts, srvs)
    return extra_strings

def unsubscribe(extra_strings, subscriber, types, servers):
    args = get_matching_string(extra_strings, subscriber, types, servers)
    if args == None: # no match
        return extra_strings # pass
    # Remove matched string
    i,s,ts,srvs = args
    if "all" in types:
        ts = []
    else:
        for t in types:
            if t in ts:
                ts.remove(t)
    if "*" in servers+srvs:
        srvs = []
    else:
        for srv in servers:
            if srv in srvs:
                srvs.remove(srv)
    if len(ts) == 0 or len(srvs) == 0:
        extra_strings.pop(i)
    else:
        extra_strings[i] = generate_string(subscriber, ts, srvs)
    return extra_strings

def get_parser():
    parser = cmdutil.CmdOptionParser("be subscribe ID")
    parser.add_option("-u", "--unsubscribe", action="store_true",
                      dest="unsubscribe", default=False,
                      help="Unsubscribe instead of subscribing.")
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
  For bugs:  all
  For DIR :  all
             new  - only notify when new bugs are added

For unsubscription, any listed SERVERS and TYPES are removed from your
subscription.  Either the catch-all server "*" or type "all" will
remove SUBSCRIBER entirely from the specified ID.

This command is intended for use primarily by public interfaces, since
if you're just hacking away on your private repository, you'll known
what's changed ;).  This command just (un)sets the appropriate
subscriptions, and leaves it up to each interface to perform the
notification.
"""

def help():
    return get_parser().help_str() + longhelp
