# SPDX-License-Identifier: GPL-3.0-or-later
"""Street furniture: lamps, benches, bins, mailboxes, hydrants, bollards, signs, traffic lights, a bus
shelter, bike racks, cafe sets, sandwich boards and planters.

Every prop stands on z = 0 at its origin with its front facing -Y, at real-world size, so the placement
rules can put it anywhere with one position and one angle.
"""

import math

from ..gn import Group
from .parts import Kit


def _prop(name, build):
    G = Group(name, [], [("Geometry", "geometry")])
    k = Kit(G.g)
    build(k)
    return G.finish(Geometry=k.result())


def _stand_x(k, geo):
    """Turn a mesh made along Z so it lies along Y (faces -Y)."""
    return k.g.transform(geo, rotation=k.g.euler(math.pi / 2, 0.0, 0.0))


def street_lamp(k):
    k.cyl(0.2, 0.18, (0, 0, 0), "OC Iron", 10)
    k.cyl(0.14, 0.55, (0, 0, 0.18), "OC Iron", 10)
    k.cyl(0.075, 3.4, (0, 0, 0.7), "OC Iron", 8)
    k.cyl(0.11, 0.08, (0, 0, 1.4), "OC Iron", 8)
    k.cyl(0.1, 0.12, (0, 0, 4.05), "OC Iron", 8)
    # the lantern: glass between a base and a cap
    k.box(-0.18, 0.18, -0.18, 0.18, 4.15, 4.24, "OC Iron", 0.02)
    k.box(-0.15, 0.15, -0.15, 0.15, 4.24, 4.66, "OC Lamp Glow", 0.01)
    for x in (-0.16, 0.16):
        for y in (-0.16, 0.16):
            k.box(x - 0.02, x + 0.02, y - 0.02, y + 0.02, 4.24, 4.66, "OC Iron")
    cap = k.g.out("GeometryNodeMeshCone", {"Vertices": 4, "Radius Top": 0.05, "Radius Bottom": 0.32,
                                           "Depth": 0.26}, output="Mesh")
    k.add(k.g.transform(cap, translation=(0, 0, 4.66), rotation=k.g.euler(0, 0, math.pi / 4)), "OC Iron")
    k.ico(0.06, (0, 0, 5.0), "OC Iron")


def park_lamp(k):
    k.cyl(0.13, 0.3, (0, 0, 0), "OC Iron", 8)
    k.cyl(0.055, 2.6, (0, 0, 0.3), "OC Iron", 8)
    k.cyl(0.1, 0.08, (0, 0, 2.9), "OC Iron", 8)
    k.ico(0.24, (0, 0, 3.18), "OC Lamp Glow", subdiv=2)


def bench(k):
    for i in range(3):
        y = -0.2 + i * 0.15
        k.box(-0.85, 0.85, y - 0.06, y + 0.06, 0.44, 0.49, "OC Wood", 0.012)
    for i in range(2):
        z = 0.62 + i * 0.17
        k.box(-0.85, 0.85, 0.15, 0.2, z, z + 0.11, "OC Wood", 0.012)
    for x in (-0.68, 0.68):
        k.box(x - 0.04, x + 0.04, -0.24, -0.18, 0.0, 0.46, "OC Iron")
        k.box(x - 0.04, x + 0.04, 0.12, 0.2, 0.0, 0.92, "OC Iron")
        k.box(x - 0.04, x + 0.04, -0.27, 0.2, 0.4, 0.44, "OC Iron")
        k.box(x - 0.035, x + 0.035, -0.25, -0.18, 0.55, 0.6, "OC Iron")


def trash_bin(k):
    k.cyl(0.24, 0.78, (0, 0, 0.04), "OC Prop Green", 12)
    k.cyl(0.26, 0.06, (0, 0, 0.0), "OC Iron", 12)
    k.cyl(0.27, 0.08, (0, 0, 0.8), "OC Iron", 12)
    k.add(k.g.transform(k.g.out("GeometryNodeMeshIcoSphere", {"Radius": 0.25, "Subdivisions": 1}, output="Mesh"),
                        translation=(0, 0, 0.86), scale=(1.0, 1.0, 0.35)), "OC Prop Green")
    for a in range(6):
        x, y = 0.245 * math.cos(a * math.pi / 3), 0.245 * math.sin(a * math.pi / 3)
        k.box(x - 0.025, x + 0.025, y - 0.025, y + 0.025, 0.1, 0.78, "OC Iron")


