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
2. Run [`augmented_diff.py`](./augmented_diff.py) to construct an augmented diff from the replication file and the (stale) OSMX database. The replication file contains the new version of every directly modified element. The OSMX database contains the old versions. The database also makes it possible to efficiently fetch related elements (e.g. ways to which a modified node belongs, or members of a modified relation) and include them in the augmented diff.
3. Apply the changes from the replication file to the OSMX database using the `osmx update` command.

The steps above are handled by [`update.sh`](./update.sh), which is run every minute as a cron job.

In reality the process is a bit more complex. Replication files contain changes from many different changesets, and sometimes a single changeset's changes are split across several replication files.

To address this, the _replication-aligned adiff_ produced in step 2 must be split into adiff files for each changeset using [`split_adiff.py`](./split_adiff.py). This splits the changes into one file per changeset. These files are then placed in separate directories, one per changeset. If another replication file contains more changes for the same changeset, a second file will be placed in that changeset's directory.

To merge changes from separate replication files together, [`merge_adiffs.py`](./merge_adiffs.py) is used. This merges all of the augmented diff files in a changeset directory together, generating a single, final _changeset-aligned adiff_. This script must be re-run if additional changes arrive in a future replication file which belong to this changeset. To avoid needlessly re-running this script when no new changes have been added, merging is handled through [`merge.mk`](./merge.mk) (a Makefile script) which skips any output (merged) adiff files whose inputs haven't changed.

The entire splitting and merging workflow is orchestrated by [`process.sh`](./process.sh).

Output files from the merge process can be copied to another location or uploaded to Object Storage ([adiffs.osmcha.org](https://adiffs.osmcha.org) uses Cloudflare R2). The data for each changeset is kept locally for a while, in case a replication file is published that has additional changes for this changeset (if this happens, a new version of the changeset will be uploaded, overwriting the old one). After a while, it's safe to assume that a changeset is complete (openstreetmap.org automatically closes changesets after 24h). The [`gc.sh`](./gc.sh) script deletes old files periodically so that they don't fill up the storage on the local machine.

The state of the system described above is managed through the filesystem. Replication files are downloaded into `stage-data/replication/minute/` by `update.sh`, and then deleted by `process.sh` once they're no longer needed. Split files are placed in `stage-data/split-adiffs/<changeset_id>/`, so that `merge.mk` knows which sets of split files have changed and can re-merge them. The final merged files are moved to `bucket-data/changesets/<changesed_id>.adiff`, where they are uploaded to cloud storage and then deleted.

## [adiffs.osmcha.org](https://adiffs.osmcha.org)

The augmented diffs produced by this process are available over HTTPS at [adiffs.osmcha.org](https://adiffs.osmcha.org).

Changeset-aligned adiffs are found at `https://adiffs.osmcha.org/changesets/<changeset_id>.adiff`. For example: https://adiffs.osmcha.org/changesets/160415129.adiff . Changeset-aligned adiffs contain the complete set of changes for a specific changeset, and are useful for visualizing or analyzing a given changeset.

Replication-aligned adiffs are also available at `https://adiffs.osmcha.org/replication/minute/<seqno.adiff>`. For example: https://adiffs.osmcha.org/replication/minute/6429815.adiff (which corresponds to https://planet.openstreetmap.org/replication/minute/006/449/815.osc.gz). Replication-aligned adiffs contain changes from many different changesets which occurred during the same minute, and may not contain complete changesets, so they are likely to only be useful for specialized purposes.

> [!NOTE]
> Augmented diff files are currently available only for changesets created after about 2024-11-26. There are plans to backfill data for older changesets eventually ([see here](https://github.com/OSMCha/osmx-adiff-builder/issues/3)).

The `adiffs.osmcha.org` service is free to use for low-volume noncommercial purposes. If you would like to build an application which depends on the service or make high-volume use of it, please contact `team at openstreetmap dot us` about the Community Projects program or Organizational Membership.

## License

Unless otherwise noted, the files in this repository are marked under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) and dedicated to the public domain.

Data from the OpenStreetMap project is licensed under [ODbL](https://opendatacommons.org/licenses/odbl/). This includes data from [openstreetmap.org](https://www.openstreetmap.org/) and [planet.openstreetmap.org](https://planet.openstreetmap.org/). It also includes data provided by the `adiffs.osmcha.org` service.
