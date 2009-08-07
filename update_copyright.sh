#!/bin/bash
#
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

# Update copyright information in source code with information from
# the bzr repository.  Run from the BE repository root.
#
# Replaces everything starting with '^# Copyright' and continuing with
# '^#' with an auto-generated copyright blurb.  If you want to add
# #-commented material after a copyright blurb, please insert a blank
# line between the blurb and your comment (as in this file), so the
# next run of update_copyright.sh doesn't clobber your comment.
#
# usage: update_copyright.sh [files ...]
#
# If no files are given, a list of files to update is generated
# automatically.

set -o pipefail

if [ $# -gt 0 ]; then
    FILES="$*"
else
    FILES=`grep -rc "# Copyright" . | grep -v ':0$' | cut -d: -f1`
fi

COPYRIGHT_TEXT="#
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
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA."
# escape newlines and special characters
SED_RM_TRAIL_END='s/[\]n$//'         # strip trailing newline escape
SED_ESC_SPECIAL='s/\([()/]\)/\\\1/g' # escape special characters
ESCAPED_TEXT=`echo "$COPYRIGHT_TEXT" | awk '{printf("%s\\\\n", $0)}' | sed "$SED_RM_TRAIL_END" | sed "$SED_ESC_SPECIAL"`

# adjust the AUTHORS file
AUTHORS=`bzr log | grep '^ *committer\|^ *author' | cut -d: -f2 | sed 's/ <.*//;s/^ *//' | sort | uniq`
AUTHORS=`echo "$AUTHORS" | grep -v 'j\^\|wking\|John Doe\|gianluca'` # remove non-names
echo "Bugs Everywhere was written by:" > AUTHORS
echo "$AUTHORS" >> AUTHORS

CURRENT_YEAR=`date +"%Y"`
TMP=`mktemp BE_update_copyright.XXXXXXX`

for file in $FILES
do
    # Ignore some files
    if [ "${file:0:5}" == "./.be" ]; then
	continue
    fi
    if [ "${file:0:6}" == "./.bzr" ]; then
	continue
    fi
    if [ "${file:0:7}" == "./build" ]; then
	continue
    fi
    if [ "$file" == "./COPYING" ]; then
	continue
    fi
    if [ "$file" == "./update_copyright.sh" ]; then
	continue
    fi
    if [ "$file" == "./xml/catmutt" ]; then
	continue
    fi
    echo "Processing $file"

    # Get author history from bzr
    AUTHORS=`bzr log "$file" | grep "^ *author: \|^ *committer: " | cut -d: -f2 | sed 's/^ *//;s/ *$//' | sort | uniq`
    if [ $? -ne 0 ]; then
	continue # bzr doesn't version that file
    fi
    ORIG_YEAR=`bzr log "$file" | grep "^ *timestamp: " | tail -n1 | sed 's/^ *//;' | cut -b 16-19`

    # Tweak the author list to make up for problems in the bzr
    # history, change of email address, etc.
    
    # Consolidate Chris Ball
    GREP_OUT=`echo "$AUTHORS" | grep 'Chris Ball <cjb@laptop.org>'`
    if [ -n "$GREP_OUT" ]; then
	AUTHORS=`echo "$AUTHORS" | grep -v '^Chris Ball <cjb@thunk.printf.net>$'`
    fi

    # Consolidate Aaron Bentley
    AUTHORS=`echo "$AUTHORS" | sed 's/<abentley@panoramicfeedback.com>/and Panometrics, Inc./'`
    GREP_OUT=`echo "$AUTHORS" | grep 'Aaron Bentley and Panometrics, Inc.'`
    if [ -n "$GREP_OUT" ]; then
	AUTHORS=`echo "$AUTHORS" | grep -v '^Aaron Bentley <aaron.bentley@utoronto.ca>$'`
    fi

    # Consolidate Ben Finney
    AUTHORS=`echo "$AUTHORS" | sed 's/John Doe <jdoe@example.com>/Ben Finney <ben+python@benfinney.id.au>/'`
    GREP_OUt=`echo "$AUTHORS" | grep 'Ben Finney <ben+python@benfinney.id.au>'`
    if [ -n "$GREP_OUT" ]; then
	AUTHORS=`echo "$AUTHORS" | grep -v '^Ben Finney <benf@cybersource.com.au>$'`
    fi

    # Consolidate Trevor King
    AUTHORS=`echo "$AUTHORS" | grep -v "wking <wking@mjolnir>"`

    # Consolidate Gianluca Montecchi
    AUTHORS=`echo "$AUTHORS" | grep -v "gianluca"`

    # Sort again...
    AUTHORS=`echo "$AUTHORS" | sort | uniq`

    # Generate new Copyright string
    if [ "$ORIG_YEAR" == "$CURRENT_YEAR" ]; then
	DATE_RANGE="$CURRENT_YEAR"
	DATE_SPACE="    "
    else
	DATE_RANGE="${ORIG_YEAR}-${CURRENT_YEAR}"
	DATE_SPACE="         "
    fi
    NUM_AUTHORS=`echo "$AUTHORS" | wc -l`
    FIRST_AUTHOR=`echo "$AUTHORS" | head -n 1`
    COPYRIGHT="# Copyright (C) $DATE_RANGE $FIRST_AUTHOR"
    if [ $NUM_AUTHORS -gt 1 ]; then
	OTHER_AUTHORS=`echo "$AUTHORS" | tail -n +2`
	while read AUTHOR; do
	    COPYRIGHT=`echo "$COPYRIGHT\\n#               $DATE_SPACE $AUTHOR"`
	done < <(echo "$OTHER_AUTHORS")
    fi
    COPYRIGHT=`echo "$COPYRIGHT\\n$ESCAPED_TEXT"`

    # Strip old copyright info and replace with tag
    awk 'BEGIN{incopy==0}{if(match($0, "^# Copyright")>0){incopy=1; print "-xyz-COPYRIGHT-zyx-"}else{if(incopy==0){print $0}else{if(match($0, "^#")==0){incopy=0; print $0}}}}' "$file" > "$TMP"

    # Replace tag in with new string
    sed -i "s/^-xyz-COPYRIGHT-zyx-$/$COPYRIGHT/" "$TMP"
    cp "$TMP" "$file"
done

rm -f "$TMP"
