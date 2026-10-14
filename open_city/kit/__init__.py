# SPDX-License-Identifier: GPL-3.0-or-later
"""The modular architectural kit: every module is a node group with a fixed frame and shared sizes.

    parts       chamfered boxes and the part builder every module uses
    openings    windows, French doors, storefronts, doors, stoops, shutters, flower boxes,
                balconies, awnings
    roofs       gable, hip and mansard roofs, dormers, chimneys, rooftop equipment
    street      street lights, benches, bins, hydrants, signs, bus shelter, cafe sets...
    nature      trees, shrubs, hedges, flower beds, fences, a fountain
    vehicles    hatchback, sedan, city car, delivery van
"""

import math

from .. import lights
from ..gn import Group
from . import nature, openings, parts, roofs, street, vehicles

SCATTER = "OC Scatter"
TRAFFIC = "OC Traffic"
# where the light sits in a lamp, just under the lantern and clear of the post
LAMP_LIGHTS = {"lamp": (lights.LAMP, (0.13, 0.0, 4.0)), "park_lamp": (lights.PARK_LAMP, (0.12, 0.0, 2.86))}
PROP_MODULES = (street, nature, vehicles)


def build_all():
    """Build every architectural group. Returns {name: node group}."""
    parts.build_cbox()
    trees = {}
    trees.update(openings.build_all())
    trees.update(roofs.build_all())
    return trees


def build_scatter(order):
    """`OC Scatter`: instances the prop library on points.

    Each point carries `oc_prop` (index into `order`), `oc_rot` (turn about Z) and `oc_scale`;
    other point attributes such as `oc_tint` travel with the instance to the shaders. Street and park lamps
    also carry a light, dark by day.
    """
    props = {}
    for mod in PROP_MODULES:
        props.update(dict(mod.build_all()))
    G = Group(SCATTER, [("Geometry", "geometry")], [("Geometry", "geometry")])
    g = G.g
    lib = []
    for key in order:
        n = g.nodes.new("GeometryNodeGroup")
        n.node_tree = props[key]
        lib.append(n.outputs[0])
    pts = G.i("Geometry")
    kind = g.named("oc_prop", "INT")
    turn = g.euler(0.0, 0.0, g.named("oc_rot"))
    inst = g.instance(pts, g.library(lib), pick=True, index=kind, rotation=turn,
                      scale=g.named("oc_scale", "FLOAT_VECTOR"))
    out = [inst]
    for key, (name, at) in LAMP_LIGHTS.items():
        lamp = g.transform(_light(g, name), translation=at)
        out.append(g.instance(pts, lamp, rotation=turn, selection=g.cmp("EQUAL", kind, order.index(key), "INT")))
    return G.finish(Geometry=g.join(*out))


def _light(g, name):
    return g.out("GeometryNodeObjectInfo", {"Object": lights.light(name), "As Instance": True}, output="Geometry")


def build_traffic(scatter):
    """`OC Traffic`: cars driving round closed routes, moved by the scene clock (press play).

    Each point is a car: `oc_route` (which curve of `Routes`), `oc_phase` (where on it the car is at time 0,
    0..1), `oc_speed` (m/s) and `oc_len` (the route's length). The cars themselves come from `OC Scatter`,
    so they are the same models as the parked ones; at night they drive with their headlights on.
    """
    G = Group(TRAFFIC, [("Geometry", "geometry"), ("Routes", "object")], [("Geometry", "geometry")])
    g = G.g
    pts = G.i("Geometry")
    routes = g.out("GeometryNodeObjectInfo", {"Object": G.i("Routes")}, output="Geometry", transform_space="ORIGINAL")
    seconds = g.out("GeometryNodeInputSceneTime", output="Seconds")
    travelled = g.div(g.mul(seconds, g.named("oc_speed")), g.max(g.named("oc_len"), 1.0))
    at = g.fract(g.add(g.named("oc_phase"), travelled))
    sample = g.node("GeometryNodeSampleCurve", mode="FACTOR", use_all_curves=False)
    g.set(sample, "Curves", routes)
    g.set(sample, "Factor", at)
    g.set(sample, "Curve Index", g.named("oc_route", "INT"))
    tx, ty, _tz = g.split(sample.outputs["Tangent"])
    heading = g.atan2(ty, tx)
    px, py, _pz = g.split(sample.outputs["Position"])
    pts = g.set_pos(pts, position=g.xyz(px, py, 0.0))
    pts = g.store(pts, "oc_rot", heading, domain="POINT")
    cars = g.group(scatter, Geometry=pts)
    # one spot per car, low at the front and dipped a little
    beam = g.transform(_light(g, lights.HEADLIGHT), translation=(2.1, 0.0, 0.75),
                       rotation=g.euler(0.0, -math.radians(78), 0.0))
    beams = g.instance(pts, beam, rotation=g.euler(0.0, 0.0, heading))
    return G.finish(Geometry=g.join(g.gout(cars), beams))


def group_names():
    names = [parts.CBOX, SCATTER, TRAFFIC]
    names += [n for n, _f in openings.BASE + openings.ADDONS]
    names += [roofs.GABLE, roofs.HIP, roofs.MANSARD, roofs.DORMER, roofs.CHIMNEY, *roofs.ROOFTOP]
    for mod in PROP_MODULES:
        names += [name for _key, name, _fn in mod.PROPS]
    return names
