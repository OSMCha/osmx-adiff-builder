#!/bin/sh

# Usage: process.sh
# 
# Does the following:
# - splits all adiffs in stage-data/replication-adiffs/*.adiff into stage-data/split-adiffs/*/
# - moves
# - merges all split adiffs in each split-adiffs/*/ into one merged-adiffs/*.adiff

# NOTE: this is an implementation detail of how OSMCha's deployment of these scripts
# works (the scripts are installed into /mnt/osmcha/bin). In your own deployment you
# should ensure that the scripts (specifically split_adiff.py, merge_adiff.py, and
# merge.mk) are in your $PATH, because process.sh assumes they are.
export PATH=$PATH:/mnt/osmcha/bin

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

# clean up old stage-data that we don't need anymore
gc.sh
