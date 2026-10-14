# SPDX-License-Identifier: GPL-3.0-or-later
"""Nature and landscaping: low-poly trees with different silhouettes, shrubs, hedge and fence
segments, flower beds, tree grates and a fountain.

Crowns are clusters of faceted icospheres (the look of the references). Each instance gets its own
leaf tone from `oc_tint`, so a row of the same tree still varies.
"""

import math

from ..gn import Group
from .parts import Kit


def _prop(name, build):
    G = Group(name, [], [("Geometry", "geometry")])
    k = Kit(G.g)
    build(k)
    return G.finish(Geometry=k.result())


def _trunk(k, h, r0=0.17, r1=0.11):
    t = k.g.out("GeometryNodeMeshCone", {"Vertices": 7, "Radius Bottom": r0, "Radius Top": r1, "Depth": h},
                output="Mesh")
    k.add(t, "OC Trunk")


def tree_round(k):
    _trunk(k, 2.6)
    for (x, y, z, r) in ((0.0, 0.0, 3.4, 1.45), (0.85, 0.3, 3.0, 1.05), (-0.8, -0.35, 3.05, 1.1),
                         (0.2, -0.8, 3.2, 1.0), (-0.3, 0.75, 3.3, 1.0), (0.1, 0.1, 4.3, 1.05)):
        k.ico(r, (x, y, z), "OC Leaves", scale=(1.0, 1.0, 0.92))
    for (x, y, z, a) in ((0.25, 0.0, 2.3, 0.6), (-0.2, 0.1, 2.5, -0.7)):
        br = k.g.out("GeometryNodeMeshCylinder", {"Vertices": 5, "Radius": 0.06, "Depth": 0.9}, output="Mesh")
        k.add(k.g.transform(br, rotation=k.g.euler(0.0, a, 0.0), translation=(x, y, z)), "OC Trunk")


def tree_tall(k):
    _trunk(k, 2.0, 0.15, 0.1)
    for (z, r, s) in ((2.6, 0.95, 1.2), (3.8, 0.9, 1.25), (5.0, 0.7, 1.2), (5.9, 0.45, 1.1)):
        k.ico(r, (0.0, 0.0, z), "OC Leaves", scale=(1.0, 1.0, s))


def tree_pine(k):
    _trunk(k, 1.4, 0.16, 0.12)
    for (z, r, h) in ((1.1, 1.5, 2.0), (2.2, 1.2, 1.8), (3.2, 0.9, 1.6), (4.1, 0.55, 1.4)):
        c = k.g.out("GeometryNodeMeshCone", {"Vertices": 8, "Radius Top": 0.0, "Radius Bottom": r, "Depth": h},
                    output="Mesh")
        k.add(k.g.transform(c, translation=(0, 0, z)), "OC Leaves")


def shrub(k):
    for (x, y, z, r) in ((0.0, 0.0, 0.42, 0.5), (0.4, 0.15, 0.32, 0.38), (-0.38, -0.1, 0.33, 0.4),
                         (0.05, -0.35, 0.3, 0.34)):
        k.ico(r, (x, y, z), "OC Leaves", scale=(1.0, 1.0, 0.85))


def hedge(k):
    """One metre of hedge (placed in segments, so the lumps never stretch far)."""
    k.box(-0.52, 0.52, -0.36, 0.36, 0.0, 0.82, "OC Leaves", 0.12)
    for x in (-0.3, 0.25):
        k.ico(0.34, (x, 0.0, 0.84), "OC Leaves", scale=(1.0, 1.0, 0.55))


