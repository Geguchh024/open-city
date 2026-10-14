# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators: add a town or a single building, presets, seeds, regenerating, re-rolling one building,
locking, baking to a real mesh and rebuilding the generator."""

import random

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import groups, inputs, params, stage, styles, town
from .props import write_town

ROLES = [("shop", "Shop & Apartments", "A mixed-use building with a shop on the ground floor"),
         ("corner", "Corner Building", "A shop on a street corner, with a second street facade"),
         ("row", "Townhouse", "A residential row house with a stoop"),
         ("house", "House", "A detached house with a pitched roof"),
         ("landmark", "Landmark", "A civic building with a clock tower, or a corner turret")]


def _preset_items(_self, _context):
    return [(n, n, p["desc"]) for n, p in params.PRESETS.items()]


def active_town(context):
    return town.town_root(context.active_object)


def active_building(context):
    ob = context.active_object
    return ob if inputs.building_modifier(ob) is not None else None


class OPENCITY_OT_add(bpy.types.Operator):
    bl_idname = "opencity.add"
    bl_label = "Add Town"
    bl_description = "Generate a new small town at the 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(name="Preset", items=_preset_items)

    def execute(self, context):
        values = params.preset_values(self.preset or "Main Street")
        values["Seed"] = random.randint(0, 9999)
        root = town.new_town(context, values, name=self.preset or "Town")
        for o in context.selected_objects:
            o.select_set(False)
        root.select_set(True)
        context.view_layer.objects.active = root
        self.report({"INFO"}, root.get("oc_summary", ""))
        return {"FINISHED"}


class OPENCITY_OT_preset(bpy.types.Operator):
    bl_idname = "opencity.preset"
    bl_label = "Apply Preset"
    bl_description = "Replace the town settings with a preset, keeping the seed"
    bl_options = {"REGISTER", "UNDO"}

    preset: StringProperty()

    @classmethod
    def poll(cls, context):
        return active_town(context) is not None

    def execute(self, context):
        root = active_town(context)
        values = params.preset_values(self.preset)
        values.pop("Seed", None)
        write_town(root, values)
        town.generate(root)
        return {"FINISHED"}


class OPENCITY_OT_seed(bpy.types.Operator):
    bl_idname = "opencity.seed"
    bl_label = "New Seed"
    bl_description = "Roll a different town with the same settings"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_town(context) is not None

    def execute(self, context):
        root = active_town(context)
        tp = root.open_city_town
        old = tp.seed
        new = old
        while new == old:
            new = random.randint(0, 9999)
        write_town(root, {"Seed": new})
        town.generate(root)
        return {"FINISHED"}


class OPENCITY_OT_regenerate(bpy.types.Operator):
    bl_idname = "opencity.regenerate"
    bl_label = "Regenerate"
    bl_description = "Rebuild the town from its settings (locked buildings are kept as they are)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_town(context) is not None

    def execute(self, context):
        plan = town.generate(active_town(context))
        self.report({"INFO"}, plan.summary())
        return {"FINISHED"}


def _town_settings_for(ob):
    root = town.town_root(ob)
    return town.settings_of(root) if root is not None else params.town_defaults()


class OPENCITY_OT_reroll(bpy.types.Operator):
    bl_idname = "opencity.reroll"
    bl_label = "Re-roll Style"
    bl_description = ("Give the selected buildings a new style, colours and height on the same footprint. "
                      "They are locked so regenerating the town keeps them")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_building(context) is not None or any(
            inputs.building_modifier(o) is not None for o in context.selected_objects)

    def execute(self, context):
        obs = [o for o in context.selected_objects if inputs.building_modifier(o)] or [active_building(context)]
        for ob in obs:
            mod = inputs.building_modifier(ob)
            cur = inputs.settings_of(mod)
            role = ob.get(town.BUILD_ROLE, "shop" if cur["Ground Use"] == 1 else "row")
            s = _town_settings_for(ob)
            s["Bay Width"] = cur["Bay Width"]
            rng = random.Random()
            p = styles.style(rng, role, s, cur["Bays Wide"], cur["Bays Deep"], styles.Namer(rng))
            for keep in ("Bays Wide", "Bays Deep", "Bay Width", "Attached Left", "Attached Right", "Corner Side"):
                p[keep] = cur[keep]
            if role == "landmark" and p["Tower"] == 1 and cur["Corner Side"] == 0:
                p["Tower"] = 2
            inputs.apply(mod, {k: v for k, v in p.items() if k in params.BY_NAME})
            if town.town_root(ob) is not None:
                ob[town.LOCK] = True
        return {"FINISHED"}


class OPENCITY_OT_building_seed(bpy.types.Operator):
    bl_idname = "opencity.building_seed"
    bl_label = "New Detail Seed"
    bl_description = "Reshuffle balconies, flower boxes, curtains and rooftop clutter of the selected buildings"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_building(context) is not None

    def execute(self, context):
        for ob in context.selected_objects or [context.active_object]:
            mod = inputs.building_modifier(ob)
            if mod is not None:
                inputs.set(mod, "Seed", random.randint(0, 99999))
        return {"FINISHED"}


class OPENCITY_OT_lock(bpy.types.Operator):
    bl_idname = "opencity.lock"
    bl_label = "Lock"
    bl_description = "Locked buildings keep their settings when the town is regenerated"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obs = [o for o in context.selected_objects if inputs.building_modifier(o)]
        state = not all(o.get(town.LOCK) for o in obs)
        for o in obs:
            o[town.LOCK] = state
        return {"FINISHED"}


class OPENCITY_OT_add_building(bpy.types.Operator):
    bl_idname = "opencity.add_building"
    bl_label = "Add Building"
    bl_description = "Add one modular building at the 3D cursor"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(name="Type", items=ROLES, default="shop")

    def execute(self, context):
        rng = random.Random()
        s = params.town_defaults()
        bays = {"house": rng.choice((2, 3)), "landmark": 5}.get(self.role, rng.choice((3, 4)))
        deep = 3 if self.role != "landmark" else 4
        p = styles.style(rng, self.role, s, bays, deep, styles.Namer(rng))
        if self.role in ("corner", "landmark"):
            p["Corner Side"] = 2
        ob = town.make_building_object(context.collection, ROLES_NAME[self.role],
                                       {k: v for k, v in p.items() if k in params.BY_NAME})
        ob.location = context.scene.cursor.location
        ob[town.BUILD_ROLE] = self.role
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}


ROLES_NAME = {k: label for k, label, _d in ROLES}


class OPENCITY_OT_make_real(bpy.types.Operator):
    bl_idname = "opencity.make_real"
    bl_label = "Make Real"
    bl_description = ("Bake the town (or the selected building) into an ordinary mesh, instances realised and "
                      "materials kept. The generator is hidden, not deleted")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_town(context) is not None or active_building(context) is not None

    def execute(self, context):
        root = active_town(context)
        if root is not None and context.active_object is root:
            ob = town.bake(context, root)
            for o in [root] + list(root.children_recursive):
                o.hide_set(True)
        else:
            src = active_building(context)
            dg = context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(src.evaluated_get(dg))
            me.name = f"{src.name} (real)"
            ob = bpy.data.objects.new(me.name, me)
            context.collection.objects.link(ob)
            ob.matrix_world = src.matrix_world
            src.hide_set(True)
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({"INFO"}, f"Baked {len(ob.data.polygons):,} faces")
        return {"FINISHED"}


class OPENCITY_OT_stage(bpy.types.Operator):
    bl_idname = "opencity.stage"
    bl_label = "Day & Night"
    bl_description = ("Light the scene like the stylized references: a warm low sun with soft shadows, a blue "
                      "sky, ambient occlusion and bright colours (EEVEE)")
    bl_options = {"REGISTER", "UNDO"}

    night: BoolProperty(name="Night", default=False,
                        description="A moonlit night: lit windows, glowing street lamps, headlights and stars")

    @classmethod
    def description(cls, _context, props):
        if props.night:
            return ("Turn the town to night: a cold moon and a starry sky, lit windows, street lamps throwing warm "
                    "pools of light, headlights on the moving traffic and a soft bloom (EEVEE)")
        return cls.bl_description

    def execute(self, context):
        stage.setup(context.scene, context.collection, night=self.night)
        return {"FINISHED"}


class OPENCITY_OT_rebuild(bpy.types.Operator):
    bl_idname = "opencity.rebuild"
    bl_label = "Update Generator"
    bl_description = "Rebuild the generator's node groups and materials, keeping every building's settings"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        groups.rebuild()
        self.report({"INFO"}, "Generator rebuilt")
        return {"FINISHED"}


CLASSES = (OPENCITY_OT_add, OPENCITY_OT_preset, OPENCITY_OT_seed, OPENCITY_OT_regenerate, OPENCITY_OT_reroll,
           OPENCITY_OT_building_seed, OPENCITY_OT_lock, OPENCITY_OT_add_building, OPENCITY_OT_make_real,
           OPENCITY_OT_stage, OPENCITY_OT_rebuild)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
