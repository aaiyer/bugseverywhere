# Copyright (C) 2009 W. Trevor King <wking@drexel.edu>
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""Tag a bug, or search bugs for tags"""
from libbe import cmdutil, bugdir
import os, copy
__desc__ = __doc__

def execute(args, test=False):
    """
    >>> from libbe import utility
    >>> bd = bugdir.simple_bug_dir()
    >>> os.chdir(bd.root)
    >>> a = bd.bug_from_shortname("a")
    >>> print a.extra_strings
    []
    >>> execute(["a", "GUI"], test=True)
    Tags for a:
    GUI
    >>> bd._clear_bugs() # resync our copy of bug
    >>> a = bd.bug_from_shortname("a")
    >>> print a.extra_strings
    ['TAG:GUI']
    >>> execute(["a", "later"], test=True)
    Tags for a:
    GUI
    later
    >>> execute(["a"], test=True)
    Tags for a:
    GUI
    later
    >>> execute(["--list"], test=True)
    GUI
    later
    >>> execute(["a", "Alphabetically first"], test=True)
    Tags for a:
    Alphabetically first
    GUI
    later
    >>> bd._clear_bugs() # resync our copy of bug
    >>> a = bd.bug_from_shortname("a")
    >>> print a.extra_strings
    ['TAG:Alphabetically first', 'TAG:GUI', 'TAG:later']
    >>> a.extra_strings = []
    >>> print a.extra_strings
    []
    >>> a.save()
    >>> execute(["a"], test=True)
    >>> bd._clear_bugs() # resync our copy of bug
    >>> a = bd.bug_from_shortname("a")
    >>> print a.extra_strings
    []
    >>> execute(["a", "Alphabetically first"], test=True)
    Tags for a:
    Alphabetically first
    >>> execute(["--remove", "a", "Alphabetically first"], test=True)
    """
    parser = get_parser()
    options, args = parser.parse_args(args)
    cmdutil.default_complete(options, args, parser,
                             bugid_args={0: lambda bug : bug.active==True})

    if len(args) == 0 and options.list == False:
        raise cmdutil.UsageError("Please specify a bug id.")
    elif len(args) > 2 or (len(args) > 0 and options.list == True):
        help()
        raise cmdutil.UsageError("Too many arguments.")
    
    bd = bugdir.BugDir(from_disk=True, manipulate_encodings=not test)
    if options.list:
        bd.load_all_bugs()
        tags = []
        for bug in bd:
            for estr in bug.extra_strings:
                if estr.startswith("TAG:"):
                    tag = estr[4:]
                    if tag not in tags:
                        tags.append(tag)
        tags.sort()
        if len(tags) > 0:
            print '\n'.join(tags)
        return
    bug = bd.bug_from_shortname(args[0])
    if len(args) == 2:
        given_tag = args[1]
        estrs = bug.extra_strings
        tag_string = "TAG:%s" % given_tag
        if options.remove == True:
            estrs.remove(tag_string)
        else: # add the tag
            estrs.append(tag_string)
        bug.extra_strings = estrs # reassign to notice change
        bd.save()

    tags = []
    for estr in bug.extra_strings:
        if estr.startswith("TAG:"):
            tags.append(estr[4:])

    if len(tags) > 0:
        print "Tags for %s:" % bug.uuid
        print '\n'.join(tags)

def get_parser():
    parser = cmdutil.CmdOptionParser("be tag BUG-ID [TAG]\nor:    be tag --list")
    parser.add_option("-r", "--remove", action="store_true", dest="remove",
                      help="Remove TAG (instead of adding it)")
    parser.add_option("-l", "--list", action="store_true", dest="list",
                      help="List all available tags and exit")
    return parser

longhelp="""
If TAG is given, add TAG to BUG-ID.  If it is not specified, just
print the tags for BUG-ID.

To search for bugs with a particular tag, try
  $ be list --extra-strings TAG:<your-tag>
"""

def help():
    return get_parser().help_str() + longhelp
