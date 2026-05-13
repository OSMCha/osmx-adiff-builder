# osmx-adiff-builder

This is a collection of scripts to help create [Augmented Diffs](https://wiki.openstreetmap.org/wiki/Overpass_API/Augmented_Diffs) of changesets in [OpenStreetMap](https://www.openstreetmap.org/), using the openstreetmap.org [replication files](https://wiki.openstreetmap.org/wiki/Planet.osm/diffs) and a local [OSMExpress](https://github.com/bdon/OSMExpress) database. An augmented diff describes a change to OSM in detail, including both old and new versions of every directly and indirectly modified element. [OSMCha](https://osmcha.org) uses augmented diffs to visualize changesets on a map. The data produced by these scripts is available as a service at [adiffs.osmcha.org](https://adiffs.osmcha.org).

## Background

OpenStreetMap is edited thousands of times every day. Edits are grouped into _changesets_. Each changeset is a group of related map edits made by a single mapper, generally confined to a particular area. Changesets are similar to commits in software version control.

The openstreetmap.org website and API offer information about any given changeset. For example:
- https://www.openstreetmap.org/changeset/160415129 (website)
- https://www.openstreetmap.org/api/0.6/changeset/160415129/download (API)

However the information offered here is limited: it only tells you what the _new_ version of each [element](https://wiki.openstreetmap.org/wiki/Elements) looks like. You can't see the old version of the modified elements, so you can't tell exactly what was changed. It also excludes elements which were changed indirectly (e.g. a way that changed shape because some of its nodes were moved, or a relation that changed because some of its members changed).

Because of these limitations, it's not possible to create a useful before-and-after picture of a changeset (like the one shown by [OSMCha](https://osmcha.org/changesets/160415129)) from this information alone. What you need instead is an [Augmented Diff](https://wiki.openstreetmap.org/wiki/Overpass_API/Augmented_Diffs). Augmented Diffs (also called adiffs) contain both old and new versions of every modified element, and they can also contain elements that were indirectly modified.

The goal of the scripts in this repository is to aid in creating these augmented diffs.

## Architecture

You can download the complete OpenStreetMap database from planet.openstreetmap.org, but by the time the 80GB file finishes downloading, it's already out of date. To support access to the very latest OSM data, openstreetmap.org also publishes minutely _replication files_ which describe edits made to OpenStreetMap. Using these replication files, you can keep a local copy of the OSM database in sync with the upstream copy (with a one or two minute delay).

Like the OSM API, the replication files only describe the new version of each changed element. But if you have a local copy of the OSM database, then you already have the _old_ version of each element too. By comparing your current (stale) version of the database and the contents of the replication file, it's possible to construct an Augmented Diff that describes the full story of the changes. Then, you can use the replication file to update your local database, so that it's ready to use to compare with the _next_ replication file and construct another augmented diff for those changes.

This is the strategy we use in the scripts in this repo. The database used is [OSMExpress](https://github.com/bdon/OSMExpress), often abbreviated `osmx`. The workflow is roughly:

1. Download a new replication file from planet.openstreetmap.org
2. Run [`osmx-rs augmented-diff`](https://github.com/jake-low/osmx-rs) to construct augmented diffs from the OSMX database (containing old versions of elements) and the replication file (containing new versions). We use the `--split` flag to produce a separate augmented diff for each changeset, representing the before and after states of elements from the perspective of just that changeset (not the entire replication file).
3. Apply the changes from the replication file to the OSMX database using the `osmx update` command. This advances the database forward in time to match the present openstreetmap.org data, making it ready to use to build diffs for the next replication file.

The steps above are handled by [`update.sh`](./update.sh), which is run every minute as a cron job.

This alone would be sufficient if changesets were always fully contained in a single replication file, but this isn't the case. It's common for changesets to have their edits be split across several replication files. To handle this, we need to accumulate all of the edits for a changeset and merge them together. To do that, we:
1. Create a directory for each changeset the first time we encounter it. Then we take the changeset's augmented diff file for a given replication file and rename it to `$changeset/$seqno.adiff`. This way, if more edits arrive for the same changeset in a future replication file, we'll store them in a new file (named after the new replication file's sequence number) rather than overwriting the previous edits.
2. We use `merge_adiffs.py` to merge all of the augmented diff files in a changeset directory together, generating a single, final _changeset-aligned adiff_. This script must be re-run if additional changes arrive in a future replication file which belong to this changeset. To avoid needlessly re-running this script when no new changes have been added, merging is handled through [`merge.mk`](./merge.mk) (a Makefile script) which skips any output (merged) adiff files whose inputs haven't changed.

Output files from the merge process can be copied to another location or uploaded to Object Storage ([adiffs.osmcha.org](https://adiffs.osmcha.org) uses Cloudflare R2). The data for each changeset is kept locally for a while, in case a replication file is published that has additional changes for this changeset (if this happens, a new version of the changeset will be uploaded, overwriting the old one). After a while, it's safe to assume that a changeset is complete (openstreetmap.org automatically closes changesets after 24h). The [`gc.sh`](./gc.sh) script deletes old files so that they don't fill up the storage on the local machine. We run this periodically with cron.

The state of the system described above is managed through the filesystem. Per-changeset split adiffs are placed in `stage-data/split-adiffs/<changeset_id>/` by `update.sh`, so that `merge.mk` knows which sets of split files have changed and can re-merge them. The final merged files are moved to `bucket-data/changesets/<changeset_id>.adiff`, where they are uploaded to cloud storage and then deleted.

## [adiffs.osmcha.org](https://adiffs.osmcha.org)

The augmented diffs produced by this process are available over HTTPS at [adiffs.osmcha.org](https://adiffs.osmcha.org).

Changeset-aligned adiffs are found at `https://adiffs.osmcha.org/changesets/<changeset_id>.adiff`. For example: https://adiffs.osmcha.org/changesets/160415129.adiff . Changeset-aligned adiffs contain the complete set of changes for a specific changeset, and are useful for visualizing or analyzing a given changeset.

> [!NOTE]
> Augmented diff files are currently available only for changesets created after about 2024-11-26. There are plans to backfill data for older changesets eventually ([see here](https://github.com/OSMCha/osmx-adiff-builder/issues/3)).

The `adiffs.osmcha.org` service is free to use for low-volume noncommercial purposes. If you would like to build an application which depends on the service or make high-volume use of it, please contact `team at openstreetmap dot us` about the Community Projects program or Organizational Membership.

## Installation and dependencies

You can "install" this software by cloning this repository and running the scripts in it directly. They expect the following dependencies to be available:

- [`osm-cli`](https://github.com/jake-low/osm-cli) for locating replication files
- `curl` for downloading replication files
- the `osmx` binary from [OSMExpress](https://github.com/bdon/OSMExpress) for maintaining the local OSM database
- the `osmx-rs` binary from [osmx-rs](https://github.com/jake-low/osmx-rs) for generating per-changeset augmented diffs
- a recent Python (tested on 3.13) for `merge_adiffs.py`
- `xmlstarlet` for pretty-printing merged adiffs
- GNU Make for orchestrating the merge step
- `rclone` for uploading generated adiffs to cloud storage

The scripts in this repository are best treated as a blueprint. If you deploy your own version of osmx-adiff-builder, you will likely want to modify them to customize the behavior for your purposes.

## License

Unless otherwise noted, the files in this repository are marked under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) and dedicated to the public domain.

Data from the OpenStreetMap project is licensed under [ODbL](https://opendatacommons.org/licenses/odbl/). This includes data from [openstreetmap.org](https://www.openstreetmap.org/) and [planet.openstreetmap.org](https://planet.openstreetmap.org/). It also includes data provided by the `adiffs.osmcha.org` service.
