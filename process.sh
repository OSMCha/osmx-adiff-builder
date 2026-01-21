#!/bin/sh

# Usage: process.sh [replication_dir] [split_dir] [changeset_dir] [bucket_dir] [api_url] [minutes_filter]
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

REPLICATION_ADIFFS_DIR=${1:-'stage-data/replication-adiffs'}
SPLIT_ADIFFS_DIR=${2:-'stage-data/split-adiffs'}
CHANGESET_DIR=${3:-'stage-data/changesets'}
BUCKET_DIR=${4:-'bucket-data/replication/minute'}
API_URL=${5:-'https://api.openstreetmap.org'}
FILTER_ADIFF_FILES=${6:-''}


# Determine which .adiff files to process
if [ -n "$FILTER_ADIFF_FILES" ]; then
  echo "Filtering .adiff files modified in the last $FILTER_ADIFF_FILES minutes..."
  adiff_files=$(find "$REPLICATION_ADIFFS_DIR" -type f -mmin -"$FILTER_ADIFF_FILES")
else
  echo "Processing all .adiff files in $REPLICATION_ADIFFS_DIR..."
  adiff_files=$(find "$REPLICATION_ADIFFS_DIR" -type f)
fi

for adiff_file in $adiff_files; do

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
    mkdir -p $SPLIT_ADIFFS_DIR/$changeset/
    mv $file $SPLIT_ADIFFS_DIR/$changeset/$seqno.adiff
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
make -f merge.mk \
  REPLICATION_ADIFFS_DIR="${REPLICATION_ADIFFS_DIR}" \
  SPLIT_ADIFFS_DIR="${SPLIT_ADIFFS_DIR}" \
  CHANGESET_DIR="${CHANGESET_DIR}" \
  BUCKET_DIR="${BUCKET_DIR}" \
  API_URL="${API_URL}"

# # clean up old stage-data that we don't need anymore
./gc.sh "${SPLIT_ADIFFS_DIR}" "${CHANGESET_DIR}"
