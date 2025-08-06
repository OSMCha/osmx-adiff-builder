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

# export PATH=$PATH:/mnt/osmcha/bin # Is this really necesary, seems not
WORKDIR=/data
REPLICATION_ADIFFS=$WORKDIR/stage-data/replication-adiffs # make sure this same as in ./update.sh
SPLIT_ADIFFS=$WORKDIR/stage-data/split-adiffs
CHANGESET_DIR=$WORKDIR/stage-data/changesets
BUCKET_DIR=$WORKDIR/bucket-data/changesets
API_URL=${API_URL:-https://api.openstreetmap.org}


mkdir -p $SPLIT_ADIFFS $CHANGESET_DIR $BUCKET_DIR

for adiff_file in $(find $REPLICATION_ADIFFS/ -type f); do
  seqno=$(basename -s .adiff $adiff_file)
  tmpdir=$(mktemp -d)

  # split the adiff file
  python split_adiff.py $adiff_file $tmpdir

  # Check if adiff files  are been generated
  if [ -z "$(ls -A "$tmpdir"/*.adiff 2>/dev/null)" ]; then
    echo "No .adiff files generated from $adiff_file — skipping"
    rm -rf "$tmpdir"
    continue
  fi

  for file in $tmpdir/*.adiff; do
    changeset=$(basename -s .adiff $file)
    echo "Changeset $changeset has $seqno adiffs"
    # move the adiff file into place
    mkdir -p $$SPLIT_ADIFFS/$changeset/
    mv $file $$SPLIT_ADIFFS/$changeset/$seqno.adiff
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

# # merge all our split files, potentially updating existing changesets.
# # this is done using a makefile script in order to avoid needlessly reprocessing
# # changesets whose set of input (split-adiffs/) files haven't changed.
# merge.mk
make -f merge.mk API_URL="$API_URL"
# # clean up old stage-data that we don't need anymore
./gc.sh
