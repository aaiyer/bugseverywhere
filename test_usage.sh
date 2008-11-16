#!/bin/bash
#
# Run through some simple usage cases.  This both tests that important
# features work, and gives an example of suggested usage to get people
# started.
#
# usage: test_usage.sh RCS
# where RCS is one of:
#   bzr, git, hg, arch, none

set -e # exit imediately on failed command
set -o pipefail # pipes fail if any stage fails
set -v # verbose, echo commands to stdout

exec 6>&2 # save stderr to file descriptor 6
exec 2>&1 # fd 2 now writes to stdout

if [ $# -ne 1 ]
then
    echo "usage: test_usage.sh RCS"
    echo ""
    echo "where RCS is one of"
    for RCS in bzr git hg arch none
    do
	echo "  $RCS"
    done
    exit 1
fi

RCS="$1"

TESTDIR=`mktemp -d /tmp/BEtest.XXXXXXXXXX`
cd $TESTDIR

if [ "$RCS" == "bzr" ]
then
    ID=`bzr whoami`
    bzr init
elif [ "$RCS" == "git" ]
then
    NAME=`git-config user.name`
    EMAIL=`git-config user.email`
    ID="$NAME <$EMAIL>"
    git init
elif [ "$RCS" == "hg" ]
then
    ID=`hg showconfig ui.username`
    hg init
elif [ "$RCS" == "arch" ]
then
    ID=`tla my-id`
    tla init-tree
elif [ "$RCS" == "none" ]
then
    ID=`id -nu`
else
    echo "Unrecognized RCS $RCS"
    exit 1
fi
if [ -z "$ID" ]
then # set a default ID
    ID="John Doe <jdoe@example.com>"
fi
echo "I am '$ID'"

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
be list --status fixed  # list all fixed bugs
be assign $BUG          # assign the bug to yourself
be list -m -s fixed     # see fixed bugs assigned to you
be assign $BUG 'Joe'    # assign the bug to Joe
be list -a Joe -s fixed # list the fixed bugs assigned to Joe
be assign $BUG none     # assign the bug to noone
be remove $BUG # decide that you don't like that bug after all
cd /
rm -rf $TESTDIR

exec 2>&6 6>&- # restore stderr and close fd 6
