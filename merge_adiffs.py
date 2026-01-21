#!/usr/bin/env python3
"""
Combine multiple augmented diff files into one file. Writes the merged file to stdout.

Usage: merge_adiff.py INPUT_FILE...

Optimized to use streaming XML parsing (lxml iterparse) to minimize memory usage.
"""

import signal
import sys
import os.path as path

from lxml import etree as ET

# Handle broken pipe gracefully (e.g., when piped to head or gzip fails)
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

input_files = sys.argv[1:]

if not input_files:
    print("Error: no input files to merge", file=sys.stderr)
    exit(2)

# Separate metadata file from adiff files
metadata_file = None
adiff_files = []

for file in input_files:
    if path.basename(file) == "metadata.xml":
        metadata_file = file
    else:
        adiff_files.append(file)

# Write XML header
sys.stdout.buffer.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
sys.stdout.buffer.write(b'<osm version="0.6" generator="osmcha" ')
sys.stdout.buffer.write(b'copyright="OpenStreetMap and contributors" ')
sys.stdout.buffer.write(b'attribution="https://www.openhistoricalmap.org/copyright" ')
sys.stdout.buffer.write(b'license="https://creativecommons.org/publicdomain/zero/1.0/">\n')

# Write changeset metadata if present (usually small, safe to parse fully)
if metadata_file:
    try:
        metadata = ET.parse(metadata_file).getroot()
        changeset = metadata[0]
        sys.stdout.buffer.write(ET.tostring(changeset, encoding="utf-8"))
        sys.stdout.buffer.write(b"\n")
        del metadata, changeset
    except Exception as e:
        print(f"Warning: failed to parse metadata file: {e}", file=sys.stderr)

# Stream actions from each adiff file
for adiff_file in adiff_files:
    try:
        context = ET.iterparse(adiff_file, events=("end",), tag="action")
        for _, action in context:
            sys.stdout.buffer.write(ET.tostring(action, encoding="utf-8"))
            sys.stdout.buffer.write(b"\n")
            # Clear element AND remove from parent to free memory completely
            action.clear()
            while action.getprevious() is not None:
                del action.getparent()[0]
        del context
    except Exception as e:
        print(f"Warning: failed to parse adiff file {adiff_file}: {e}", file=sys.stderr)

# Close the root element
sys.stdout.buffer.write(b"</osm>\n")
