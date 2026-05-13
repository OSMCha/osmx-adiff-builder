#!/bin/bash

# Usage: update.sh planet.osmx
#
# For each new replication file since planet.osmx was last updated, generates
# per-changeset augmented diffs (using `osmx-rs augmented-diff --split`) and
# writes them to /mnt/osmcha/stage-data/split-adiffs/<changeset_id>/<seqno>.adiff,
# then applies the replication file to planet.osmx via `osmx update`.
#
# This script runs once and then exits. How long it takes to run depends on
# how far behind planet.osmx is compared to the latest available seqno on the
# replication server. To keep your planet.osmx continuously up to date, you
# should run this script in a cron job once per minute. It is good practice
# to use flock to ensure that only one instance of the job is running at a time.

set -euxo pipefail

osm replication minute --seqno $(osmx query $1 seqnum) \
  | while read seqno timestamp url; do
  test -z "$seqno" && continue # skip blank lines or empty output

  curl -sL $url | gzip -d > $seqno.osc

  tmpdir=$(mktemp -d)
  time osmx-rs augmented-diff --split $1 $seqno.osc $tmpdir

  for file in $tmpdir/*.adiff; do
    changeset=$(basename -s .adiff $file)
    mkdir -p /mnt/osmcha/stage-data/split-adiffs/$changeset/
    mv $file /mnt/osmcha/stage-data/split-adiffs/$changeset/$seqno.adiff
  done

  rm -rf $tmpdir

  osmx update $1 $seqno.osc $seqno $timestamp --commit
  rm $seqno.osc
done
