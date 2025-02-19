#!/usr/bin/env python3
"""
Generates an augmented diff from an OSC (osmChange) file

See https://wiki.openstreetmap.org/wiki/Overpass_API/Augmented_Diffs
This is intended to be run before the OSC file is applied to the osmx file.

Usage: augmented_adiff.py OSMX_FILE OSC_FILE
"""

# This script is adapted from https://github.com/bdon/OSMExpress/blob/main/python/examples/augmented_diff.py
# 
# Used under the terms of the BSD 2-Clause License, reproduced below
# 
# Copyright 2019 Protomaps.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from collections import namedtuple
from datetime import datetime
import copy
import sys
import time
import xml.etree.ElementTree as ET
import osmx

def eprint(*args, **kwargs):
    print(*args, **kwargs, file=sys.stderr)

if len(sys.argv) < 3:
    eprint("Usage: augmented_diff.py OSMX_FILE OSC_FILE")
    exit(1)

start_time = time.time()

# 1st pass:
# populate the collection of actions
# create dictionary from osm_type/osm_id to action
# e.g. node/12345 > Node()
# FIXME: this assumes the changeset only contains a single action for any element,
# but that's not true for replication changesets. Examples:
# - replication/minute/005/998/765.osc.gz (5998765) contains two changes to way 1260417858,
#   made by the same user (TerraTexGeo) in two different changesets (148485991 and 148485994)
#   about 18 seconds apart
# - replication/minute/005/998/712.osc.gz (5998712) contains two changes to way 1260406351
#   which were made in the same changeset (148485294). the changeset created and then
#   modified the way. it was made using StreetComplete.
Action = namedtuple("Action", ["type", "element"])
actions = {}

osc = ET.parse(sys.argv[2]).getroot()
for block in osc:
    for e in block:
        action_key = e.tag + "/" + e.get("id")
        # Always ensure we're updating to the latest version of an object for the diff
        if action_key in actions:
            newest_version = int(actions[action_key].element.get("version"))
            e_version = int(e.get("version"))
            if e_version < newest_version:
                eprint(
                    "Found element {}, version {} is less than previously visited version {}".format(
                        action_key, e_version, newest_version
                    )
                )
                continue
        actions[action_key] = Action(block.tag, e)


action_list = [v for k, v in actions.items()]

eprint(f"Pass 1: {time.time() - start_time:.3f}s")

