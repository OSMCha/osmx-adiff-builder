#!/bin/sh

# Usage: gc.sh
# 
# Deletes old intermediate files in stage-data/ that aren't needed anymore.
# The openstreetmap.org server automatically closes changesets after 24h,
# so if a changeset hasn't been modified in at least that long, we can
# safely assume that it won't change again in the future.

find stage-data/changesets/ -type f -mtime +3 -printf '%P\n' \
  | cut -d '.' -f1 \
  | while read changeset_id; do
    echo "removing files for changeset $changeset_id"
    # atomically move the split files to a temporary location before deleting
    # them (prevents merge_adiffs.py being run during the deletion, which could
    # result in an incomplete adiff being generated)
    tmpdir=$(mktemp -d)
    mv stage-data/split-adiffs/$changeset_id/ $tmpdir
    rm -rf $tmpdir

    # also delete the stamp file
    rm stage-data/changesets/$changeset_id.adiff.md5
done
