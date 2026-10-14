# SPDX-License-Identifier: GPL-3.0-or-later
"""Day and night stages for the town (EEVEE). Optional: `opencity.stage` applies one.

    day     a soft warm sun, a blue sky with gentle fill light, contact shadows and the bright Standard
            colour transform: the look of the stylized references
    night   a cold moon, a deep blue sky with stars, lit windows and glowing street lamps that throw warm
            pools of light, headlights on the moving cars, and a soft bloom round every light
"""

import math

import bpy

from . import lights
from .styles import hexlin

SUN = "Open City Sun"
GLOW = "OC Night Glow"


def _world(scene, night):
    world = scene.world
    if world is None or not world.name.startswith("Open City Sky"):
        world = bpy.data.worlds.new("Open City Sky")
        scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    # the camera sees the sky; the scene is lit by a softer, paler (or at night, dim blue) fill
    path = nt.nodes.new("ShaderNodeLightPath")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    if night:
        els[0].position, els[0].color = 0.5, (*hexlin("#33456E"), 1.0)
        els[1].position, els[1].color = 0.75, (*hexlin("#070B1D"), 1.0)
    else:
        els[0].position, els[0].color = 0.5, (*hexlin("#BFD9F2"), 1.0)
        els[1].position, els[1].color = 0.85, (*hexlin("#5E9BE0"), 1.0)
    nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    sky = nt.nodes.new("ShaderNodeBackground")
    sky.inputs["Strength"].default_value = 1.0
    colour = ramp.outputs[0]
    if night:
        # stars: tiny bright cells of a Voronoi pattern on the sky dome, fading out towards the horizon
        vor = nt.nodes.new("ShaderNodeTexVoronoi")
        vor.inputs["Scale"].default_value = 420.0
        nt.links.new(coord.outputs["Generated"], vor.inputs["Vector"])
        dot = nt.nodes.new("ShaderNodeMapRange")
        dot.inputs["From Min"].default_value = 0.09
        dot.inputs["From Max"].default_value = 0.0
        nt.links.new(vor.outputs["Distance"], dot.inputs["Value"])
        high = nt.nodes.new("ShaderNodeMapRange")
        high.inputs["From Min"].default_value = 0.53
        high.inputs["From Max"].default_value = 0.7
        nt.links.new(sep.outputs["Z"], high.inputs["Value"])
        bright = nt.nodes.new("ShaderNodeMath")
        bright.operation = "MULTIPLY"
        nt.links.new(dot.outputs[0], bright.inputs[0])
        nt.links.new(high.outputs[0], bright.inputs[1])
        stars = nt.nodes.new("ShaderNodeMix")
        stars.data_type = "RGBA"
        stars.blend_type = "ADD"
        nt.links.new(bright.outputs[0], stars.inputs["Factor"])
        nt.links.new(ramp.outputs[0], stars.inputs["A"])
        stars.inputs["B"].default_value = (2.5, 2.5, 2.8, 1.0)
        colour = stars.outputs["Result"]
    nt.links.new(colour, sky.inputs["Color"])
    fill = nt.nodes.new("ShaderNodeBackground")
    fill.inputs["Color"].default_value = (*hexlin("#2A3C66" if night else "#D6E4F5"), 1.0)
    fill.inputs["Strength"].default_value = 0.22 if night else 0.55
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(fill.outputs[0], mix.inputs[1])
    nt.links.new(sky.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return world


def _sun(scene, collection, night):
    ob = bpy.data.objects.get(SUN)
    if ob is None:
        ob = bpy.data.objects.new(SUN, bpy.data.lights.new(SUN, "SUN"))
        collection.objects.link(ob)
    sun = ob.data
    for key, value in (("shadow_cascade_max_distance", 600.0), ("shadow_maximum_resolution", 0.01),
                       ("use_shadow_jitter", True)):
        if hasattr(sun, key):
            setattr(sun, key, value)
    if night:
        # a high, cold moon: just enough to read the roofs and the streets between the lamps
        sun.energy = 0.35
        sun.color = hexlin("#9DB5FF")
        sun.angle = math.radians(1.0)
        ob.rotation_euler = (math.radians(35), 0.0, math.radians(140))
    else:
        sun.energy = 4.2
        sun.color = hexlin("#FFF0D8")
        sun.angle = math.radians(2.5)
        # low and from the front left, so facades facing the street get light and long soft shadows
        ob.rotation_euler = (math.radians(52), 0.0, math.radians(-38))
    return ob


def _glow(scene, night):
    """A soft bloom round lamps and lit windows at night (the compositor); nothing by day."""
    if not hasattr(scene, "compositing_node_group"):
        return
    if not night:
        if scene.compositing_node_group is not None and scene.compositing_node_group.name.startswith(GLOW):
            scene.compositing_node_group = None
        return
    tree = bpy.data.node_groups.get(GLOW)
    if tree is None:
        tree = bpy.data.node_groups.new(GLOW, "CompositorNodeTree")
        tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    tree.nodes.clear()
    rl = tree.nodes.new("CompositorNodeRLayers")
    glare = tree.nodes.new("CompositorNodeGlare")
    for key, value in (("Type", "Bloom"), ("Quality", "High"), ("Threshold", 0.8), ("Strength", 0.55),
                       ("Size", 0.6), ("Smoothness", 0.4)):
        sock = glare.inputs.get(key)
        if sock is not None:
            try:
                sock.default_value = value
            except (TypeError, ValueError):
                pass
    out = tree.nodes.new("NodeGroupOutput")
    rl.location, glare.location, out.location = (-300, 0), (0, 0), (300, 0)
    tree.links.new(rl.outputs["Image"], glare.inputs["Image"])
    tree.links.new(glare.outputs[0], out.inputs[0])
    scene.compositing_node_group = tree
    scene.render.use_compositing = True


def setup(scene, collection=None, night=False):
    """Apply the day (or night) stage to a scene. Returns the sun (or moon) object."""
    _world(scene, night)
    sun = _sun(scene, collection or scene.collection, night)
    lights.set_night(1.0 if night else 0.0)
    _glow(scene, night)
    ee = scene.eevee
    for key, value in (("use_raytracing", True), ("use_fast_gi", True), ("fast_gi_distance", 6.0),
                       ("shadow_ray_count", 2), ("shadow_step_count", 10), ("taa_render_samples", 64),
                       ("use_shadows", True)):
        if hasattr(ee, key):
            setattr(ee, key, value)
    if night and hasattr(ee, "shadow_pool_size"):
        ee.shadow_pool_size = "1024"              # room for the shadows of every street lamp
    if night:
        # AgX rolls bright lamps and windows off softly instead of clipping them to flat white
        scene.view_settings.view_transform = "AgX"
        for look in ("AgX - Punchy", "Punchy", "None"):
            try:
                scene.view_settings.look = look
                break
            except TypeError:
                continue
        scene.view_settings.exposure = 0.3
    else:
        # Standard keeps the saturated, toy-like colours of the references (AgX greys them)
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"
        scene.view_settings.exposure = -0.1
    return sun
