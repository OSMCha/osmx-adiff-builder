#!/usr/bin/env python3
"""
Split an augmented diff file into multiple files, one per changeset ID contained in the original.

Usage: split_adiff.py ADIFF_FILE OUTPUT_DIRECTORY
"""

import sys
import time
from collections import defaultdict

from lxml import etree as ET


def main():
    adiff_file = sys.argv[1]
    output_directory = sys.argv[2]
    # Maps: changeset_id -> set of (type, id) tuples
    changesets = defaultdict(set)
    # Reverse index: (type, id) -> set of changeset_ids (for O(1) lookup)
    elem_to_changesets = defaultdict(set)

    start = time.time()

    # Pass 1: identify modified elements and their changesets
    context = ET.iterparse(adiff_file, events=("end",), tag="action")
    for _, action in context:
        action_type = action.get("type")
        if action_type == "create":
            new = action[0]
            old = None
        else:
            old = action[0][0]
            new = action[1][0]

        # Skip context elements (unmodified)
        if old is not None and new is not None and old.get("version") == new.get("version"):
            action.clear()
            continue

        changeset = new.get("changeset")
        elem_id = (new.tag, new.get("id"))
        changesets[changeset].add(elem_id)
        elem_to_changesets[elem_id].add(changeset)

        action.clear()

    del context
    print(f"{time.time() - start:.3f}s to identify modified elements (pass 1)")

    # Pass 2: collect context elements using the reverse index
    start = time.time()

    context = ET.iterparse(adiff_file, events=("end",), tag="action")
    for _, action in context:
        action_type = action.get("type")
        if action_type == "create":
            new = action[0]
            old = None
        else:
            old = action[0][0]
            new = action[1][0]

        for elem in (old, new):
            if elem is None:
                continue

            elem_tag = elem.tag
            if elem_tag == "way":
                elem_id_str = elem.get("id")
                for child in elem:
                    if child.tag == "nd":
                        node_id = ("node", child.get("ref"))
                        cs_set = elem_to_changesets.get(node_id)
                        if cs_set:
                            way_id = ("way", elem_id_str)
                            for cs_id in cs_set:
                                changesets[cs_id].add(way_id)
                                elem_to_changesets[way_id].add(cs_id)

            elif elem_tag == "relation":
                elem_id_str = elem.get("id")
                for child in elem:
                    if child.tag == "member":
                        member_id = (child.get("type"), child.get("ref"))
                        cs_set = elem_to_changesets.get(member_id)
                        if cs_set:
                            rel_id = ("relation", elem_id_str)
                            for cs_id in cs_set:
                                changesets[cs_id].add(rel_id)
                                elem_to_changesets[rel_id].add(cs_id)

        action.clear()

    del context
    print(f"{time.time() - start:.3f}s to assign context elements (pass 2)")

    # Pass 3: write output files incrementally
    start = time.time()

    output_files = {}
    actions_count = 0

    context = ET.iterparse(adiff_file, events=("end",), tag="action")
    for _, action in context:
        action_type = action.get("type")
        if action_type == "create":
            new = action[0]
        else:
            new = action[1][0]

        elem_id = (new.tag, new.get("id"))
        cs_set = elem_to_changesets.get(elem_id)

        if cs_set:
            action_xml = ET.tostring(action, encoding="unicode")

            for cs_id in cs_set:
                if cs_id not in output_files:
                    output_files[cs_id] = open(f"{output_directory}/{cs_id}.adiff", "w")
                    output_files[cs_id].write('<?xml version="1.0" encoding="UTF-8"?>\n<osm version="0.6">\n')

                output_files[cs_id].write(action_xml)
                output_files[cs_id].write("\n")
                actions_count += 1

        action.clear()

    del context

    # Close all files
    for f in output_files.values():
        f.write("</osm>\n")
        f.close()

    print(f"{time.time() - start:.3f}s to write {len(output_files)} files, {actions_count} actions (pass 3)")


if __name__ == "__main__":
    main()
