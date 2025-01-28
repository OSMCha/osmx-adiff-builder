#!/usr/bin/env python3
"""
Split an augmented diff file into multiple files, one per changeset ID contained in the original.

Usage: split_adiff.py ADIFF_FILE OUTPUT_DIRECTORY
"""

import sys
import time
from collections import defaultdict
import xml.etree.ElementTree as ET

adiff_file = sys.argv[1]
output_directory = sys.argv[2]

# map from changeset ID to set of element IDs that belong in that changeset's adiff
# (this will include both elements modified directly in that changeset, and also
# parent elements of those modified elements if present). an element ID is a
# tuple of (str, int) like ("way", 123456).
changesets = defaultdict(set)

start = time.time()
adiff = ET.parse(adiff_file).getroot()
print(f"{time.time() - start:.3f}s to parse input XML")

# collect elements that were directly modified in each changeset. every element
# will get put into at most one changeset (or zero if it wasn't actually modified)
start = time.time()
for elem in adiff:
    if elem.tag != "action":
        continue
    
    action = elem
    if action.get("type") == "create":
        old = None
        new = action[0]
    else:
        old = action[0][0]
        new = action[1][0]

    if old and new and old.get("version") == new.get("version"):
        # this is an unmodified element which is included in the adiff for
        # context. we don't yet know which changeset it's relevant to, so skip
        # it for now.
        continue
    
    changeset = new.get("changeset")
    changesets[changeset].add((new.tag, new.get("id")))

print(f"{time.time() - start:.3f}s to group changed elements by changeset ID")

# collect context elements for each changeset. an element may end up in more
# than one changeset if it happens to have a child that was modified multiple
# times, or several children that were each modified in different changesets
start = time.time()
for elem in adiff:
    if elem.tag != "action":
        continue
    
    action = elem
    if action.get("type") == "create":
        old = None
        new = action[0]
    else:
        old = action[0][0]
        new = action[1][0]

    for elem in filter(lambda e: e is not None, [old, new]):
        if elem.tag == "way":
            way_nodes = set([("node", child.get("ref")) for child in elem if child.tag == "nd"])
            for changeset_id, elem_ids in changesets.items():
                if elem_ids & way_nodes:
                    # print(f"adding context way {elem.get('id')} to changeset {changeset_id}")
                    elem_ids.add(("way", elem.get("id")))

        if elem.tag == "relation":
            rel_members = set([(child.get("type"), child.get("ref")) for child in elem if child.tag == "member"])
            for changeset_id, elem_ids in changesets.items():
                if elem_ids & rel_members:
                    elem_ids.add(("relation", elem.get("id")))

print(f"{time.time() - start:.3f}s to assign context elements to changesets")

# Build a dictionary mapping changeset IDs to lists of XML <action> elements
# borrowed from the input XML tree.
start = time.time()
changeset_elems = defaultdict(list)
for elem in adiff:
    if elem.tag != "action":
        continue
    
    action = elem
    if action.get("type") == "create":
        old = None
        new = action[0]
    else:
        old = action[0][0]
        new = action[1][0]

    id = (new.tag, new.get("id"))

    for changeset_id, elem_ids in changesets.items():
        if id in elem_ids:
            changeset_elems[changeset_id].append(action)

print(f"{time.time() - start:.3f}s to build action lists for each changeset")

# Write output XML documents
start = time.time()
for (changeset, actions) in changeset_elems.items():
    tree = ET.ElementTree()
    root = ET.Element("osm")
    root.set("version", "0.6")
    for action in actions:
        root.append(action)
    tree._setroot(root)
    # print(f"writing split file {output_directory}/{changeset}.adiff")
    with open(f"{output_directory}/{changeset}.adiff", "w") as f:
        tree.write(f, encoding="unicode")
        f.write('\n')
    
print(f"{time.time() - start:.3f}s to write output files")
