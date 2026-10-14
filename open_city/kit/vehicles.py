# SPDX-License-Identifier: GPL-3.0-or-later
"""Stylized vehicles: a hatchback, a sedan, a city car and a delivery van.

Cars point along +X (the front is at +X) and stand on z = 0. The body colour comes from the instance's
`oc_tint`, so one model gives a whole street of different cars. Proportions are slightly chunky, like
toys, but true to scale next to the buildings.
"""

import math

from ..gn import Group
from .parts import Kit


def _prop(name, build):
    G = Group(name, [], [("Geometry", "geometry")])
    k = Kit(G.g)
    build(k)
    return G.finish(Geometry=k.result())


def _wheels(k, xs, half_track, r=0.33, w=0.24):
    g = k.g
    for x in xs:
        for s in (-1, 1):
            y = half_track * s
            tyre = g.out("GeometryNodeMeshCylinder", {"Vertices": 14, "Radius": r, "Depth": w}, output="Mesh")
            k.add(g.transform(tyre, rotation=g.euler(math.pi / 2, 0, 0), translation=(x, y, r)), "OC Tyre")
            hub = g.out("GeometryNodeMeshCylinder", {"Vertices": 10, "Radius": r * 0.55, "Depth": 0.03}, output="Mesh")
            k.add(g.transform(hub, rotation=g.euler(math.pi / 2, 0, 0), translation=(x, y + (w / 2) * s, r)),
                  "OC Chrome")


def _cabin(k, x0, x1, top0, top1, z0, z1, half0, half1):
    """A glasshouse: a hull from the belt line (x0..x1) to the roof (top0..top1)."""
    k.hull([(x0, -half0, z0), (x1, -half0, z0), (x0, half0, z0), (x1, half0, z0),
            (top0, -half1, z1), (top1, -half1, z1), (top0, half1, z1), (top1, half1, z1)], "OC Car Glass")
    k.box(top0 - 0.02, top1 + 0.02, -half1 - 0.02, half1 + 0.02, z1 - 0.02, z1 + 0.07, "OC Car Paint", 0.03)


def _lights(k, front, back, z, half):
    for s in (-1, 1):
        y = (half - 0.22) * s
        k.box(front - 0.04, front + 0.02, y - 0.16, y + 0.16, z - 0.07, z + 0.07, "OC Lamp Glow", 0.02)
        k.box(back - 0.02, back + 0.04, y - 0.14, y + 0.14, z - 0.06, z + 0.06, "OC Rear Light", 0.02)


def hatchback(k):
    L, half = 1.95, 0.86
    k.box(-L, L, -half, half, 0.28, 0.98, "OC Car Paint", 0.14)
    _cabin(k, -1.85, 0.75, -1.7, 0.05, 0.96, 1.52, 0.82, 0.72)
    k.box(L - 0.06, L + 0.04, -0.75, 0.75, 0.3, 0.45, "OC Tyre", 0.03)
    k.box(-L - 0.04, -L + 0.06, -0.75, 0.75, 0.3, 0.45, "OC Tyre", 0.03)
    _lights(k, L + 0.02, -L - 0.02, 0.78, half)
    _wheels(k, (-1.25, 1.25), 0.78)


def sedan(k):
    L, half = 2.3, 0.88
    k.box(-L, L, -half, half, 0.28, 0.92, "OC Car Paint", 0.14)
    _cabin(k, -1.2, 0.95, -0.95, 0.35, 0.9, 1.45, 0.84, 0.74)
    k.box(L - 0.06, L + 0.04, -0.78, 0.78, 0.3, 0.45, "OC Tyre", 0.03)
    k.box(-L - 0.04, -L + 0.06, -0.78, 0.78, 0.3, 0.45, "OC Tyre", 0.03)
    _lights(k, L + 0.02, -L - 0.02, 0.74, half)
    _wheels(k, (-1.45, 1.45), 0.8)


def city_car(k):
    L, half = 1.6, 0.8
    k.box(-L, L, -half, half, 0.26, 1.0, "OC Car Paint", 0.16)
    _cabin(k, -1.5, 0.55, -1.4, -0.05, 0.98, 1.62, 0.76, 0.68)
    _lights(k, L + 0.02, -L - 0.02, 0.8, half)
    _wheels(k, (-1.0, 1.0), 0.72, r=0.3, w=0.22)


def van(k):
    L, half = 2.55, 1.0
    k.box(-L, L - 0.9, -half, half, 0.35, 2.45, "OC Car Paint", 0.1)
    k.box(L - 1.0, L, -half, half, 0.35, 1.25, "OC Car Paint", 0.12)
    k.hull([(L - 1.0, -0.95, 1.2), (L - 0.15, -0.95, 1.2), (L - 1.0, 0.95, 1.2), (L - 0.15, 0.95, 1.2),
            (L - 1.0, -0.9, 2.2), (L - 0.95, -0.9, 2.2), (L - 1.0, 0.9, 2.2), (L - 0.95, 0.9, 2.2)], "OC Car Glass")
    k.box(-L + 0.2, L - 1.2, -half - 0.01, half + 0.01, 1.2, 1.25, "OC Prop White")
    k.box(L - 0.05, L + 0.06, -0.9, 0.9, 0.35, 0.5, "OC Tyre", 0.03)
    _lights(k, L + 0.02, -L - 0.02, 0.85, half)
    _wheels(k, (-1.6, 1.55), 0.9, r=0.36, w=0.26)


PROPS = [
    ("hatchback", "OC Prop Hatchback", hatchback),
    ("sedan", "OC Prop Sedan", sedan),
    ("city_car", "OC Prop City Car", city_car),
    ("van", "OC Prop Van", van),
]


def build_all():
    return [(key, _prop(name, fn)) for key, name, fn in PROPS]
