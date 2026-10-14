# SPDX-License-Identifier: GPL-3.0-or-later
"""Roof modules: gable, hip and mansard roofs, dormers, chimneys and rooftop equipment.

Roofs are convex hulls of a few points, so they are built to the exact footprint (never scaled) and
get clean, flat-shaded planes. They are written in a local frame with the ridge along X, centred on the
origin; the building turns and places them. Faces that look up get roof tiles, the rest trim.
"""

import math

from ..gn import Group
from .parts import Kit, V, val, vmax, vmin, xyz

GABLE, HIP, MANSARD, DORMER, CHIMNEY = (
    "OC Kit Roof Gable", "OC Kit Roof Hip", "OC Kit Roof Mansard", "OC Kit Dormer", "OC Kit Chimney")
ROOFTOP = ("OC Kit Rooftop AC", "OC Kit Rooftop Vents", "OC Kit Rooftop Hatch", "OC Kit Rooftop Skylight")

SLAB = 0.18   # roof thickness


def _tiles_or_trim(k, geo):
    """Roof tiles on faces that look up, trim on fascias and soffits."""
    g = k.g
    geo = k.paint(geo, "OC Trim")
    _nx, _ny, nz = g.split(g.normal())
    return k.paint(geo, "OC Roof Tiles", selection=g.gt(nz, 0.25))


def _hull(k, pts):
    g = k.g
    return g.hull(g.join(*[g.points(1, xyz(*p)) for p in pts]))


def build_gable():
    G = Group(GABLE, [("Length", "float"), ("Span", "float"), ("Base", "float"), ("Pitch", "float"),
                      ("Overhang", "float"), ("End L", "float"), ("End R", "float")],
              [("Roof", "geometry"), ("Gable", "geometry"), ("Top", "float")])
    g, i = G.g, G.i
    k = Kit(g)
    L, S, base, ov = V(i("Length")), V(i("Span")), V(i("Base")), V(i("Overhang"))
    s = V(g.math("TANGENT", g.math("RADIANS", i("Pitch"))))
    x0, x1 = -L / 2 - V(i("End L")), L / 2 + V(i("End R"))
    ridge = base + S / 2 * s
    eave = base - ov * s
    slabs = []
    for side in (-1.0, 1.0):
        ye = (S / 2 + ov) * side
        pts = []
        for x in (x0, x1):
            pts += [(x, ye, eave), (x, ye, eave + SLAB), (x, 0.0, ridge), (x, 0.0, ridge + SLAB)]
        slabs.append(_hull(k, pts))
    roof = _tiles_or_trim(k, g.join(*slabs))
    cap = k.paint(k.raw_box(x0 - 0.05, x1 + 0.05, -0.14, 0.14, ridge + SLAB - 0.06, ridge + SLAB + 0.12, 0.03),
                  "OC Roof Tiles")
    # gutters along both eaves
    gut = []
    for side in (-1.0, 1.0):
        ye = (S / 2 + ov) * side
        gut.append(k.raw_box(x0, x1, ye - 0.09, ye + 0.09, eave - 0.1, eave + 0.04))
    gutters = k.paint(g.join(*gut), "OC Metal")
    gable = _hull(k, [(-L / 2, -S / 2, base - 0.35), (L / 2, -S / 2, base - 0.35), (-L / 2, S / 2, base - 0.35),
                      (L / 2, S / 2, base - 0.35), (-L / 2, 0.0, ridge - 0.02), (L / 2, 0.0, ridge - 0.02)])
    return G.finish(Roof=g.join(roof, cap, gutters), Gable=gable, Top=val(ridge + SLAB + 0.12))


def build_hip():
    G = Group(HIP, [("Length", "float"), ("Span", "float"), ("Base", "float"), ("Pitch", "float"),
                    ("Overhang", "float")], [("Roof", "geometry"), ("Top", "float")])
    g, i = G.g, G.i
    k = Kit(g)
    L, S, base, ov = V(i("Length")), V(i("Span")), V(i("Base")), V(i("Overhang"))
    s = V(g.math("TANGENT", g.math("RADIANS", i("Pitch"))))
    rx, ry = vmax(L - S, 0.0) / 2, vmax(S - L, 0.0) / 2
    rise = vmin(L, S) / 2 * s
    eave = base - ov * s
    ex, ey = L / 2 + ov, S / 2 + ov
    pts = []
    for x in (-1.0, 1.0):
        for y in (-1.0, 1.0):
            pts += [(ex * x, ey * y, eave - 0.02), (ex * x, ey * y, eave + SLAB),
                    (rx * x, ry * y, base + rise + SLAB)]
    roof = _tiles_or_trim(k, _hull(k, pts))
    gut = [k.raw_box(-ex, ex, -ey - 0.09, -ey + 0.09, eave - 0.1, eave + 0.04),
           k.raw_box(-ex, ex, ey - 0.09, ey + 0.09, eave - 0.1, eave + 0.04)]
    G.finish(Roof=g.join(roof, k.paint(g.join(*gut), "OC Metal")), Top=val(base + rise + SLAB))
    return G.tree


