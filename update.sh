#!/bin/bash

# Usage: update.sh planet.osmx data-directory
#
# Updates planet.osmx with the latest OSM changes from the replication server,
# and generates augmented diffs and places them in the data-directory.
#
# This script runs once and then exits. How long it takes to run depends on
# how far behind planet.osmx is compared to the latest available seqno on the
# replication server. To keep your planet.osmx continuously up to date, you
# should run this script in a cron job once per minute. It is good practice
# to use flock to ensure that only one instance of the job is running at a time.

set -ex
export PATH=$PATH:/${PWD}

eval "$(mise activate bash --shims)"

if [ -n "$INITIAL_SEQNUM" ]; then
  seqno_start="$INITIAL_SEQNUM"
else
  seqno_start="$(osmx query "$1" seqnum)"
fi

osm replication minute --seqno $seqno_start \
  | while read seqno timestamp url; do
  test -z "$seqno" && continue # skip blank lines or empty output

  curl -sL $url | gzip -d > $seqno.osc
  tmpfile=$(mktemp)

  augmented_diff.py $1 $seqno.osc | xmlstarlet format > $tmpfile
  mv $tmpfile $2/$seqno.adiff

  osmx update $1 $seqno.osc $seqno $timestamp --commit
  rm $seqno.osc
done
