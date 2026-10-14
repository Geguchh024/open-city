# SPDX-License-Identifier: GPL-3.0-or-later
"""Building, finding and rebuilding the generator's node groups and materials.

    OC Kit *         the modular architectural kit (windows, doors, roofs, ...)
    OC Building *    the parametric building and its four sub-groups
    OC Prop *        the prop library
    OC Scatter       instances the prop library on points
    OC Traffic       drives cars round the town's routes
"""

import bpy

from . import building, inputs, kit, materials
from .placement import PROP_KEYS

VERSION = 3


def group_names():
    return kit.group_names() + [building.BUILDING, *building.SUBGROUPS]


def _build():
    materials.ensure_all()
    trees = kit.build_all()
    master = building.build_building(trees)
    kit.build_traffic(kit.build_scatter(PROP_KEYS))
    master["oc_version"] = VERSION
    for name in group_names():
        tree = bpy.data.node_groups.get(name)
        if tree is not None:
            tree.use_fake_user = False
    return master


def ensure():
    """The `OC Building` group, building every group the first time it is needed."""
    tree = bpy.data.node_groups.get(building.BUILDING)
    if (tree is None or tree.get("oc_version") != VERSION or bpy.data.node_groups.get(kit.SCATTER) is None
            or bpy.data.node_groups.get(kit.TRAFFIC) is None):
        return rebuild()
    return tree


def scatter():
    ensure()
    return bpy.data.node_groups[kit.SCATTER]


def traffic():
    ensure()
    return bpy.data.node_groups[kit.TRAFFIC]


def rebuild():
    """Rebuild every group and material in place; modifiers that used them keep their settings."""
    users = []
    for ob in bpy.data.objects:
        for mod in ob.modifiers:
            if mod.type == "NODES" and mod.node_group is not None and mod.node_group.name in (
                    building.BUILDING, kit.SCATTER, kit.TRAFFIC):
                users.append((mod, mod.node_group.name, inputs.read_all(mod)))
                mod.node_group = None
    for name in group_names():
        old = bpy.data.node_groups.get(name)
        if old is not None:
            bpy.data.node_groups.remove(old)
    materials.rebuild_all()
    master = _build()
    for mod, name, saved in users:
        mod.node_group = bpy.data.node_groups[name]
        inputs.apply(mod, saved)
    return master
