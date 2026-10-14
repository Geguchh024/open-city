# SPDX-License-Identifier: GPL-3.0-or-later
"""Putting a town in the scene.

A town is an empty (the root, which holds the town settings) with generated children:

    Ground              roads, kerbed islands, lawns, paths, markings and the countryside (a plain mesh)
    one object per building, each with its own `OC Building` modifier, so any building can be
                        edited, re-rolled or locked on its own
    Street Furniture, Greenery, Cars
                        point clouds instanced through `OC Scatter`
    Traffic             cars driving round `Traffic Routes` (hidden curves), through `OC Traffic`

Regenerating reuses objects by lot, so a building keeps its name and selection, and skips buildings
that are locked.
"""


import bpy

from . import groups, ground, inputs, layout, params, placement
from .layout import CURB

TOWN = "oc_town"          # on the root
ROLE = "oc_role"          # on generated children: "ground", "building", "props"
LOT = "oc_lot"
LOCK = "oc_locked"
BUILD_ROLE = "oc_building_role"
LAYERS = ("Street Furniture", "Greenery", "Cars")


def town_root(obj):
    """The town an object belongs to (itself, if it is a town root), or None."""
    while obj is not None:
        if obj.get(TOWN):
            return obj
        obj = obj.parent
    return None


def settings_of(root):
    """The town settings stored on a root, by name."""
    from .props import read_town
    tp = root.open_city_town
    out = params.town_defaults()
    for name, _kind, _d, _o in params.TOWN_PARAMS:
        out[name] = read_town(tp, name)
    return out


def new_town(context, settings, name="Town"):
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 4.0
    root[TOWN] = True
    context.collection.objects.link(root)
    root.location = context.scene.cursor.location
    from .props import write_town
    write_town(root, settings)
    generate(root)
    return root


def _children(root, role):
    return [o for o in root.children if o.get(ROLE) == role]


def _child_mesh(root, role, name, layer=None):
    for o in _children(root, role):
        if layer is None or o.get("oc_layer") == layer:
            return o
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    for c in root.users_collection:
        c.objects.link(ob)
    ob.parent = root
    ob[ROLE] = role
    if layer:
        ob["oc_layer"] = layer
    return ob


def generate(root, settings=None):
    """Plan the town and bring the scene in line with the plan. Returns the plan."""
    groups.ensure()
    s = settings or settings_of(root)
    plan = layout.plan_town(s)
    props = placement.place_props(plan)
    _ground(root, plan)
    _buildings(root, plan)
    _props(root, props)
    _traffic(root, *placement.place_traffic(plan))
    root["oc_summary"] = plan.summary()
    return plan


def _ground(root, plan):
    ob = _child_mesh(root, "ground", f"{root.name} Ground")
    data = ground.build(plan)
    me = ob.data
    me.clear_geometry()
    me.materials.clear()
    names = sorted(set(data.mats))
    from . import materials
    for n in names:
        me.materials.append(materials.get(n))
    me.from_pydata(data.verts, [], data.faces)
    index = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [index[n] for n in data.mats])
    me.polygons.foreach_set("use_smooth", data.smooth)
    me.update()


def building_name(bd):
    shop = bd.params.get("Shop Name")
    if bd.role == "landmark":
        base = "Town Hall" if bd.params.get("Tower") == 2 else "Corner Tower"
    elif shop:
        base = shop.title()
    else:
        base = {"house": "House", "row": "Townhouse", "corner": "Corner House", "shop": "Shop"}.get(bd.role, "Building")
    return f"{base} {bd.lot}"


def make_building_object(collection, name, values, parent=None):
    """A mesh object carrying an `OC Building` modifier set to `values`."""
    tree = groups.ensure()
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    mod = ob.modifiers.new(inputs.MODIFIER_NAME, "NODES")
    mod.node_group = tree
    inputs.apply(mod, values)
    ob[ROLE] = "building"
    return ob


def _buildings(root, plan):
    existing = {}
    for o in _children(root, "building"):
        existing.setdefault(o.get(LOT), o)
    coll = root.users_collection[0]
    keep = set()
    for bd in plan.buildings:
        ob = existing.get(bd.lot)
        if ob is not None and ob.get(LOCK):
            keep.add(ob.name)
            continue
        values = bd.module_inputs()
        if ob is None or inputs.building_modifier(ob) is None:
            ob = make_building_object(coll, building_name(bd), values, parent=root)
        else:
            inputs.apply(inputs.building_modifier(ob), values)
            ob.name = building_name(bd)
        ob[LOT] = bd.lot
        ob[BUILD_ROLE] = bd.role
        ob.location = (bd.x, bd.y, CURB)
        ob.rotation_euler = (0.0, 0.0, bd.rot)
        keep.add(ob.name)
    for o in _children(root, "building"):
        if o.name not in keep and not o.get(LOCK):
            me = o.data
            bpy.data.objects.remove(o)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)