def flower_bed(k):
    """A one-metre raised bed; placed in rows."""
    k.box(-0.5, 0.5, -0.5, 0.5, 0.0, 0.28, "OC Curb", 0.03)
    k.box(-0.42, 0.42, -0.42, 0.42, 0.2, 0.3, "OC Soil")
    for i in range(6):
        x = -0.28 + 0.56 * ((i * 0.618) % 1.0)
        y = -0.28 + 0.56 * ((i * 0.381) % 1.0)
        k.ico(0.17, (x, y, 0.38), "OC Leaves", scale=(1.0, 1.0, 0.75))
    for i in range(12):
        x = -0.36 + 0.72 * ((i * 0.618 + 0.1) % 1.0)
        y = -0.36 + 0.72 * ((i * 0.7548) % 1.0)
        k.ico(0.06, (x, y, 0.5 + 0.06 * ((i * 0.53) % 1.0)), "OC Flowers")


def fence(k):
    """Two metres of white picket fence."""
    k.box(-1.0, 1.0, -0.02, 0.02, 0.25, 0.32, "OC Prop White")
    k.box(-1.0, 1.0, -0.02, 0.02, 0.65, 0.72, "OC Prop White")
    for i in range(10):
        x = -0.9 + i * 0.2
        k.hull([(x - 0.04, -0.04, 0.0), (x + 0.04, -0.04, 0.0), (x - 0.04, -0.01, 0.0), (x + 0.04, -0.01, 0.0),
                (x - 0.04, -0.04, 0.88), (x + 0.04, -0.04, 0.88), (x - 0.04, -0.01, 0.88),
                (x + 0.04, -0.01, 0.88), (x, -0.04, 0.96), (x, -0.01, 0.96)], "OC Prop White")


def tree_grate(k):
    k.box(-0.65, 0.65, -0.65, 0.65, 0.0, 0.03, "OC Iron")
    k.box(-0.5, 0.5, -0.5, 0.5, 0.0, 0.045, "OC Soil")


def fountain(k):
    g = k.g
    k.cyl(2.3, 0.55, (0, 0, 0), "OC Concrete", 24)
    k.cyl(2.45, 0.1, (0, 0, 0.5), "OC Curb", 24)
    k.cyl(2.08, 0.05, (0, 0, 0.42), "OC Water", 24)
    k.cyl(0.34, 1.5, (0, 0, 0.45), "OC Concrete", 10)
    bowl = g.out("GeometryNodeMeshCone", {"Vertices": 16, "Radius Bottom": 0.3, "Radius Top": 1.0,
                                          "Depth": 0.35}, output="Mesh")
    k.add(g.transform(bowl, translation=(0, 0, 1.75)), "OC Concrete")
    k.cyl(0.92, 0.04, (0, 0, 2.06), "OC Water", 16)
    k.cyl(0.14, 0.7, (0, 0, 2.05), "OC Concrete", 8)
    k.ico(0.2, (0, 0, 2.85), "OC Water", scale=(1.0, 1.0, 1.4), subdiv=2)
    jet = g.out("GeometryNodeMeshCone", {"Vertices": 10, "Radius Bottom": 0.62, "Radius Top": 0.12,
                                         "Depth": 0.7}, output="Mesh")
    k.add(g.transform(jet, translation=(0, 0, 1.9), scale=(1, 1, -1)), "OC Water")
    for a in range(8):
        x, y = 1.6 * math.cos(a * math.pi / 4), 1.6 * math.sin(a * math.pi / 4)
        k.ico(0.07, (x, y, 0.5), "OC Water")


PROPS = [
    ("tree_round", "OC Prop Tree Round", tree_round),
    ("tree_tall", "OC Prop Tree Tall", tree_tall),
    ("tree_pine", "OC Prop Tree Pine", tree_pine),
    ("shrub", "OC Prop Shrub", shrub),
    ("hedge", "OC Prop Hedge", hedge),
    ("flower_bed", "OC Prop Flower Bed", flower_bed),
    ("fence", "OC Prop Fence", fence),
    ("tree_grate", "OC Prop Tree Grate", tree_grate),
    ("fountain", "OC Prop Fountain", fountain),
]


def build_all():
    return [(key, _prop(name, fn)) for key, name, fn in PROPS]
