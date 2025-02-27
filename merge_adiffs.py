#!/usr/bin/env python3
"""
Combine multiple augmented diff files into one file. Writes the merged file to stdout.

Usage: merge_adiff.py INPUT_FILE...
"""

import shutil
import sys

input_files = sys.argv[1:]

if not input_files:
    print("Error: no input files to merge", file=sys.stderr)
    exit(2)

# TODO: this would hugely benefit from a happy-path optimization
# that simply copies the input file to the output path if there's
# only one input. That case will be true for the huge majority of
# changesets and avoids having to parse and re-serialize the XML.

# Here's a stab at it (untested):
# if len(input_files) == 1:
#     with open(input_files[0]) as f:
#         shutil.copyfileobj(f, sys.stdout)
#     exit(0)

# Oops, wait, now that we're also embedding the changeset metadata
# into the adiff, we can't use the above shortcut.

from collections import defaultdict
import os.path as path
import xml.etree.ElementTree as ET

changeset = None
actions = []
for file in input_files:
    if path.basename(file) == "metadata.xml":
        metadata = ET.parse(file).getroot()
        changeset = metadata[0]
    else:
        adiff = ET.parse(file).getroot()
        for elem in adiff:
            if elem.tag != "action":
                continue
            actions.append(elem)

# build output file
tree = ET.ElementTree()
root = ET.Element("osm")

root.set("version", "0.6")
root.set("generator", "osmcha")
root.set("copyright", "OpenStreetMap and contributors")
root.set("attribution", "http://www.openstreetmap.org/copyright")
root.set("license", "http://opendatacommons.org/licenses/odbl/1-0/")

if changeset:
    root.append(changeset)

for action in actions:
    root.append(action)

tree._setroot(root)

tree.write(sys.stdout.buffer, encoding="utf-8", xml_declaration=True)
sys.stdout.write('\n')
    