def mailbox(k):
    for x in (-0.15, 0.15):
        k.box(x - 0.04, x + 0.04, -0.12, 0.12, 0.0, 0.42, "OC Prop Blue")
    k.box(-0.24, 0.24, -0.22, 0.22, 0.42, 1.05, "OC Prop Blue", 0.03)
    top = k.g.out("GeometryNodeMeshCylinder", {"Vertices": 16, "Radius": 0.22, "Depth": 0.48}, output="Mesh")
    top = k.g.transform(top, rotation=k.g.euler(0, math.pi / 2, 0), translation=(0, 0, 1.05))
    k.add(top, "OC Prop Blue")
    k.box(-0.14, 0.14, -0.235, -0.2, 0.92, 0.98, "OC Iron")
    k.box(-0.1, 0.1, -0.235, -0.22, 0.6, 0.72, "OC Prop White")


def hydrant(k):
    k.cyl(0.15, 0.08, (0, 0, 0), "OC Prop Red", 10)
    k.cyl(0.12, 0.52, (0, 0, 0.08), "OC Prop Red", 10)
    k.cyl(0.15, 0.06, (0, 0, 0.5), "OC Prop Red", 10)
    k.add(k.g.transform(k.g.out("GeometryNodeMeshIcoSphere", {"Radius": 0.12, "Subdivisions": 1}, output="Mesh"),
                        translation=(0, 0, 0.58)), "OC Prop Red")
    k.cyl(0.03, 0.08, (0, 0, 0.68), "OC Chrome", 6)
    for s in (-1, 1):
        nz = k.g.out("GeometryNodeMeshCylinder", {"Vertices": 8, "Radius": 0.055, "Depth": 0.14}, output="Mesh")
        k.add(k.g.transform(nz, rotation=k.g.euler(0, math.pi / 2, 0), translation=(0.15 * s, 0, 0.38)), "OC Chrome")
    nz = k.g.out("GeometryNodeMeshCylinder", {"Vertices": 8, "Radius": 0.07, "Depth": 0.12}, output="Mesh")
    k.add(k.g.transform(nz, rotation=k.g.euler(math.pi / 2, 0, 0), translation=(0, -0.15, 0.36)), "OC Prop Red")


def bollard(k):
    k.cyl(0.1, 0.82, (0, 0, 0), "OC Iron", 10)
    k.cyl(0.12, 0.06, (0, 0, 0.62), "OC Chrome", 10)
    k.add(k.g.transform(k.g.out("GeometryNodeMeshIcoSphere", {"Radius": 0.1, "Subdivisions": 1}, output="Mesh"),
                        translation=(0, 0, 0.82), scale=(1, 1, 0.6)), "OC Iron")


def stop_sign(k):
    g = k.g
    k.cyl(0.04, 2.5, (0, 0, 0), "OC Metal", 6)
    for r, d, y, mat in ((0.36, 0.02, 0.0, "OC Prop White"), (0.33, 0.02, -0.012, "OC Prop Red")):
        o = g.out("GeometryNodeMeshCylinder", {"Vertices": 8, "Radius": r, "Depth": d}, output="Mesh")
        o = g.transform(o, rotation=g.euler(math.pi / 2, 0, math.pi / 8), translation=(0, -0.05 + y, 2.3))
        k.add(o, mat)
    k.box(-0.2, 0.2, -0.075, -0.07, 2.27, 2.33, "OC Prop White")