def build_mansard():
    G = Group(MANSARD, [("Length", "float"), ("Span", "float"), ("Base", "float"), ("Height", "float"),
                        ("Inset", "float")], [("Roof", "geometry"), ("Top", "float")])
    g, i = G.g, G.i
    k = Kit(g)
    L, S, base, h, m = V(i("Length")), V(i("Span")), V(i("Base")), V(i("Height")), V(i("Inset"))
    bx, by = L / 2 + 0.1, S / 2 + 0.1
    ux, uy = L / 2 - m, S / 2 - m
    rx, ry = vmax(ux - uy, 0.0), vmax(uy - ux, 0.0)
    top = base + h + 0.45
    pts = []
    for x in (-1.0, 1.0):
        for y in (-1.0, 1.0):
            pts += [(bx * x, by * y, base - 0.05), (ux * x, uy * y, base + h), (rx * x, ry * y, top)]
    roof = _tiles_or_trim(k, _hull(k, pts))
    curb = []
    for y in (-1.0, 1.0):
        curb.append(k.raw_box(-ux - 0.12, ux + 0.12, uy * y - 0.12, uy * y + 0.12, base + h - 0.08,
                              base + h + 0.08, 0.02))
    for x in (-1.0, 1.0):
        curb.append(k.raw_box(ux * x - 0.12, ux * x + 0.12, -uy, uy, base + h - 0.08, base + h + 0.08, 0.02))
    G.finish(Roof=g.join(roof, k.paint(g.join(*curb), "OC Trim")), Top=val(top))
    return G.tree


def build_dormer():
    """A small gabled dormer, front face at y = 0 facing -Y, sitting on z = 0."""
    G = Group(DORMER, [], [("Geometry", "geometry")])
    k = Kit(G.g)
    from .openings import bars, frame, glass
    w, d, h = 0.66, 1.5, 1.35
    k.box(-w, w, -0.02, d, 0.0, h, "OC Trim", 0.02)
    glass(k, -0.36, 0.36, 0.28, 1.08)
    frame(k, -0.36, 0.36, 0.28, 1.08, t=0.08, d=0.1)
    bars(k, -0.36, 0.36, 0.28, 1.08, 2, 2, w=0.04)
    k.box(-0.5, 0.5, -0.18, 0.02, 0.12, 0.2, "OC Trim", 0.02)
    roof = _hull(k, [(-w - 0.14, -0.16, h - 0.04), (w + 0.14, -0.16, h - 0.04), (-w - 0.14, d, h - 0.04),
                     (w + 0.14, d, h - 0.04), (-w - 0.14, -0.16, h + 0.08), (w + 0.14, -0.16, h + 0.08),
                     (0.0, -0.16, h + 0.55), (0.0, d, h + 0.55), (0.0, -0.16, h + 0.42)])
    k.add(_tiles_or_trim(k, roof))
    return G.finish(Geometry=k.result())


def build_chimney():
    G = Group(CHIMNEY, [("Height", "float", {"default": 2.0})], [("Geometry", "geometry")])
    k = Kit(G.g)
    h = V(G.i("Height"))
    k.box(-0.38, 0.38, -0.28, 0.28, 0.0, h, "OC Brick", 0.015)
    k.box(-0.46, 0.46, -0.36, 0.36, h - 0.12, h + 0.02, "OC Trim", 0.025)
    k.box(-0.42, 0.42, -0.32, 0.32, h - 0.32, h - 0.24, "OC Trim", 0.015)
    for x in (-0.17, 0.17):
        k.cyl(0.09, 0.32, xyz(x, 0.0, h + 0.02), "OC Brick", verts=8)
    return G.finish(Geometry=k.result())


def build_rooftop():
    """Four pieces of rooftop clutter, all standing on z = 0."""
    trees = []
    # air conditioning unit with a fan grille
    G = Group(ROOFTOP[0], [], [("Geometry", "geometry")])
    k = Kit(G.g)
    k.box(-0.55, 0.55, -0.42, 0.42, 0.0, 0.12, "OC Metal", 0.01)
    k.box(-0.5, 0.5, -0.38, 0.38, 0.12, 0.82, "OC Concrete", 0.04)
    k.cyl(0.3, 0.04, (0.0, 0.0, 0.82), "OC Metal", verts=16)
    k.box(-0.52, -0.46, -0.3, 0.3, 0.2, 0.7, "OC Metal")
    trees.append(G.finish(Geometry=k.result()))
    # vent stacks
    G = Group(ROOFTOP[1], [], [("Geometry", "geometry")])
    k = Kit(G.g)
    for x, y, h in ((0.0, 0.0, 0.9), (0.45, 0.2, 0.6), (-0.3, 0.35, 0.5)):
        k.cyl(0.11, h, (x, y, 0.0), "OC Metal", verts=10)
        k.cyl(0.17, 0.08, (x, y, h), "OC Metal", verts=10)
    trees.append(G.finish(Geometry=k.result()))
    # roof hatch
    G = Group(ROOFTOP[2], [], [("Geometry", "geometry")])
    k = Kit(G.g)
    k.box(-0.5, 0.5, -0.5, 0.5, 0.0, 0.4, "OC Concrete", 0.03)
    k.box(-0.55, 0.55, -0.55, 0.55, 0.4, 0.48, "OC Metal", 0.02)
    trees.append(G.finish(Geometry=k.result()))
    # skylight
    G = Group(ROOFTOP[3], [], [("Geometry", "geometry")])
    k = Kit(G.g)
    k.box(-0.7, 0.7, -0.55, 0.55, 0.0, 0.3, "OC Trim", 0.03)
    roof = _hull(k, [(-0.62, -0.47, 0.3), (0.62, -0.47, 0.3), (-0.62, 0.47, 0.3), (0.62, 0.47, 0.3),
                     (-0.4, 0.0, 0.75), (0.4, 0.0, 0.75)])
    k.add(roof, "OC Glass")
    trees.append(G.finish(Geometry=k.result()))
    return trees


def build_all():
    return {GABLE: build_gable(), HIP: build_hip(), MANSARD: build_mansard(), DORMER: build_dormer(),
            CHIMNEY: build_chimney(), **dict(zip(ROOFTOP, build_rooftop()))}


PITCH_DEFAULT = math.radians(35)
