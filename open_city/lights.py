# SPDX-License-Identifier: GPL-3.0-or-later
"""Day and night.

One switch turns the whole town from day to night: `OC Night`, a tiny shader group every night-aware
material reads (lit windows, glowing lamps, sign letters, tail lights), and three shared lights the node
groups instance on street lamps, park lamps and moving cars. Night is 1, day is 0. Nothing here uses
drivers or handlers, so a saved file keeps its day or night without the add-on.
"""

import math

import bpy

from .styles import hexlin

NIGHT = "OC Night"
LAMP, PARK_LAMP, HEADLIGHT = "OC Lamp Light", "OC Park Lamp Light", "OC Headlight"

# name -> (type, colour, watts at night, radius, casts shadows)
SPECS = {
    LAMP: ("POINT", "#FFC27A", 520.0, 0.12, True),
    PARK_LAMP: ("POINT", "#FFD8A0", 200.0, 0.1, True),
    HEADLIGHT: ("SPOT", "#FFF0D2", 700.0, 0.06, False),
}


def night_group():
    """The shader group holding the switch; its one output is 0 by day and 1 by night."""
    tree = bpy.data.node_groups.get(NIGHT)
    if tree is not None:
        return tree
    tree = bpy.data.node_groups.new(NIGHT, "ShaderNodeTree")
    tree.interface.new_socket("Night", in_out="OUTPUT", socket_type="NodeSocketFloat")
    v = tree.nodes.new("ShaderNodeValue")
    v.name = v.label = "Night"
    v.outputs[0].default_value = 0.0
    out = tree.nodes.new("NodeGroupOutput")
    out.location = (200, 0)
    tree.links.new(v.outputs[0], out.inputs[0])
    tree.use_fake_user = True
    return tree


def night_amount():
    return night_group().nodes["Night"].outputs[0].default_value


def light(name):
    """One of the shared light objects, made on first use (it lives only in the node groups that instance it)."""
    kind, colour, watts, radius, shadow = SPECS[name]
    ob = bpy.data.objects.get(name)
    if ob is None or ob.type != "LIGHT":
        data = bpy.data.lights.get(name) or bpy.data.lights.new(name, kind)
        ob = bpy.data.objects.new(name, data)
        ob.use_fake_user = True
    data = ob.data
    data.color = hexlin(colour)
    data.shadow_soft_size = radius
    data.use_shadow = shadow
    if kind == "SPOT":
        data.spot_size = math.radians(75)
        data.spot_blend = 0.7
    if hasattr(data, "use_custom_distance"):
        # a lamp only lights its own stretch of street, which keeps a town of them fast in EEVEE
        data.use_custom_distance = True
        data.cutoff_distance = 30.0
    if shadow and hasattr(data, "shadow_resolution_scale"):
        data.shadow_resolution_scale = 0.3        # soft lamp shadows need few texels, and there are many lamps
    data.energy = watts * night_amount()
    return ob


def set_night(amount):
    """Turn every town in the file to night (1.0) or day (0.0)."""
    night_group().nodes["Night"].outputs[0].default_value = amount
    for name in SPECS:
        light(name)