def street_sign(k):
    k.cyl(0.045, 3.0, (0, 0, 0), "OC Iron", 6)
    k.box(-0.5, 0.5, -0.02, 0.02, 2.72, 2.92, "OC Prop Green", 0.01)
    k.box(-0.02, 0.02, -0.5, 0.5, 2.48, 2.68, "OC Prop Green", 0.01)
    k.box(-0.42, 0.42, -0.025, 0.025, 2.79, 2.85, "OC Prop White")
    k.box(-0.025, 0.025, -0.42, 0.42, 2.55, 2.61, "OC Prop White")
    k.ico(0.06, (0, 0, 3.02), "OC Iron")


def traffic_light(k):
    g = k.g
    k.cyl(0.16, 0.3, (0, 0, 0), "OC Iron", 8)
    k.cyl(0.07, 3.3, (0, 0, 0.3), "OC Iron", 8)
    k.box(-0.17, 0.17, -0.16, 0.14, 2.45, 3.4, "OC Iron", 0.03)
    for z, mat in ((3.15, "OC Prop Red"), (2.92, "OC Prop Yellow"), (2.69, "OC Lamp Glow")):
        lens = g.out("GeometryNodeMeshCylinder", {"Vertices": 12, "Radius": 0.085, "Depth": 0.04}, output="Mesh")
        k.add(g.transform(lens, rotation=g.euler(math.pi / 2, 0, 0), translation=(0, -0.17, z)), mat)
        k.box(-0.11, 0.11, -0.3, -0.16, z + 0.08, z + 0.1, "OC Iron")
    k.box(-0.11, 0.11, -0.04, 0.12, 1.15, 1.42, "OC Prop Yellow", 0.02)


def bus_shelter(k):
    w, d, h = 1.9, 0.75, 2.45
    for x in (-w, w):
        for y in (-d, d):
            k.box(x - 0.05, x + 0.05, y - 0.05, y + 0.05, 0.0, h, "OC Prop Blue")
    k.box(-w - 0.15, w + 0.15, -d - 0.25, d + 0.15, h, h + 0.12, "OC Prop Blue", 0.03)
    k.box(-w - 0.1, w + 0.1, -d - 0.2, d + 0.1, h + 0.12, h + 0.16, "OC Prop White", 0.01)
    k.box(-w, w, d - 0.02, d + 0.02, 0.15, h - 0.1, "OC Car Glass")
    for x in (-w, w):
        k.box(x - 0.02, x + 0.02, -d + 0.2, d, 0.15, h - 0.1, "OC Car Glass")
    k.box(-1.4, 1.4, 0.25, 0.65, 0.45, 0.5, "OC Wood", 0.01)
    for x in (-1.2, 1.2):
        k.box(x - 0.04, x + 0.04, 0.35, 0.55, 0.0, 0.45, "OC Iron")
    k.box(w - 0.1, w + 0.1, -d - 0.3, -d - 0.26, 1.6, 2.2, "OC Prop Yellow", 0.01)


def bike_rack(k):
    for x in (-0.9, -0.3, 0.3, 0.9):
        k.box(x - 0.025, x + 0.025, -0.4, -0.35, 0.0, 0.8, "OC Chrome")
        k.box(x - 0.025, x + 0.025, 0.35, 0.4, 0.0, 0.8, "OC Chrome")
        k.box(x - 0.025, x + 0.025, -0.4, 0.4, 0.75, 0.8, "OC Chrome")


def cafe_table(k):
    """A round bistro table with two chairs."""
    k.cyl(0.36, 0.04, (0, 0, 0.72), "OC Prop White", 16)
    k.cyl(0.035, 0.72, (0, 0, 0), "OC Iron", 6)
    k.cyl(0.2, 0.03, (0, 0, 0), "OC Iron", 10)
    for s in (-1, 1):
        y = 0.62 * s
        k.box(-0.21, 0.21, y - 0.21, y + 0.21, 0.44, 0.48, "OC Wood", 0.01)
        k.box(-0.21, 0.21, y + 0.17 * s - 0.03, y + 0.17 * s + 0.03, 0.48, 0.9, "OC Wood", 0.01)
        for x in (-0.17, 0.17):
            for yy in (-0.17, 0.17):
                k.box(x - 0.02, x + 0.02, y + yy - 0.02, y + yy + 0.02, 0.0, 0.44, "OC Iron")


