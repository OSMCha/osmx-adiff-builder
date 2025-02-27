#!/usr/bin/make -f

# Builds changeset augmented diffs from stage-data/split-adiffs/*/ and writes
# them to bucket-data/*.adiff. Skips any output changeset that already exists
# and is newer than any of its constituent inputs.

.PHONY: all
.ONESHELL:
.SECONDEXPANSION:

MAKEDIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

# all: metadatas changesets
all: changesets

changesets: $(shell find stage-data/split-adiffs/ -mindepth 1 -type d -printf 'stage-data/changesets/%P.adiff.md5\n')

# bucket-data/changesets/%.adiff: $$(wildcard stage-data/split-adiffs/%/*)
stage-data/changesets/%.adiff.md5: $$(wildcard stage-data/split-adiffs/%/*)
	tmpfile=$$(mktemp)
	merge_adiffs.py $^ | xmlstarlet format > $$tmpfile
	if [ -s $$tmpfile ]; then
		# merge_adiffs.py can fail if it is given no input files or if one or more
		# of its input files are not found. Either of these can happen if the input
		# split-adiffs/*/ directory is deleted by gc.sh while Make is running this
		# script. So we only move the adiff file into bucket-data and update the
		# stamp file if the merged output file is nonempty (-s).
		md5sum < $$tmpfile > $@
		gzip -c < $$tmpfile > $$tmpfile.gz
		mv $$tmpfile.gz bucket-data/changesets/$*.adiff && rm $$tmpfile
	fi

metadatas: $(shell find stage-data/split-adiffs/ -mindepth 1 -type d -printf '%p/metadata.xml\n')

stage-data/split-adiffs/%/metadata.xml:
	curl -sL https://api.openstreetmap.org/api/0.6/changeset/$* -o $@
