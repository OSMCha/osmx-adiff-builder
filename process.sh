#!/bin/sh

# Usage: process.sh
# 
# Does the following:
# - splits all adiffs in stage-data/replication-adiffs/*.adiff into stage-data/split-adiffs/*/
# - moves
# - merges all split adiffs in each split-adiffs/*/ into one merged-adiffs/*.adiff

LOCKFILE=/var/run/osmx-adiff-process.lock

# flock -n $LOCKFILE || { echo "already running" && exit 0 }

for adiff_file in $(find stage-data/replication-adiffs/ -type f); do
  seqno=$(basename -s .adiff $adiff_file)
  tmpdir=$(mktemp -d)

  # split the adiff file
  split_adiff.py $adiff_file $tmpdir

  for file in $tmpdir/*.adiff; do
    changeset=$(basename -s .adiff $file)
    mkdir -p stage-data/split-adiffs/$changeset/
    mv $file stage-data/split-adiffs/$changeset/$seqno.adiff
  done

  rm -rf $tmpdir

  # move the adiff file to the output directory. this means it won't be processed
  # again in the future and can be uploaded to R2 and deleted locally.
  # compress it first
  tmpfile=$(mktemp)
  gzip -c < $adiff_file > $tmpfile
  # move it into place atomically
  mv $tmpfile bucket-data/replication/minute/$(basename $adiff_file)
  # remove the uncompressed original
  rm $adiff_file
done

# merge all our split files, potentially updating existing changesets.
# this is done using a makefile script in order to avoid needlessly reprocessing
# changesets whose set of input (split-adiffs/) files haven't changed.
merge.mk


