#!/bin/bash
#
# Run through some simple usage cases.  This both tests that important
# features work, and gives an example of suggested usage to get people
# started.
#
# usage: test_usage.sh RCS
# where RCS is one of:
#   bzr, git, hg, arch, none
#
# Note that this script uses the *installed* version of be, not the
# one in your working tree.

set -e # exit immediately on failed command
set -o pipefail # pipes fail if any stage fails
set -v # verbose, echo commands to stdout

exec 6>&2 # save stderr to file descriptor 6
exec 2>&1 # fd 2 now writes to stdout

if [ $# -gt 1 ]
then
    echo "usage: test_usage.sh [RCS]"
    echo ""
    echo "where RCS is one of"
    for RCS in arch bzr darcs git hg none
    do
	echo "  $RCS"
    done
    exit 1
elif [ $# -eq 0 ]
then
    for RCS in arch bzr darcs git hg none
    do
	echo -e "\n\nTesting $RCS\n\n"
	$0 "$RCS" || exit 1
    done
    exit 0
fi

RCS="$1"

TESTDIR=`mktemp -d /tmp/BEtest.XXXXXXXXXX`
cd $TESTDIR

if [ "$RCS" == "arch" ]
then
    ID=`tla my-id`
    ARCH_PARAM_DIR="$HOME/.arch-params"
    ARCH_ARCHIVE_ROOT=`mktemp -d /tmp/BEtest.XXXXXXXXXX`
    UNIQUE=`echo "$ARCH_ARCHIVE_ROOT" | sed 's/\/tmp\/BEtest.//;s/[0-9]//g'` 
    ARCH_ARCHIVE="j@x.com--BE-test-usage-$UNIQUE"
    ARCH_PROJECT="BE-test-usage--twig--99.5"
    ARCH_ARCHIVE_DIR="$ARCH_ARCHIVE_ROOT/$ARCH_PROJECT"
    echo "tla make-archive $ARCH_ARCHIVE $ARCH_ARCHIVE_DIR"
    tla make-archive $ARCH_ARCHIVE $ARCH_ARCHIVE_DIR
    echo "tla archive-setup -A $ARCH_ARCHIVE $ARCH_PROJECT"
    tla archive-setup -A $ARCH_ARCHIVE $ARCH_PROJECT
    echo "tla init-tree -A $ARCH_ARCHIVE $ARCH_PROJECT"
    tla init-tree -A $ARCH_ARCHIVE $ARCH_PROJECT
    echo "Adjusing the naming conventions to allow .files"
    sed -i 's/^source .*/source ^[._=a-zA-X0-9].*$/' '{arch}/=tagging-method'
    echo "tla import -A $ARCH_ARCHIVE --summary 'Began versioning'"
    tla import -A $ARCH_ARCHIVE --summary 'Began versioning'
elif [ "$RCS" == "bzr" ]
then
    ID=`bzr whoami`
    bzr init
elif [ "$RCS" == "darcs" ]
then
    if [ -z "$DARCS_EMAIL" ]; then
	export DARCS_EMAIL="J. Doe <jdoe@example.com>"
    fi
    ID="$DARCS_EMAIL"
    darcs init
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
elif [ "$RCS" == "none" ]
then
    ID=`id -nu`
else
    echo "Unrecognized RCS '$RCS'"
    exit 1
fi
if [ -z "$ID" ]
then # set a default ID
    ID="John Doe <jdoe@example.com>"
fi
echo "I am '$ID'"

be init
OUT=`be new 'having too much fun'`
echo "$OUT"
BUG=`echo "$OUT" | sed -n 's/Created bug with ID //p'`
echo "Working with bug: $BUG"
be comment $BUG "This is an argument"
be set user_id "$ID"    # get tired of guessing user id for none RCS
be set                  # show settings
be comment $BUG:1 "No it isn't" # comment on the first comment
be show $BUG            # show details on a given bug
be close $BUG           # set bug status to 'closed'
be comment $BUG "It's closed, but I can still comment."
be open $BUG            # set bug status to 'open'
be comment $BUG "Reopend, comment again"
be status $BUG fixed    # set bug status to 'fixed'
be list                 # list all open bugs
be list --status fixed  # list all fixed bugs
be assign $BUG          # assign the bug to yourself
be list -m -s fixed     # see fixed bugs assigned to you
be assign $BUG 'Joe'    # assign the bug to Joe
be list -a Joe -s fixed # list the fixed bugs assigned to Joe
be assign $BUG none     # assign the bug to noone
be diff                 # see what has changed
OUT=`be new 'also having too much fun'`
BUGB=`echo "$OUT" | sed -n 's/Created bug with ID //p'`
be comment $BUGB "Blissfully unaware of a similar bug"
be merge $BUG $BUGB     # join BUGB to BUG
be show $BUG            # show bug details & comments
be remove $BUG # decide that you don't like that bug after all
cd /
rm -rf $TESTDIR

if [ "$RCS" == "arch" ]
then
    # Cleanup everything outside of TESTDIR
    rm -rf "$ARCH_ARCHIVE_ROOT"
    rm -rf "$ARCH_PARAM_DIR/=locations/$ARCH_ARCHIVE"
fi

exec 2>&6 6>&- # restore stderr and close fd 6
