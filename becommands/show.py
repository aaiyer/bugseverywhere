"""Show a particular bug"""
from libbe import bugdir, cmdutil, utility
import os

def execute(args):
    bug_dir = cmdutil.bug_tree()
    if len(args) !=1:
        raise cmdutil.UserError("Please specify a bug id.")
    bug = cmdutil.get_bug(args[0], bug_dir)
    print cmdutil.bug_summary(bug, list(bug_dir.list())).rstrip("\n")
    if bug.time is None:
        time_str = "(Unknown time)"
    else:
        time_str = "%s (%s)" % (utility.handy_time(bug.time), 
                                utility.time_to_str(bug.time))
    print "Created: %s" % time_str
    for comment in bug.list_comments():
        print "--------- Comment ---------"
        print "From: %s" % comment.From
        print "Date: %s\n" % utility.time_to_str(comment.date)
        print comment.body.rstrip('\n')
