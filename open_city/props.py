# SPDX-License-Identifier: GPL-3.0-or-later
"""Generation settings as Blender properties.

    object.open_city_town   on a town root: the town settings. Changing one regenerates the town
                            (when Live Update is on); the same seed and settings give the same town.
    object.open_city        on a building: its settings, read from and written to its modifier through
                            getters and setters, so the sidebar, the modifier panel and animation never
                            disagree and a saved file keeps working without the add-on.
"""

import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)

from . import inputs, params

_suspend = [0]


def attr(name):
    """Property name for a setting: 'Bays Wide' -> 'bays_wide'."""
    return name.lower().replace(" ", "_").replace("-", "_")


# -- the town --------------------------------------------------------------------------------------------
def _town_update(self, context):
    if _suspend[0] or not self.live_update:
        return
    from . import town
    root = self.id_data
    if root.get(town.TOWN):
        town.generate(root)


def _town_props():
    ann = {"live_update": BoolProperty(name="Live Update", default=True,
                                       description="Regenerate the town as soon as a setting changes")}
    for name, kind, default, opts in params.TOWN_PARAMS:
        tip = opts.get("tip", "")
        key = attr(name)
        if kind == "bool":
            ann[key] = BoolProperty(name=name, description=tip, default=default, update=_town_update)
        elif kind == "int" and "items" in opts:
            items = [(str(i), label, "", i) for i, label in enumerate(opts["items"])]
            ann[key] = EnumProperty(name=name, description=tip, items=items, default=str(default),
                                    update=_town_update)
        elif kind == "int":
            ann[key] = IntProperty(name=name, description=tip, default=default, min=opts["min"], max=opts["max"],
                                   update=_town_update)
        else:
            extra = {"unit": "LENGTH", "subtype": "DISTANCE"} if opts.get("subtype") == "DISTANCE" else {}
            ann[key] = FloatProperty(name=name, description=tip, default=default, min=opts["min"],
                                     max=opts["max"], update=_town_update, **extra)
    return type("OpenCityTownProps", (bpy.types.PropertyGroup,), {"__annotations__": ann})


def write_town(root, values):
    """Store town settings on a root without regenerating once per value."""
    tp = root.open_city_town
    _suspend[0] += 1
    try:
        for name, value in values.items():
            if name in params.TOWN_BY_NAME:
                value = params.clamp_value(name, value, params.TOWN_BY_NAME)
                if "items" in params.TOWN_BY_NAME[name][3]:
                    value = str(value)
                setattr(tp, attr(name), value)
    finally:
        _suspend[0] -= 1


def read_town(tp, name):
    """One town setting from the property group, as the plain value the planner takes."""
    value = getattr(tp, attr(name))
    return int(value) if "items" in params.TOWN_BY_NAME[name][3] else value


# -- a building ---------------------------------------------------------------------------------------------
def _modifier(self):
    return inputs.building_modifier(self.id_data)


def _getter(name, default, cast):
    def get(self):
        mod = _modifier(self)
        if mod is None:
            return cast(default)
        return cast(inputs.get(mod, name, default))
    return get


def _setter(name):
    def set_(self, value):
        mod = _modifier(self)
        if mod is not None:
            inputs.set(mod, name, value)
    return set_


def _building_props():
    ann = {}
    for name, kind, default, opts in params.BUILDING_PARAMS:
        key = attr(name)
        tip = opts.get("tip", "")
        if kind == "int" and "items" in opts:
            items = [(str(i), label, "", i) for i, label in enumerate(opts["items"])]
            ann[key] = EnumProperty(name=name, description=tip, items=items,
                                    get=_getter(name, default, int), set=_setter(name))
        elif kind == "bool":
            ann[key] = BoolProperty(name=name, description=tip, default=bool(default),
                                    get=_getter(name, default, bool), set=_setter(name))
        elif kind == "int":
            ann[key] = IntProperty(name=name, description=tip, default=int(default), min=opts.get("min", 0),
                                   max=opts.get("max", 1000), get=_getter(name, default, int), set=_setter(name))
        elif kind == "string":
            ann[key] = StringProperty(name=name, description=tip, default=default,
                                      get=_getter(name, default, str), set=_setter(name))
        elif kind == "color":
            ann[key] = FloatVectorProperty(name=name, description=tip, subtype="COLOR", size=4, min=0.0, max=1.0,
                                           default=default, get=_getter(name, default, tuple), set=_setter(name))
        else:
            extra = {"unit": "LENGTH", "subtype": "DISTANCE"} if opts.get("subtype") == "DISTANCE" else {}
            ann[key] = FloatProperty(name=name, description=tip, default=float(default), min=opts.get("min", 0.0),
                                     max=opts.get("max", 1.0), get=_getter(name, default, float),
                                     set=_setter(name), **extra)
    return type("OpenCityBuildingProps", (bpy.types.PropertyGroup,), {"__annotations__": ann})


OpenCityTownProps = _town_props()
OpenCityBuildingProps = _building_props()


def register():
    bpy.utils.register_class(OpenCityTownProps)
    bpy.utils.register_class(OpenCityBuildingProps)
    bpy.types.Object.open_city_town = PointerProperty(type=OpenCityTownProps)
    bpy.types.Object.open_city = PointerProperty(type=OpenCityBuildingProps)


def unregister():
    del bpy.types.Object.open_city
    del bpy.types.Object.open_city_town
    bpy.utils.unregister_class(OpenCityBuildingProps)
    bpy.utils.unregister_class(OpenCityTownProps)
