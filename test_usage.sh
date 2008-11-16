#!/bin/bash
#
# Run through some simple usage cases.  This both tests that important
# features work, and gives an example of suggested usage to get people
# started.
#
# usage: test_usage.sh

set -e # exit imediately on failed command
set -o pipefail # pipes fail if any stage fails
set -v # verbose, echo commands to stdout

exec 6>&2 # save stderr to file descriptor 6
exec 2>&1 # fd 2 now writes to stdout

ID=`bzr whoami`
echo "I am: $ID"

TESTDIR=`mktemp -d /tmp/BEtest.XXXXXXXXXX`
cd $TESTDIR
bzr init
be set-root .
OUT=`be new 'having too much fun'`
echo "$OUT"
BUG=`echo "$OUT" | sed -n 's/Created bug with ID //p'`
echo "Working with bug: $BUG"
be comment $BUG "This is an argument"
be comment $BUG:1 "No it isn't" # comment on the first comment
be show $BUG            # show details on a given bug
be close $BUG           # set bug status to 'closed'
be comment $BUG "It's closed, but I can still comment."
be open $BUG            # set bug status to 'open'
be comment $BUG "Reopend, comment again"
be status $BUG fixed    # set bug status to 'fixed'
be show $BUG            # show bug details & comments
be list                 # list all open bugs
be list --status closed # list all closed bugs
be assign $BUG          # assign the bug to yourself
be list -m              # see bugs assigned to you
be assign $BUG 'Joe'    # assign the bug to Joe
be list --assigned Joe  # list the bugs assigned to Joe
be assign $BUG none     # assign the bug to noone
be remove $BUG # decide that you don't like that bug after all
cd /
rm -rf $TESTDIR

exec 2>&6 6>&- # restore stderr and close fd 6
