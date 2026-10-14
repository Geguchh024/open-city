# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading and writing a building's settings on its modifier.

Blender 5.2 keeps modifier inputs in `modifier.properties.inputs[identifier]["value"]`; older versions
used `modifier[identifier]`. Everything else goes through here and addresses settings by name.
"""

import bpy

from . import params

MODIFIER_NAME = "Open City Building"
BUILDING_GROUP = "OC Building"


def _ids(tree):
    return {it.name: it.identifier for it in tree.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT"}


def _new_style(mod):
    props = getattr(mod, "properties", None)
    return props is not None and hasattr(props, "inputs")


def _plain(v):
    """IDProperty arrays (colours) as tuples."""
    if hasattr(v, "to_list"):
        return tuple(v.to_list())
    if hasattr(v, "__len__") and not isinstance(v, str):
        return tuple(v)
    return v


def get(mod, name, default=None):
    if mod.node_group is None:
        return default
    ident = _ids(mod.node_group).get(name)
    if ident is None:
        return default
    try:
        if _new_style(mod):
            return _plain(mod.properties.inputs[ident]["value"])
        return _plain(mod[ident])
    except (KeyError, TypeError):
        return default


def set(mod, name, value):
    """Set one setting by name (clamped to its range). Returns False if the modifier has no such input."""
    if mod.node_group is None:
        return False
    ident = _ids(mod.node_group).get(name)
    if ident is None:
        return False
    if name in params.BY_NAME:
        value = params.clamp_value(name, value)
    if isinstance(value, list):
        value = tuple(value)
    if _new_style(mod):
        mod.properties.inputs[ident]["value"] = value
    else:
        mod[ident] = value
    mod.id_data.update_tag()
    return True


def read_all(mod):
    out = {}
    if mod.node_group is None:
        return out
    for name in _ids(mod.node_group):
        v = get(mod, name)
        if v is not None:
            out[name] = v
    return out


def apply(mod, values):
    for name, value in values.items():
        if value is not None:
            set(mod, name, value)


def building_modifier(obj):
    """The Open City building modifier on an object, or None."""
    if obj is None or getattr(obj, "modifiers", None) is None:
        return None
    for mod in obj.modifiers:
        if mod.type == "NODES" and mod.node_group is not None and mod.node_group.name.startswith(BUILDING_GROUP):
            return mod
    return None


def settings_of(mod):
    """Every building setting, with the defaults filled in."""
    values = params.building_defaults()
    values.update({k: v for k, v in read_all(mod).items() if k in params.BY_NAME})
    return values


def users():
    """(object, modifier) for every object with a building modifier."""
    return [(o, m) for o in bpy.data.objects if (m := building_modifier(o)) is not None]
