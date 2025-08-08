#!/bin/sh

# Usage: gc.sh
# 
# Deletes old intermediate files in stage-data/ that aren't needed anymore.
# The openstreetmap.org server automatically closes changesets after 24h,
# so if a changeset hasn't been modified in at least that long, we can
# safely assume that it won't change again in the future.

SPLIT_ADIFFS_DIR=${1:-'stage-data/split-adiffs'}
CHANGESET_DIR=${2:-'stage-data/changesets'}


find "$CHANGESET_DIR" -type f -name "*.adiff.md5" -mtime +3 | while read stampfile; do
  changeset_id=$(basename "$stampfile" .adiff.md5)
  echo "removing files for changeset $changeset_id"
  # atomically move the split files to a temporary location before deleting
  # them (prevents merge_adiffs.py being run during the deletion, which could
  # result in an incomplete adiff being generated)
  tmpdir=$(mktemp -d)
  mv $SPLIT_ADIFFS_DIR/$changeset_id/ $tmpdir
  rm -rf $tmpdir

  # also delete the stamp file
  rm $CHANGESET_DIR/$changeset_id.adiff.md5
done