env = osmx.Environment(sys.argv[1])
with osmx.Transaction(env) as txn:
    locations = osmx.Locations(txn)
    nodes = osmx.Nodes(txn)
    ways = osmx.Ways(txn)
    relations = osmx.Relations(txn)

    def not_in_db(elem):
        elem_id = int(elem.get("id"))
        if elem.tag == "node":
            return not locations.get(elem_id)
        elif elem.tag == "way":
            return not ways.get(elem_id)
        else:
            return not relations.get(elem_id)

    def get_lat_lon(ref, use_new):
        if use_new and ("node/" + ref in actions):
            node = actions["node/" + ref]
            return (node.element.get("lon"), node.element.get("lat"))
        else:
            ll = locations.get(ref)
            return (str(ll[1]), str(ll[0]))

    def set_old_metadata(elem):
        elem_id = int(elem.get("id"))
        if elem.tag == "node":
            o = nodes.get(elem_id)
        elif elem.tag == "way":
            o = ways.get(elem_id)
        else:
            o = relations.get(elem_id)
        if o:
            with o as o:
                elem.set("version", str(o.metadata.version))
                elem.set("user", str(o.metadata.user))
                elem.set("uid", str(o.metadata.uid))
                # convert to ISO8601 timestamp
                timestamp = o.metadata.timestamp
                formatted = datetime.utcfromtimestamp(timestamp).isoformat()
                elem.set("timestamp", formatted + "Z")
                elem.set("changeset", str(o.metadata.changeset))
        else:
            # tagless nodes
            try:
                version = locations.get(elem_id)[2]
                elem.set("version", str(version))
            except TypeError:
                # If loc is None here, it typically means that a node was created and
                # then deleted within the diff interval. In the future we should
                # remove these operations from the diff entirely.
                eprint("No old loc found for tagless node {}".format(elem_id))
                # elem.set("version", "?")
                
            # elem.set("user", "?")
            # elem.set("uid", "?")
            # elem.set("timestamp", "?")
            # elem.set("changeset", "?")
            

    # 2nd pass
    # create an XML tree of actions with old and new sub-elements

    pass_2_start_time = time.time()

    o = ET.Element("osm")
    o.set("version", "0.6")
    o.set(
        "generator",
        "Overpass API not used, but achavi detects it at the start of string; OSMExpress/python/examples/augmented_diff.py",
    )

    for action in action_list:
        a = ET.SubElement(o, "action")
        a.set("type", action.type)
        old = ET.SubElement(a, "old")
        new = ET.SubElement(a, "new")
        if action.type == "create":
            new.append(action.element)
        elif action.type == "delete":
            # # get the old metadata
            # modified = copy.deepcopy(action.element)
            # set_old_metadata(action.element)
            # old.append(action.element)

            # modified.set("visible", "false")
            # for child in list(modified):
            #     modified.remove(child)
            # # TODO the Geofabrik deleted elements seem to have the old metadata and old version numbers
            # # check if this is true of planet replication files
            # new.append(modified)

            # TODO: dedupe this with "modify" case below (jake)
            # I copy-pasted this because deleted elements also need to be augmented
            # with tags and nodes (not just metadata) in order to be visualized in OSMCha
            obj_id = action.element.get("id")
            prev_version = ET.SubElement(old, action.element.tag)
            prev_version.set("id", obj_id)
            set_old_metadata(prev_version)

            # logically this goes at the end, but do it first so that we can use
            # 'continue' to skip processing below (python doesn't have 'goto out;')
            action.element.set("visible", "false")
            new.append(action.element)
            
            # FIXME: is this right? goal here is to avoid crashing when handling
            # tagless nodes that were deleted...
            if prev_version.get("version") == None or prev_version.get("version") == "?":
                continue
            
            if action.element.tag == "node":
                ll = get_lat_lon(obj_id, False)
                prev_version.set("lon", ll[0])
                prev_version.set("lat", ll[1])
                node = nodes.get(obj_id)
                if node:
                    with node as node:
                        it = iter(node.tags)
                        for t in it:
                            tag = ET.SubElement(prev_version, "tag")
                            tag.set("k", t)
                            tag.set("v", next(it))
            elif action.element.tag == "way":
                way = ways.get(obj_id)
                if not way:
                    # TODO: this seems to be happening (e.g. for way 987234331), might
                    # be a bug in osmx expand?
                    continue
                with way as way:
                    for n in way.nodes:
                        node = ET.SubElement(prev_version, "nd")
                        node.set("ref", str(n))
                    it = iter(way.tags)
                    for t in it:
                        tag = ET.SubElement(prev_version, "tag")
                        tag.set("k", t)
                        tag.set("v", next(it))
            else:
                relation = relations.get(obj_id)
                if not relation:
                    # TODO: this guard avoids errors from the 'with' statement
                    # like "AttributeError: __enter__ -:1.1: Document is empty"
                    continue
                with relation as relation:
                    for m in relation.members:
                        member = ET.SubElement(prev_version, "member")
                        member.set("ref", str(m.ref))
                        member.set("role", m.role)
                        member.set("type", str(m.type))
                    it = iter(relation.tags)
                    for t in it:
                        tag = ET.SubElement(prev_version, "tag")
                        tag.set("k", t)
                        tag.set("v", next(it))

        else:
            obj_id = action.element.get("id")
            if not_in_db(action.element):
                # Typically occurs when:
                #  1. TODO: An element is deleted but then restored later,
                #     which should remain a modify operation. This will be difficult
                #     because objects are not retained in OSMX when deleted in OSM.
                #  2. OK: An element was created and then modified within the diff interval
                eprint(
                    "Could not find {0} {1} in db, changing to create".format(
                        action.element.tag, action.element.get("id")
                    )
                )
                new.append(action.element)
                a.set("type", "create")
            else:
                prev_version = ET.SubElement(old, action.element.tag)
                prev_version.set("id", obj_id)
                set_old_metadata(prev_version)
                if action.element.tag == "node":
                    ll = get_lat_lon(obj_id, False)
                    prev_version.set("lon", ll[0])
                    prev_version.set("lat", ll[1])
                    node = nodes.get(obj_id)
                    if node:
                        with node as node:
                            it = iter(node.tags)
                            for t in it:
                                tag = ET.SubElement(prev_version, "tag")
                                tag.set("k", t)
                                tag.set("v", next(it))
                elif action.element.tag == "way":
                    with ways.get(obj_id) as way:
                        for n in way.nodes:
                            node = ET.SubElement(prev_version, "nd")
                            node.set("ref", str(n))
                        it = iter(way.tags)
                        for t in it:
                            tag = ET.SubElement(prev_version, "tag")
                            tag.set("k", t)
                            tag.set("v", next(it))
                else:
                    with relations.get(obj_id) as relation:
                        for m in relation.members:
                            member = ET.SubElement(prev_version, "member")
                            member.set("ref", str(m.ref))
                            member.set("role", m.role)
                            member.set("type", str(m.type))
                        it = iter(relation.tags)
                        for t in it:
                            tag = ET.SubElement(prev_version, "tag")
                            tag.set("k", t)
                            tag.set("v", next(it))
                new.append(action.element)

    eprint(f"Pass 2: {time.time() - pass_2_start_time:.3f}s")
    
    # 3rd pass
    # Augment the created "old" and "new" elements
    def augment_nd(nd, use_new):
        ll = get_lat_lon(nd.get("ref"), use_new)
        nd.set("lon", ll[0])
        nd.set("lat", ll[1])

    def augment_member(mem, use_new):
        if mem.get("type") == "way":
            ref = mem.get("ref")
            if use_new and ("way/" + ref in actions):
                way = actions["way/" + ref]
                for child in way.element:
                    if child.tag == "nd":
                        ll = get_lat_lon(child.get("ref"), use_new)
                        nd = ET.SubElement(mem, "nd")
                        nd.set("lon", ll[0])
                        nd.set("lat", ll[1])
            else:
                with ways.get(ref) as way:
                    for node_id in way.nodes:
                        ll = get_lat_lon(str(node_id), use_new)
                        nd = ET.SubElement(mem, "nd")
                        nd.set("lon", ll[0])
                        nd.set("lat", ll[1])
        elif mem.get("type") == "node":
            ll = get_lat_lon(mem.get("ref"), use_new)
            mem.set("lon", ll[0])
            mem.set("lat", ll[1])

    def augment(elem, use_new):
        if len(elem) == 0:
            return
        if elem[0].tag == "way":
            for child in elem[0]:
                if child.tag == "nd":
                    augment_nd(child, use_new)
        elif elem[0].tag == "relation":
            for child in elem[0]:
                if child.tag == "member":
                    augment_member(child, use_new)

    pass_3_start_time = time.time()
    
    for elem in o:
        try:
            augment(elem[0], False)
            augment(elem[1], True)
        except (TypeError, AttributeError):
            eprint(
                "Changed {0} {1} is incomplete in db".format(
                    elem[1][0].tag, elem[1][0].get("id")
                )
            )

    eprint(f"Pass 3: {time.time() - pass_3_start_time:.3f}s")
    
    # 4th pass:
    # find changes that propagate to referencing elements:
    # when a node's location changes, that propagates to any ways it belongs to, relations it belongs to
    # and also any relations that the way belongs to
    # when a way's node list changes, it propagates to any relations it belongs to
    pass_4_start_time = time.time()
    
    node_way = osmx.NodeWay(txn)
    node_relation = osmx.NodeRelation(txn)
    way_relation = osmx.WayRelation(txn)

    affected_ways = set()
    affected_relations = set()
    for elem in o:
        if elem.get("type") == "modify":
            if elem[0][0].tag == "node":
                old_loc = (elem[0][0].get("lat"), elem[0][0].get("lon"))
                new_loc = (elem[1][0].get("lat"), elem[1][0].get("lon"))
                if old_loc != new_loc:
                    # TODO: the condition above assumes we only want ways whose
                    # geometry has changed, but maybe we also want to include
                    # ways as context if one of the nodes had a tag-only change?
                    # e.g. adding ford=yes to a node where a road and waterway
                    # are already connected, you'd probably want to see the road
                    # and waterway in OSMCha
                    node_id = elem[0][0].get("id")
                    for rel in node_relation.get(node_id):
                        if "relation/" + str(rel) not in actions:
                            affected_relations.add(rel)
                    for way in node_way.get(node_id):
                        if "way/" + str(way) not in actions:
                            affected_ways.add(way)
                            for rel in way_relation.get(way):
                                if "relation/" + str(rel) not in actions:
                                    affected_relations.add(rel)

            elif elem[0][0].tag == "way":
                old_way = [nd.get("ref") for nd in elem[0][0] if nd.tag == "nd"]
                new_way = [nd.get("ref") for nd in elem[1][0] if nd.tag == "nd"]
                if old_way != new_way:
                    way_id = elem[0][0].get("id")
                    for rel in way_relation.get(way_id):
                        if "relation/" + str(rel) not in actions:
                            affected_relations.add(rel)

    for w in affected_ways:
        a = ET.SubElement(o, "action")
        a.set("type", "modify")
        old = ET.SubElement(a, "old")
        way_element = ET.SubElement(old, "way")
        way_element.set("id", str(w))
        set_old_metadata(way_element)
        with ways.get(w) as way:
            for n in way.nodes:
                node = ET.SubElement(way_element, "nd")
                node.set("ref", str(n))
            it = iter(way.tags)
            for t in it:
                tag = ET.SubElement(way_element, "tag")
                tag.set("k", t)
                tag.set("v", next(it))

        new = ET.SubElement(a, "new")
        new_elem = copy.deepcopy(way_element)
        new.append(new_elem)
        augment(old, False)
        augment(new, True)

    for r in affected_relations:
        old = ET.Element("old")
        relation_element = ET.SubElement(old, "relation")
        relation_element.set("id", str(r))
        set_old_metadata(relation_element)
        with relations.get(r) as relation:
            for m in relation.members:
                member = ET.SubElement(relation_element, "member")
                member.set("ref", str(m.ref))
                member.set("role", m.role)
                member.set("type", str(m.type))
            it = iter(relation.tags)
            for t in it:
                tag = ET.SubElement(relation_element, "tag")
                tag.set("k", t)
                tag.set("v", next(it))

        new_elem = copy.deepcopy(relation_element)
        new = ET.Element("new")
        new.append(new_elem)
        try:
            augment(old, False)
            augment(new, True)
            a = ET.SubElement(o, "action")
            a.set("type", "modify")
            a.append(old)
            a.append(new)
        except (TypeError, AttributeError):
            eprint("Affected relation {0} is incomplete in db".format(r))

    eprint(f"Pass 4: {time.time() - pass_4_start_time:.3f}s")
    
