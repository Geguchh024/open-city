# SPDX-License-Identifier: GPL-3.0-or-later
"""Headless test suite.

    blender -b --factory-startup --python tests/run_tests.py

Exits with a non-zero status when any test fails. The first block runs the plain-Python layers
(settings, layout, styles, placement, ground) without touching the scene; the rest builds the kit, single
buildings and whole towns.
"""

import math
import os
import random
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import open_city  # noqa: E402
from open_city import ground, groups, inputs, kit, layout, lights, materials, params, placement, stage, styles, town  # noqa: E402,E501

open_city.register()

TMP = tempfile.mkdtemp(prefix="oc_tests_")
results = []


def test(fn):
    results.append(fn)
    return fn


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not hasattr(bpy.types.Object, "open_city_town"):
        open_city.register()


def evaluated_mesh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    eo = ob.evaluated_get(dg)
    me = eo.to_mesh()
    return eo, me


def positions(me):
    p = np.zeros(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", p)
    return p.reshape(-1, 3)


def material_faces(me):
    idx = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    return {(m.name if m else None): int((idx == i).sum()) for i, m in enumerate(me.materials)}


def faces_without_material(me):
    idx = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    empty = [i for i, m in enumerate(me.materials) if m is None]
    return int(np.isin(idx, empty).sum()) if len(me.materials) else len(idx)


def face_bounds(me, material):
    """(min, max) corners of all faces with a material."""
    names = [m.name if m else None for m in me.materials]
    if material not in names:
        return None
    k = names.index(material)
    idx = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", idx)
    verts = sorted({v for p in np.nonzero(idx == k)[0] for v in me.polygons[int(p)].vertices})
    co = positions(me)[verts]
    return co.min(0), co.max(0)


def one_building(**values):
    groups.ensure()
    v = params.building_defaults()
    v.update(values)
    ob = town.make_building_object(bpy.context.scene.collection, "B", {k: v[k] for k in params.BY_NAME})
    return ob, inputs.building_modifier(ob)


def add_town(preset="Main Street", **overrides):
    bpy.ops.opencity.add(preset=preset)
    root = bpy.context.active_object
    if overrides:
        open_city.props.write_town(root, overrides)
        town.generate(root)
    return root


# -- plain python -------------------------------------------------------------------------------------------
@test
def settings_tables_are_consistent():
    for table in (params.BUILDING_PARAMS, params.TOWN_PARAMS):
        names = [p[0] for p in table]
        assert len(names) == len(set(names)), "duplicate setting names"
        for name, kind, default, opts in table:
            assert "panel" in opts, name
            if kind in ("int", "float"):
                assert opts["min"] <= default <= opts["max"], f"{name} default out of range"
            if "items" in opts:
                assert opts["max"] == len(opts["items"]) - 1, name
    for pname, preset in params.PRESETS.items():
        assert preset["desc"]
        for k, v in preset["values"].items():
            assert k in params.TOWN_BY_NAME, f"{pname}: unknown setting {k}"
            assert params.clamp_value(k, v, params.TOWN_BY_NAME) == v, f"{pname}: {k}={v} out of range"


@test
def styles_fill_every_building_input():
    rng = random.Random(1)
    town_s = params.town_defaults()
    for role in ("shop", "corner", "row", "house", "landmark"):
        for _ in range(20):
            p = styles.style(rng, role, town_s, 3, 3, styles.Namer(rng))
            missing = set(params.BY_NAME) - set(p)
            assert not missing, (role, missing)
            for name in params.BY_NAME:
                if params.BY_NAME[name][1] in ("int", "float"):
                    assert params.clamp_value(name, p[name]) == p[name], (role, name, p[name])
            assert all(0.0 <= c <= 1.0 for c in p["Wall Color"])


@test
def same_seed_same_plan_other_seed_other_plan():
    v = params.preset_values("Main Street")
    a = layout.plan_town(dict(v, Seed=11))
    b = layout.plan_town(dict(v, Seed=11))
    c = layout.plan_town(dict(v, Seed=12))
    key = [(bd.lot, round(bd.x, 3), round(bd.y, 3), bd.params["Floors"], bd.params.get("Scheme")) for bd in a.buildings]
    assert key == [(bd.lot, round(bd.x, 3), round(bd.y, 3), bd.params["Floors"], bd.params.get("Scheme"))
                   for bd in b.buildings]
    assert key != [(bd.lot, round(bd.x, 3), round(bd.y, 3), bd.params["Floors"], bd.params.get("Scheme"))
                   for bd in c.buildings]


@test
def default_town_is_a_small_town():
    counts = []
    for seed in range(10):
        plan = layout.plan_town(dict(params.preset_values("Main Street"), Seed=seed))
        counts.append(len(plan.buildings))
        floors = [bd.params["Floors"] for bd in plan.buildings]
        # two to four storeys dominate; a landmark may be taller
        assert sum(2 <= f <= 4 for f in floors) >= 0.7 * len(floors), floors
        assert max(floors) <= 6, floors
        roles = {bd.role for bd in plan.buildings}
        assert len(roles) >= 3, roles
        schemes = [bd.params.get("Scheme") for bd in plan.buildings]
        assert len(set(schemes)) >= len(schemes) * 0.4, "too many look-alike facades"
    assert 10 <= sum(counts) / len(counts) <= 20, counts


@test
def buildings_never_overlap_and_stay_in_their_block():
    for name in params.PRESETS:
        for seed in (1, 2, 3):
            s = dict(params.preset_values(name), Seed=seed)
            plan = layout.plan_town(s)
            boxes = [bd.bbox() for bd in plan.buildings]
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    overlap = a[0] < b[1] - 0.05 and b[0] < a[1] - 0.05 and a[2] < b[3] - 0.05 and b[2] < a[3] - 0.05
                    assert not overlap, (name, seed, a, b)
            for blk in plan.blocks:
                ix0, ix1, iy0, iy1 = blk.inner(s["Sidewalk Width"])
                for bd in blk.buildings:
                    x0, x1, y0, y1 = bd.bbox()
                    assert ix0 - 0.01 <= x0 and x1 <= ix1 + 0.01 and iy0 - 0.01 <= y0 and y1 <= iy1 + 0.01, (
                        name, seed, bd.lot)


@test
def rows_fill_frontage_exactly_and_share_party_walls():
    plan = layout.plan_town(dict(params.preset_values("Old Quarter"), Seed=4))
    attached = 0
    for blk in plan.blocks:
        for key, e in blk.edges.items():
            on = sorted((bd for bd in blk.buildings if bd.edge is e), key=lambda bd: bd.a0)
            for a, b in zip(on, on[1:]):
                gap = b.a0 - (a.a0 + a.width)
                # neighbours in a row keep a small gap that clears their cornices and eaves
                assert gap > layout.ROW_GAP - 0.01, f"buildings {gap:.2f} m apart: their trims would collide"
                if gap < layout.ROW_GAP + 0.05:
                    assert a.params["Attached Right"] and b.params["Attached Left"]
                    attached += 1
                else:
                    assert gap > 1.0, f"a sliver gap of {gap:.2f} m"
            for bd in on:
                assert 2.5 <= bd.bay <= 3.6, bd.bay
    assert attached > 10


@test
def props_respect_buildings_doors_and_roads():
    for name in ("Main Street", "Garden Suburb", "Old Quarter"):
        s = dict(params.preset_values(name), Seed=5)
        plan = layout.plan_town(s)
        props = placement.place_props(plan)
        assert {p.key for p in props} <= set(placement.PROP_KEYS)
        boxes = [bd.bbox() for bd in plan.buildings]
        X0, X1, Y0, Y1 = plan.extent
        for p in props:
            if p.key in placement.CARS:
                assert p.z == 0.0
                inside_block = any(b.x0 < p.x < b.x1 and b.y0 < p.y < b.y1 for b in plan.blocks)
                assert not inside_block, f"{p.key} parked on a sidewalk"
                continue
            for x0, x1, y0, y1 in boxes:
                assert not (x0 + 0.05 < p.x < x1 - 0.05 and y0 + 0.05 < p.y < y1 - 0.05), f"{p.key} inside a building"
            if p.key in ("lamp", "bench", "bin", "hydrant", "bus_shelter", "tree_grate", "sandwich_board"):
                on_island = any(b.x0 <= p.x <= b.x1 and b.y0 <= p.y <= b.y1 for b in plan.blocks)
                assert on_island, f"{p.key} off the sidewalk"
        # nothing stands in front of a door on the sidewalk
        for b in plan.blocks:
            for bd in b.buildings:
                if bd.setback > 0.5:
                    continue
                a, _stoop = bd.entrance()
                dx, dy = bd.edge.at(a, -s["Sidewalk Width"] / 2)
                for p in props:
                    if p.key in placement.CARS or p.key in ("hedge", "fence"):
                        continue
                    assert math.hypot(p.x - dx, p.y - dy) > 0.6, f"{p.key} blocks the door of {bd.lot}"


@test
def ground_mesh_is_valid():
    plan = layout.plan_town(params.preset_values("Market Town"))
    placement.place_props(plan)
    m = ground.build(plan)
    assert len(m.faces) == len(m.mats) > 300
    assert all(len(f) >= 3 for f in m.faces)
    assert max(i for f in m.faces for i in f) < len(m.verts)
    assert {"OC Asphalt", "OC Sidewalk", "OC Curb", "OC Grass", "OC Marking", "OC Paving"} <= set(m.mats)
    assert len(m.smooth) == len(m.faces)


def _crosses(p, q, r, s):
    def side(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return side(p, q, r) * side(p, q, s) < 0 and side(r, s, p) * side(r, s, q) < 0


def _to_polyline(pt, loop):
    best = 1e9
    for i in range(len(loop)):
        a, b = loop[i], loop[(i + 1) % len(loop)]
        ab = (b[0] - a[0], b[1] - a[1])
        t = max(0.0, min(1.0, ((pt[0] - a[0]) * ab[0] + (pt[1] - a[1]) * ab[1]) / (ab[0] ** 2 + ab[1] ** 2 or 1)))
        best = min(best, math.hypot(pt[0] - a[0] - ab[0] * t, pt[1] - a[1] - ab[1] * t))
    return best


@test
def traffic_loops_stay_in_their_lanes_and_never_cross():
    for name in params.PRESETS:
        for over in ({}, {"Street Width": 9.0}, {"Parking": 0.0}):
            s = dict(params.preset_values(name), Seed=3, Traffic=1.0, **over)
            plan = layout.plan_town(s)
            props = placement.place_props(plan)
            loops, cars = placement.place_traffic(plan)
            assert len(loops) == len(plan.blocks) + 1 and cars
            X0, X1, Y0, Y1 = plan.extent
            for loop in loops:
                for x, y in loop:
                    assert X0 + 0.9 < x < X1 - 0.9 and Y0 + 0.9 < y < Y1 - 0.9, f"{name}: a lane off the road"
                    for b in plan.blocks:
                        # distance to the kerb: a rectangle with rounded corners
                        r = layout.CORNER_RADIUS
                        dx = max(b.x0 + r - x, 0.0, x - b.x1 + r)
                        dy = max(b.y0 + r - y, 0.0, y - b.y1 + r)
                        assert math.hypot(dx, dy) - r > 0.88, f"{name}: a lane over a kerb"   # half a car
            segs = [[(lp[i], lp[(i + 1) % len(lp)]) for i in range(len(lp))] for lp in loops]
            for i in range(len(segs)):
                for j in range(i + 1, len(segs)):
                    assert not any(_crosses(*a, *b) for a in segs[i] for b in segs[j]), f"{name}: loops cross"
            # parked cars sit beside the lanes, never in them
            for p in props:
                if p.key in placement.CARS:
                    assert min(_to_polyline((p.x, p.y), lp) for lp in loops) > 1.95, f"{name}: parked in a lane"
            # cars on one loop keep their distance
            for i, loop in enumerate(loops):
                on = sorted(c.phase for c in cars if c.route == i)
                if len(on) > 1:
                    length = placement.loop_length(loop)
                    assert all((b - a) * length > 6.0 for a, b in zip(on, on[1:] + [on[0] + 1.0])), "cars too close"


@test
def the_countryside_closes_off_the_town():
    for kind in (0, 1, 2):
        s = dict(params.preset_values("Main Street"), Seed=4, Surroundings=kind)
        plan = layout.plan_town(s)
        props = placement.place_props(plan)
        m = ground.build(plan)
        ox0, ox1, oy0, oy1 = ground.town_edge(plan)
        xs = [v[0] for v in m.verts]
        assert min(xs) < ox0 - ground.FAR + 1 and max(xs) > ox1 + ground.FAR - 1, "the land ends near town"
        assert ground.terrain_height(plan, ox0, (oy0 + oy1) / 2) == layout.CURB
        far = ground.terrain_height(plan, ox0 - 90.0, 0.0)
        assert (far > 12.0) if kind == 2 else (far == layout.CURB)
        woods = [p for p in props if ground.outside(plan, p.x, p.y) > 1.0]
        assert (len(woods) > 300) if kind else not woods
        for p in woods:
            assert abs(p.z - ground.terrain_height(plan, p.x, p.y)) < 0.2, "a tree floating over the hill"
    s = dict(params.preset_values("Main Street"), Seed=4, **{"Diorama Base": True})
    m = ground.build(layout.plan_town(s))
    assert "OC Base" in m.mats and max(abs(v[0]) for v in m.verts) < 200


# -- blender --------------------------------------------------------------------------------------------------
@test
def register_cycle():
    open_city.unregister()
    open_city.register()
    open_city.unregister()
    open_city.register()
    assert hasattr(bpy.types.Object, "open_city") and hasattr(bpy.types.Object, "open_city_town")


@test
def every_material_is_a_node_material():
    reset()
    materials.ensure_all()
    for name in materials.NAMES:
        m = bpy.data.materials[name]
        assert m.node_tree and any(n.type == "OUTPUT_MATERIAL" for n in m.node_tree.nodes), name


@test
def every_kit_module_builds_geometry():
    reset()
    groups.ensure()
    for name in kit.group_names():
        if name in (kit.SCATTER, kit.TRAFFIC, "OC Kit CBox", "OC Kit Empty"):
            continue
        tree = bpy.data.node_groups[name]
        wrap = bpy.data.node_groups.new("w", "GeometryNodeTree")
        wrap.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        n = wrap.nodes.new("GeometryNodeGroup")
        n.node_tree = tree
        wrap.links.new(n.outputs[0], wrap.nodes.new("NodeGroupOutput").inputs[0])
        ob = bpy.data.objects.new("m", bpy.data.meshes.new("m"))
        bpy.context.scene.collection.objects.link(ob)
        ob.modifiers.new("g", "NODES").node_group = wrap
        eo, me = evaluated_mesh(ob)
        assert len(me.polygons) > 4, name
        assert faces_without_material(me) == 0, f"{name} has faces without a material"
        eo.to_mesh_clear()
        bpy.data.objects.remove(ob)
        bpy.data.node_groups.remove(wrap)


@test
def a_building_has_every_part():
    reset()
    ob, mod = one_building(**{"Ground Use": 1, "Shop Name": "BAKERY", "Shutters": True, "Flower Boxes": 1.0,
                              "Balconies": 0.6, "Corner Style": 1})
    eo, me = evaluated_mesh(ob)
    mats = material_faces(me)
    for m in ("OC Wall", "OC Trim", "OC Glass", "OC Accent", "OC Awning", "OC Stone", "OC Sign Text",
              "OC Roof Flat", "OC Shutter", "OC Flowers", "OC Leaves"):
        assert mats.get(m, 0) > 0, f"no {m}"
    assert faces_without_material(me) == 0
    for name in ("oc_wall", "oc_trim", "oc_accent", "oc_roof", "oc_awning", "oc_gu", "oc_gv", "oc_slot"):
        assert name in me.attributes, name
    eo.to_mesh_clear()


@test
def width_and_floors_add_modules_instead_of_stretching():
    """More bays add whole bays; more floors add whole floors; the windows stay the same size."""
    reset()
    base = {"Bays Wide": 3, "Floors": 3, "Ground Use": 0, "Balconies": 0.0, "Flower Boxes": 0.0,
            "Shutters": False, "Corner Style": 0, "Roof Type": 1, "Chimneys": 0, "Rooftop Units": False}
    ob, mod = one_building(**base)

    def measure():
        eo, me = evaluated_mesh(ob)
        lo, hi = face_bounds(me, "OC Wall")
        glass = material_faces(me)["OC Glass"]
        eo.to_mesh_clear()
        return hi - lo, glass

    size3, glass3 = measure()
    inputs.set(mod, "Bays Wide", 5)
    size5, glass5 = measure()
    bw = inputs.get(mod, "Bay Width")
    assert abs((size5[0] - size3[0]) - 2 * bw) < 1e-3, (size3, size5)
    assert glass5 > glass3 * 1.2, "new bays get new windows"
    inputs.set(mod, "Floors", 5)
    size5b, glass5b = measure()
    fh = inputs.get(mod, "Floor Height")
    assert abs((size5b[2] - size5[2]) - 2 * fh) < 0.05, (size5, size5b)
    assert glass5b > glass5 * 1.3

    # one window measured in a narrow and in a wide building is the same size
    def window_size(bays):
        reset()
        b, m = one_building(**dict(base, **{"Bays Wide": bays, "Bays Deep": 1, "Floors": 2}))
        eo, me = evaluated_mesh(b)
        names = [x.name if x else None for x in me.materials]
        k = names.index("OC Glass")
        top_of_ground = inputs.get(m, "Plinth Height") + inputs.get(m, "Ground Height")
        sizes = set()
        for p in me.polygons:
            # the front panes of the upper floor
            if (p.material_index == k and p.normal.y < -0.9 and p.center.z > top_of_ground
                    and p.center.y < 0.0 and p.area > 0.05):
                co = np.array([me.vertices[v].co[:] for v in p.vertices])
                sizes.add(tuple(np.round(co.max(0) - co.min(0), 3)))
        eo.to_mesh_clear()
        return sizes
    narrow, wide = window_size(2), window_size(6)
    assert narrow and narrow == wide, ("window panes change size with the building width", narrow, wide)


@test
def every_roof_tower_window_and_wall_builds():
    reset()
    ob, mod = one_building()
    for name, count in (("Roof Type", 5), ("Tower", 3), ("Window Style", 3), ("Wall Kind", 4),
                        ("Balcony Style", 3), ("Corner Style", 3), ("Awnings", 3), ("Corner Side", 3)):
        for v in range(count):
            inputs.set(mod, name, v)
            if name == "Awnings":
                inputs.set(mod, "Ground Use", 1)
            eo, me = evaluated_mesh(ob)
            assert len(me.polygons) > 1000, (name, v)
            assert faces_without_material(me) == 0, (name, v)
            assert np.isfinite(positions(me)).all(), (name, v)
            eo.to_mesh_clear()
        inputs.set(mod, name, params.BY_NAME[name][2])
    inputs.set(mod, "Gable Front", True)
    inputs.set(mod, "Roof Type", 2)
    eo, me = evaluated_mesh(ob)
    assert material_faces(me).get("OC Roof Tiles", 0) > 0
    eo.to_mesh_clear()


@test
def attached_sides_have_no_windows():
    reset()
    ob, mod = one_building(**{"Bays Deep": 4, "Attached Left": True, "Attached Right": True, "Corner Style": 0,
                              "Roof Type": 1, "Chimneys": 0})
    eo, me = evaluated_mesh(ob)
    names = [x.name if x else None for x in me.materials]
    k = names.index("OC Glass")
    # panes facing sideways (not the thin edges of the front panes)
    side = sum(1 for p in me.polygons if p.material_index == k and abs(p.normal.x) > 0.9 and p.area > 0.05)
    assert side == 0, f"{side} side-facing glass faces on a party wall"
    eo.to_mesh_clear()


@test
def add_town_makes_a_complete_town():
    reset()
    t = time.time()
    root = add_town("Main Street")
    dt = time.time() - t
    kids = root.children
    roles = [o.get(town.ROLE) for o in kids]
    plan = layout.plan_town(town.settings_of(root))
    assert roles.count("ground") == 1 and roles.count("props") == 3
    assert roles.count("traffic") == 1 and roles.count("routes") == 1
    assert roles.count("building") == len(plan.buildings) >= 8
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    faces = 0
    for o in kids:
        if o.get(town.ROLE) == "building":
            eo = o.evaluated_get(dg)
            me = eo.to_mesh()
            faces += len(me.polygons)
            assert faces_without_material(me) == 0, o.name
            eo.to_mesh_clear()
    inst = sum(1 for i in dg.object_instances if i.is_instance)
    print(f"    {len(plan.buildings)} buildings, {faces:,} building faces, {inst} prop instances, {dt:.1f}s")
    assert faces > 50000 and inst > 200


@test
def town_settings_regenerate_live_and_keep_names():
    reset()
    root = add_town("Main Street")
    before = sorted(o.name for o in root.children if o.get(town.ROLE) == "building")
    root.open_city_town.density = 0.3
    after = [o for o in root.children if o.get(town.ROLE) == "building"]
    assert len(after) != len(before) or sorted(o.name for o in after) != before
    root.open_city_town.live_update = False
    n = len(root.children)
    root.open_city_town.blocks_x = 4
    assert len(root.children) == n, "nothing regenerates with Live Update off"
    bpy.ops.opencity.regenerate()
    assert len(root.children) > n


@test
def seeds_reproduce_towns():
    reset()
    root = add_town("Main Street", Seed=21)

    def snapshot():
        return sorted((o.get(town.LOT), tuple(round(c, 3) for c in o.location), inputs.get(
            inputs.building_modifier(o), "Floors")) for o in root.children if o.get(town.ROLE) == "building")
    a = snapshot()
    open_city.props.write_town(root, {"Seed": 22})
    town.generate(root)
    b = snapshot()
    open_city.props.write_town(root, {"Seed": 21})
    town.generate(root)
    c = snapshot()
    assert a == c and a != b


@test
def locked_and_rerolled_buildings_keep_their_edits():
    reset()
    root = add_town("Main Street", Seed=3)
    ob = next(o for o in root.children if o.get(town.ROLE) == "building")
    mod = inputs.building_modifier(ob)
    bays = inputs.get(mod, "Bays Wide")
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.opencity.reroll()
    assert ob.get(town.LOCK), "re-rolled buildings are locked"
    assert inputs.get(mod, "Bays Wide") == bays, "re-rolling keeps the footprint"
    ob.open_city.floors = 7
    name = ob.name
    bpy.context.view_layer.objects.active = root
    bpy.ops.opencity.regenerate()
    ob = bpy.data.objects[name]
    assert inputs.get(inputs.building_modifier(ob), "Floors") == 7, "a locked building survives regeneration"


@test
def building_properties_follow_the_modifier():
    reset()
    ob, mod = one_building()
    bp = ob.open_city
    bp.floors = 5
    assert inputs.get(mod, "Floors") == 5
    inputs.set(mod, "Bays Wide", 4)
    assert bp.bays_wide == 4
    bp.roof_type = "4"
    assert inputs.get(mod, "Roof Type") == 4
    bp.shop_name = "CAFE"
    assert inputs.get(mod, "Shop Name") == "CAFE"
    bp.wall_color = (0.1, 0.2, 0.3, 1.0)
    assert abs(inputs.get(mod, "Wall Color")[2] - 0.3) < 1e-6
    bp.floors = 999
    assert bp.floors <= 10


class FakeLayout:
    """Stands in for a UI layout: checks every property a panel draws actually exists."""

    def __init__(self, log):
        self.log = log
        self.alert = False
        self.scale_y = 1.0

    def prop(self, data, name, **_kw):
        assert hasattr(data, name), f"panel draws a missing property {name!r}"
        getattr(data, name)
        self.log.append(name)

    def operator(self, idname, **_kw):
        cat, op = idname.split(".")
        assert hasattr(getattr(bpy.ops, cat), op), idname
        return type("Op", (), {})()

    def operator_menu_enum(self, idname, prop, **_kw):
        self.operator(idname)

    def __getattr__(self, _name):
        return lambda *a, **k: FakeLayout(self.log)


@test
def ui_panels_draw_for_towns_and_buildings():
    reset()
    root = add_town("Main Street", Seed=6)
    bld = next(o for o in root.children if o.get(town.ROLE) == "building")
    from open_city import ui
    for active in (None, root, bld):
        ctx = type("Ctx", (), {"active_object": active, "selected_objects": [active] if active else [],
                               "scene": bpy.context.scene})()
        log = []
        for cls in ui.CLASSES:
            if not issubclass(cls, bpy.types.Panel):
                continue
            if hasattr(cls, "poll") and not cls.poll(ctx):
                continue
            panel = type("P", (), {"layout": FakeLayout(log)})()
            cls.draw(panel, ctx)
        if active is root:
            assert "density" in log and "street_width" in log
        if active is bld:
            assert "floors" in log and "roof_type" in log and "wall_color" in log


@test
def make_real_bakes_the_town():
    reset()
    root = add_town("Garden Suburb", Seed=2)
    bpy.context.view_layer.objects.active = root
    bpy.ops.opencity.make_real()
    baked = bpy.context.active_object
    assert baked is not root and baked.type == "MESH" and not baked.modifiers
    assert len(baked.data.polygons) > 50000
    assert all(baked.data.materials) and len(baked.data.materials) >= 15
    assert root.hide_get()


@test
def rebuild_keeps_every_building_setting():
    reset()
    root = add_town("Main Street", Seed=8)
    obs = [o for o in root.children if o.get(town.ROLE) == "building"]
    before = {o.name: inputs.read_all(inputs.building_modifier(o)) for o in obs}
    bpy.ops.opencity.rebuild()
    for o in obs:
        after = inputs.read_all(inputs.building_modifier(o))
        for k, v in before[o.name].items():
            if isinstance(v, tuple):
                assert np.allclose(v, after[k]), (o.name, k)
            elif isinstance(v, float):
                assert abs(v - after[k]) < 1e-6, (o.name, k)
            else:
                assert v == after[k], (o.name, k, v, after[k])


@test
def the_file_works_without_the_addon():
    reset()
    root = add_town("Main Street", Seed=9)
    name = root.name
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    faces = sum(len(o.evaluated_get(dg).data.polygons) for o in root.children if o.type == "MESH")
    inst = sum(1 for i in dg.object_instances if i.is_instance)
    path = os.path.join(TMP, "town.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    open_city.unregister()
    bpy.ops.wm.open_mainfile(filepath=path)
    root = bpy.data.objects[name]
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    faces2 = sum(len(o.evaluated_get(dg).data.polygons) for o in root.children if o.type == "MESH")
    inst2 = sum(1 for i in dg.object_instances if i.is_instance)
    assert faces == faces2 and inst == inst2, (faces, faces2, inst, inst2)
    open_city.register()


@test
def editing_one_building_is_fast():
    reset()
    root = add_town("Main Street", Seed=4)
    ob = max((o for o in root.children if o.get(town.ROLE) == "building"),
             key=lambda o: inputs.get(inputs.building_modifier(o), "Bays Wide"))
    mod = inputs.building_modifier(ob)
    eo, me = evaluated_mesh(ob)
    eo.to_mesh_clear()
    t = time.time()
    inputs.set(mod, "Floors", inputs.get(mod, "Floors") + 1)
    eo, me = evaluated_mesh(ob)
    eo.to_mesh_clear()
    dt = time.time() - t
    t = time.time()
    town.generate(root)
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    dt2 = time.time() - t
    print(f"    one building re-evaluates in {dt * 1000:.0f} ms; the whole town regenerates in {dt2:.2f}s")
    assert dt < 2.0 and dt2 < 10.0


@test
def traffic_drives_with_the_clock():
    reset()
    root = add_town("Main Street")
    root.open_city_town.traffic = 0.8
    traffic = next(o for o in root.children if o.get(town.ROLE) == "traffic")
    n = len(traffic.data.vertices)
    assert n > 5

    def cars():
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        return sorted(tuple(round(v, 2) for v in i.matrix_world.translation) for i in dg.object_instances
                      if i.is_instance and i.parent and i.parent.original == traffic and i.object.type == "MESH")
    sc = bpy.context.scene
    sc.frame_set(1)
    a = cars()
    sc.frame_set(40)
    b = cars()
    assert len(a) == len(b) == n
    assert a != b, "the traffic stands still"
    root.open_city_town.traffic = 0.0
    assert len(traffic.data.vertices) == 0


@test
def night_lights_the_town_and_day_turns_it_off():
    reset()
    add_town("Main Street")
    sc = bpy.context.scene
    stage.setup(sc, night=True)
    assert lights.night_amount() == 1.0
    assert all(lights.light(n).data.energy > 0 for n in lights.SPECS)
    assert sc.view_settings.view_transform == "AgX"
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    lamps = sum(1 for i in dg.object_instances if i.is_instance and i.object.type == "LIGHT")
    assert lamps > 20, lamps
    bpy.ops.opencity.stage(night=False)
    assert lights.night_amount() == 0.0
    assert all(lights.light(n).data.energy == 0 for n in lights.SPECS)
    assert getattr(sc, "compositing_node_group", None) is None


def main():
    failed = 0
    for fn in results:
        t = time.time()
        try:
            fn()
            print(f"PASS  {fn.__name__}  ({time.time() - t:.1f}s)")
        except Exception:
            failed += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(results) - failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


main()