def _props(root, props):
    index = {k: i for i, k in enumerate(placement.PROP_KEYS)}
    by_layer = {layer: [] for layer in LAYERS}
    for p in props:
        by_layer[placement.layer_of(p.key)].append(p)
    scatter = groups.scatter()
    for layer, items in by_layer.items():
        ob = _child_mesh(root, "props", f"{root.name} {layer}", layer)
        me = ob.data
        me.clear_geometry()
        me.vertices.add(len(items))
        co = []
        for p in items:
            co += (p.x, p.y, p.z)
        me.vertices.foreach_set("co", co)
        for name, kind, values in (
                ("oc_prop", "INT", [index[p.key] for p in items]),
                ("oc_rot", "FLOAT", [p.rot for p in items]),
                ("oc_tint", "FLOAT", [p.tint for p in items])):
            a = me.attributes.get(name) or me.attributes.new(name, kind, "POINT")
            a.data.foreach_set("value", values)
        a = me.attributes.get("oc_scale") or me.attributes.new("oc_scale", "FLOAT_VECTOR", "POINT")
        sc = []
        for p in items:
            sc += p.scale
        a.data.foreach_set("vector", sc)
        me.update()
        mod = next((m for m in ob.modifiers if m.type == "NODES"), None)
        if mod is None:
            mod = ob.modifiers.new("Open City Props", "NODES")
        mod.node_group = scatter


def _traffic(root, loops, cars):
    """The route curves (hidden) and one point per car on the `Traffic` object."""
    routes = next((o for o in _children(root, "routes")), None)
    if routes is None:
        cu = bpy.data.curves.new(f"{root.name} Traffic Routes", "CURVE")
        cu.dimensions = "3D"
        routes = bpy.data.objects.new(cu.name, cu)
        for c in root.users_collection:
            c.objects.link(routes)
        routes.parent = root
        routes[ROLE] = "routes"
        routes.hide_render = True
        routes.hide_set(True)
    cu = routes.data
    cu.splines.clear()
    for pts in loops:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        sp.points.foreach_set("co", [v for x, y in pts for v in (x, y, 0.0, 1.0)])
        sp.use_cyclic_u = True

    ob = _child_mesh(root, "traffic", f"{root.name} Traffic")
    me = ob.data
    me.clear_geometry()
    me.vertices.add(len(cars))
    co = []
    for c in cars:
        x, y, _h = placement.car_at(loops[c.route], c.length, c.phase)
        co += (x, y, 0.0)
    me.vertices.foreach_set("co", co)
    index = {k: i for i, k in enumerate(placement.PROP_KEYS)}
    for name, kind, values in (
            ("oc_prop", "INT", [index[c.key] for c in cars]),
            ("oc_route", "INT", [c.route for c in cars]),
            ("oc_phase", "FLOAT", [c.phase for c in cars]),
            ("oc_speed", "FLOAT", [c.speed for c in cars]),
            ("oc_len", "FLOAT", [c.length for c in cars]),
            ("oc_tint", "FLOAT", [c.tint for c in cars])):
        a = me.attributes.get(name) or me.attributes.new(name, kind, "POINT")
        a.data.foreach_set("value", values)
    a = me.attributes.get("oc_scale") or me.attributes.new("oc_scale", "FLOAT_VECTOR", "POINT")
    a.data.foreach_set("vector", [1.0] * (3 * len(cars)))
    me.update()
    mod = next((m for m in ob.modifiers if m.type == "NODES"), None)
    if mod is None:
        mod = ob.modifiers.new("Open City Traffic", "NODES")
    mod.node_group = groups.traffic()
    inputs.set(mod, "Routes", routes)


def delete_town(root):
    for o in list(root.children):
        me = o.data if o.type == "MESH" else None
        bpy.data.objects.remove(o)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    bpy.data.objects.remove(root)


def _realize_group():
    tree = bpy.data.node_groups.get("OC Realize")
    if tree is not None:
        return tree
    from .gn import Group
    G = Group("OC Realize", [("Geometry", "geometry")], [("Geometry", "geometry")])
    return G.finish(Geometry=G.g.realize(G.i("Geometry")))


def bake(context, root):
    """One plain mesh object with everything in the town realised (instances included). Returns it."""
    import bmesh
    realize = _realize_group()
    bm = bmesh.new()
    mats = []
    to_root = root.matrix_world.inverted()
    for o in root.children_recursive:
        if o.type != "MESH" or o.hide_get():
            continue
        tmp = o.copy()
        context.collection.objects.link(tmp)
        tmp.modifiers.new("Realize", "NODES").node_group = realize
        depsgraph = context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(depsgraph))
        bpy.data.objects.remove(tmp)
        me.transform(to_root @ o.matrix_world)
        offset = len(mats)
        mats += list(me.materials)
        if offset:
            idx = [0] * len(me.polygons)
            me.polygons.foreach_get("material_index", idx)
            me.polygons.foreach_set("material_index", [i + offset for i in idx])
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = bpy.data.meshes.new(f"{root.name} (real)")
    bm.to_mesh(out)
    bm.free()
    # one slot per material; faces that had none (empty slots left by primitives) get concrete
    from . import materials
    idx = [0] * len(out.polygons)
    out.polygons.foreach_get("material_index", idx)
    mats = [m or materials.get("OC Concrete") for m in mats] or [materials.get("OC Concrete")]
    unique, remap = [], []
    for m in mats:
        if m not in unique:
            unique.append(m)
        remap.append(unique.index(m))
    for m in unique:
        out.materials.append(m)
    out.polygons.foreach_set("material_index", [remap[i] if i < len(remap) else 0 for i in idx])
    ob = bpy.data.objects.new(out.name, out)
    context.collection.objects.link(ob)
    ob.matrix_world = root.matrix_world
    return ob
