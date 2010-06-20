#!/bin/bash
#
# Test upgrade functionality by checking out revisions with the
# various initial on-disk versions and running `be list` on them to
# force an auto-upgrade.
#
# usage: test_upgrade.sh

REVS='revid:wking@drexel.edu-20090831063121-85p59rpwoi1mzk3i
revid:wking@drexel.edu-20090831171945-73z3wwt4lrm7zbmu
revid:wking@drexel.edu-20091205224008-z4fed13sd80bj4fe
revid:wking@drexel.edu-20091207123614-okq7i0ahciaupuy9'

ROOT=$(bzr root)
BE="$ROOT/be"
cd "$ROOT"

echo "$REVS" | while read REV; do
    TMPDIR=$(mktemp --directory --tmpdir "BE-upgrade.XXXXXXXXXX")
    REPO="$TMPDIR/repo"
    echo "Testing revision: $REV"
    echo "  Test directory: $REPO"
    bzr checkout --lightweight --revision="$REV" "$ROOT" "$TMPDIR/repo"
    VERSION=$(cat "$REPO/.be/version")
    echo "  Version: $VERSION"
    $BE --repo "$REPO" list > /dev/null
    RET="$?"
    rm -rf "$TMPDIR"
    if [ $RET -ne 0 ]; then
	echo "Error! ($RET)"
	exit $RET
    fi
done
