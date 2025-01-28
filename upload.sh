#!/bin/sh

# Upload bucket-data/ to R2, adding new files and possibly overwriting those
# that have been changed locally (occurs when a changeset's changes are split
# across multiple replication files)

# The headers being set here tell Cloudflare that the content we're uploading
# is XML that is already gzip-compressed. Storing compressed content reduces our
# storage costs. Cloudflare automatically handles serving the content correctly:
# if a client sends an Accept-Encoding: gzip header, they'll get compressed
# content, and if not they'll get plaintext content (which Cloudflare's servers
# decompress on the fly).

# You'll need to provide your own rclone.conf file containing credentials to
# your Cloudflare R2 bucket.

rclone --config rclone.conf copy --progress \
  --header-upload "Content-Type: application/xml" \
  --header-upload "Content-Encoding: gzip"\
  bucket-data r2:osm-augmented-diffs

