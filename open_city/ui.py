# SPDX-License-Identifier: GPL-3.0-or-later
"""Sidebar panels (3D View > City) and the Add menu entries."""

import bpy

from . import groups, inputs, params, town
from .ops import ROLES, active_building, active_town
from .props import attr

TOWN_OPEN = (params.T_LAYOUT,)
BUILDING_OPEN = (params.SHAPE,)


def _wrap(text, width):
    line, out = "", []
    for word in text.split():
        if len(line) + len(word) + 1 > width and line:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return out + ([line] if line else [])


def _stage_buttons(layout):
    row = layout.row(align=True)
    row.operator("opencity.stage", text="Day", icon="LIGHT_SUN").night = False
    row.operator("opencity.stage", text="Night", icon="OUTLINER_OB_LIGHT").night = True


class OPENCITY_PT_base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "City"


class OPENCITY_PT_main(OPENCITY_PT_base, bpy.types.Panel):
    bl_label = "Open City"
    bl_idname = "OPENCITY_PT_main"

    def draw(self, context):
        layout = self.layout
        root = active_town(context)
        bld = active_building(context)
        if root is None and bld is None:
            col = layout.column()
            col.label(text="Generate a small town")
            for name, preset in params.PRESETS.items():
                row = col.row()
                row.scale_y = 1.3
                row.operator("opencity.add", text=name, icon="HOME").preset = name
                for line in _wrap(preset["desc"], 44):
                    col.label(text=line)
                col.separator(factor=0.5)
            col.separator()
            col.operator_menu_enum("opencity.add_building", "role", text="Add One Building", icon="MOD_BUILD")
            _stage_buttons(col)
            return

        tree = bpy.data.node_groups.get("OC Building")
        if tree is not None and tree.get("oc_version", 0) < groups.VERSION:
            box = layout.box()
            box.alert = True
            box.label(text="Made by an older generator", icon="ERROR")
            box.operator("opencity.rebuild", icon="FILE_REFRESH")

        if root is not None:
            box = layout.box()
            box.label(text=root.name, icon="HOME")
            row = box.row(align=True)
            row.menu("OPENCITY_MT_presets", text="Preset", icon="PRESET")
            row.operator("opencity.seed", text="", icon="FILE_REFRESH")
            tp = root.open_city_town
            row = box.row(align=True)
            row.prop(tp, "seed")
            row.prop(tp, "live_update", text="", icon="PLAY")
            box.operator("opencity.regenerate", icon="MOD_BUILD")
            if root.get("oc_summary"):
                for line in _wrap(root["oc_summary"], 46):
                    box.label(text=line)

        if bld is not None:
            box = layout.box()
            role = dict((k, label) for k, label, _d in ROLES).get(bld.get(town.BUILD_ROLE), "Building")
            box.label(text=f"{bld.name}", icon="MOD_BUILD")
            s = inputs.settings_of(inputs.building_modifier(bld))
            w = s["Bays Wide"] * s["Bay Width"]
            d = s["Bays Deep"] * s["Bay Width"]
            box.label(text=f"{role}: {w:.1f} x {d:.1f} m, {s['Floors']} floors")
            row = box.row(align=True)
            row.operator("opencity.reroll", icon="SHADERFX")
            row.operator("opencity.building_seed", text="", icon="FILE_REFRESH")
            if town.town_root(bld) is not None:
                locked = bool(bld.get(town.LOCK))
                box.operator("opencity.lock", text="Locked" if locked else "Lock",
                             icon="LOCKED" if locked else "UNLOCKED", depress=locked)


class OPENCITY_MT_presets(bpy.types.Menu):
    bl_label = "Town Presets"
    bl_idname = "OPENCITY_MT_presets"

    def draw(self, _context):
        for name in params.PRESETS:
            self.layout.operator("opencity.preset", text=name).preset = name


def _town_panel(panel_name):
    idname = "OPENCITY_PT_town_" + attr(panel_name)

    class Panel(OPENCITY_PT_base, bpy.types.Panel):
        bl_label = f"Town: {panel_name}"
        bl_idname = idname
        bl_parent_id = "OPENCITY_PT_main"
        bl_options = set() if panel_name in TOWN_OPEN else {"DEFAULT_CLOSED"}

        @classmethod
        def poll(cls, context):
            return active_town(context) is not None

        def draw(self, context):
            tp = active_town(context).open_city_town
            col = self.layout.column(align=True)
            for name, kind, _d, opts in params.TOWN_PARAMS:
                if opts.get("panel") != panel_name or name == "Seed":
                    continue
                col.prop(tp, attr(name), slider=kind == "float" and opts.get("max", 2) <= 1.0)

    Panel.__name__ = idname
    return Panel


def _building_panel(panel_name):
    idname = "OPENCITY_PT_building_" + attr(panel_name)

    class Panel(OPENCITY_PT_base, bpy.types.Panel):
        bl_label = f"Building: {panel_name}"
        bl_idname = idname
        bl_parent_id = "OPENCITY_PT_main"
        bl_options = set() if panel_name in BUILDING_OPEN else {"DEFAULT_CLOSED"}

        @classmethod
        def poll(cls, context):
            return active_building(context) is not None

        def draw(self, context):
            bp = active_building(context).open_city
            col = self.layout.column(align=True)
            for name, kind, _d, opts in params.BUILDING_PARAMS:
                if opts.get("panel") != panel_name:
                    continue
                col.prop(bp, attr(name), slider=kind == "float" and opts.get("max", 2) <= 1.0)

    Panel.__name__ = idname
    return Panel


class OPENCITY_PT_tools(OPENCITY_PT_base, bpy.types.Panel):
    bl_label = "Tools"
    bl_idname = "OPENCITY_PT_tools"
    bl_parent_id = "OPENCITY_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return active_town(context) is not None or active_building(context) is not None

    def draw(self, context):
        col = self.layout.column(align=True)
        col.operator("opencity.make_real", icon="MESH_DATA")
        _stage_buttons(col)
        col.operator_menu_enum("opencity.add_building", "role", text="Add One Building", icon="MOD_BUILD")
        col.operator("opencity.rebuild", icon="FILE_REFRESH")


BUILDING_PANELS = [_building_panel(p) for p in (params.SHAPE, params.FACADE, params.GROUND, params.ROOF,
                                                params.COLOURS)]
TOWN_PANELS = [_town_panel(p) for p in (params.T_LAYOUT, params.T_BUILDINGS, params.T_STREETS,
                                        params.T_DETAILS)]
CLASSES = (OPENCITY_PT_main, OPENCITY_MT_presets, *BUILDING_PANELS, *TOWN_PANELS, OPENCITY_PT_tools)


def _menu_add(self, _context):
    self.layout.operator("opencity.add", text="Town", icon="HOME").preset = "Main Street"
    self.layout.operator_menu_enum("opencity.add_building", "role", text="Town Building", icon="MOD_BUILD")


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_mesh_add.append(_menu_add)


def unregister():
    bpy.types.VIEW3D_MT_mesh_add.remove(_menu_add)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