# 5th pass: add bounding boxes
pass_5_start_time = time.time()

class Bounds:
    def __init__(self):
        self.minx = 180
        self.maxx = -180
        self.miny = 90
        self.maxy = -90

    def add(self, x, y):
        if x < self.minx:
            self.minx = x
        if x > self.maxx:
            self.maxx = x
        if y < self.miny:
            self.miny = y
        if y > self.maxy:
            self.maxy = y

    def elem(self):
        e = ET.Element("bounds")
        e.set("minlat", str(self.miny))
        e.set("minlon", str(self.minx))
        e.set("maxlat", str(self.maxy))
        e.set("maxlon", str(self.maxx))
        return e


for child in o:
    if len(child[0]) > 0:
        osm_obj = child[0][0]
        nds = osm_obj.findall(".//nd")
        if nds:
            bounds = Bounds()
            for nd in nds:
                bounds.add(float(nd.get("lon")), float(nd.get("lat")))
            osm_obj.insert(0, bounds.elem())

eprint(f"Pass 5: {time.time() - pass_5_start_time:.3f}s")

# 6th pass
# sort by node, way, relation
# within each, sorted by increasing ID

pass_6_start_time = time.time()

def sort_by_type(x):
    if x[1][0].tag == "node":
        return 1
    elif x[1][0].tag == "way":
        return 2
    return 3


