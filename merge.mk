#!/usr/bin/make -f

# Builds changeset augmented diffs from stage-data/split-adiffs/*/ and writes
# them to bucket-data/*.adiff. Skips any output changeset that already exists
# and is newer than any of its constituent inputs.

.PHONY: all
.ONESHELL:
.SECONDEXPANSION:

SPLIT_ADIFFS_DIR ?= stage-data/split-adiffs
CHANGESET_DIR ?= stage-data/changesets
BUCKET_DIR ?= bucket-data/replication/minute
API_URL ?= https://api.openstreetmap.org


MAKEDIR := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

# all: metadatas changesets
all: changesets

changesets: $(shell find $(SPLIT_ADIFFS_DIR)/ -mindepth 1 -type d | sed 's|$(SPLIT_ADIFFS_DIR)|$(CHANGESET_DIR)/|g' | sed 's|$$|.adiff.md5|')

# bucket-data/changesets/%.adiff: $$(wildcard stage-data/split-adiffs/%/*)
$(CHANGESET_DIR)/%.adiff.md5: $$(wildcard $(SPLIT_ADIFFS_DIR)/%/*)
	tmpfile=$$(mktemp)
	python merge_adiffs.py $^ | xmlstarlet format > $$tmpfile
	if [ -s $$tmpfile ]; then
		# merge_adiffs.py can fail if it is given no input files or if one or more
		# of its input files are not found. Either of these can happen if the input
		# split-adiffs/*/ directory is deleted by gc.sh while Make is running this
		# script. So we only move the adiff file into bucket-data and update the
		# stamp file if the merged output file is nonempty (-s).
		md5sum < $$tmpfile > $@
		gzip -c < $$tmpfile > $$tmpfile.gz
		mv $$tmpfile.gz $(BUCKET_DIR)/$*.adiff && rm $$tmpfile
	fi

metadatas: $(shell find $(SPLIT_ADIFFS_DIR)/ -mindepth 1 -type d | sed 's|$$|/metadata.xml|')

$(SPLIT_ADIFFS_DIR)/%/metadata.xml:
	curl -sL "$(API_URL)/api/0.6/changeset/$*" -o $@