def cafe_set(k):
    """The table and chairs under a parasol."""
    cafe_table(k)
    k.cyl(0.03, 2.3, (0, 0, 0.74), "OC Wood", 6)
    shade = k.g.out("GeometryNodeMeshCone", {"Vertices": 8, "Radius Top": 0.06, "Radius Bottom": 1.0,
                                             "Depth": 0.4}, output="Mesh")
    k.add(k.g.transform(shade, translation=(0, 0, 2.2)), "OC Fabric")


def sandwich_board(k):
    for s in (-1, 1):
        k.hull([(-0.3, 0.02 * s, 1.0), (0.3, 0.02 * s, 1.0), (-0.3, 0.02 * s + 0.03 * s, 1.0),
                (0.3, 0.02 * s + 0.03 * s, 1.0), (-0.3, 0.3 * s, 0.0), (0.3, 0.3 * s, 0.0),
                (-0.3, 0.33 * s, 0.0), (0.3, 0.33 * s, 0.0)], "OC Wood")
    k.hull([(-0.24, -0.03, 0.9), (0.24, -0.03, 0.9), (-0.24, -0.29, 0.12), (0.24, -0.29, 0.12),
            (-0.24, -0.045, 0.9), (0.24, -0.045, 0.9), (-0.24, -0.305, 0.12), (0.24, -0.305, 0.12)],
           "OC Iron")
    k.box(-0.15, 0.15, -0.21, -0.19, 0.55, 0.58, "OC Prop White")


def planter(k):
    k.box(-0.55, 0.55, -0.25, 0.25, 0.0, 0.5, "OC Wood", 0.03)
    k.box(-0.5, 0.5, -0.2, 0.2, 0.46, 0.5, "OC Soil")
    for x in (-0.3, 0.0, 0.3):
        k.ico(0.26, (x, 0.0, 0.66), "OC Leaves", scale=(1.0, 0.85, 0.8))
    for i in range(7):
        x = -0.4 + 0.8 * ((i * 0.618) % 1.0)
        y = -0.12 + 0.24 * ((i * 0.37) % 1.0)
        k.ico(0.05, (x, y, 0.84 + 0.05 * ((i * 0.53) % 1.0)), "OC Flowers")


def potted_plant(k):
    pot = k.g.out("GeometryNodeMeshCone", {"Vertices": 10, "Radius Top": 0.26, "Radius Bottom": 0.18,
                                           "Depth": 0.5}, output="Mesh")
    k.add(pot, "OC Brick")
    k.cyl(0.27, 0.06, (0, 0, 0.48), "OC Brick", 10)
    k.cyl(0.03, 0.4, (0, 0, 0.5), "OC Trunk", 5)
    k.ico(0.36, (0, 0, 1.12), "OC Leaves", subdiv=2)


PROPS = [
    ("lamp", "OC Prop Street Lamp", street_lamp),
    ("park_lamp", "OC Prop Park Lamp", park_lamp),
    ("bench", "OC Prop Bench", bench),
    ("bin", "OC Prop Bin", trash_bin),
    ("mailbox", "OC Prop Mailbox", mailbox),
    ("hydrant", "OC Prop Hydrant", hydrant),
    ("bollard", "OC Prop Bollard", bollard),
    ("stop_sign", "OC Prop Stop Sign", stop_sign),
    ("street_sign", "OC Prop Street Sign", street_sign),
    ("traffic_light", "OC Prop Traffic Light", traffic_light),
    ("bus_shelter", "OC Prop Bus Shelter", bus_shelter),
    ("bike_rack", "OC Prop Bike Rack", bike_rack),
    ("cafe_set", "OC Prop Cafe Set", cafe_set),
    ("cafe_table", "OC Prop Cafe Table", cafe_table),
    ("sandwich_board", "OC Prop Sandwich Board", sandwich_board),
    ("planter", "OC Prop Planter", planter),
    ("potted_plant", "OC Prop Potted Plant", potted_plant),
]


def build_all():
    return [(key, _prop(name, fn)) for key, name, fn in PROPS]