o[:] = sorted(o, key=lambda x: int(x[1][0].get("id")))
o[:] = sorted(o, key=sort_by_type)

eprint(f"Pass 6: {time.time() - pass_6_start_time:.3f}s")

# 7th pass: fix <action type="create"> elements. They're supposed to have a
# single child which is an OSM element, but the code above has instead given
# them a <new> child with an OSM element inside _that_, and refactoring was
# going to be hard so I'm just fixing it at the end here.

pass_7_start_time = time.time()

for child in o:
    if child.tag == "action" and child.get("type") == "create":
        # child[0] is an empty <old> element, child[1] is a <new> element
        # which contains the created OSM element as _its_ only child
        elem = child[1][0]
        child[:] = [elem]

eprint(f"Pass 7: {time.time() - pass_7_start_time:.3f}s")

note = ET.Element("note")
note.text = "The data included in this document is from www.openstreetmap.org. The data is made available under ODbL."
o.insert(0, note)

# pretty print helper
# http://effbot.org/zone/element-lib.htm#prettyprint
def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

write_output_start_time = time.time()

# indent(o)

# ET.ElementTree(o).write(sys.argv[3])
ET.ElementTree(o).write(sys.stdout, encoding="unicode", xml_declaration=True)
sys.stdout.write("\n")  # tree.write does not write a final newline

end_time = time.time()

eprint(f"Pass 8: {end_time - write_output_start_time:.3f}s")
eprint(f"Generated augmented diff in {end_time - start_time:.3f} seconds")
