# SPDX-License-Identifier: GPL-3.0-or-later
"""Facade modules: windows, French doors, storefronts, doors and the add-ons that stack on them.

Every module fills one facade slot (one bay wide, one floor tall) in the same local frame:

    x   along the wall, 0 at the middle of the bay
    y   out of the wall is NEGATIVE y; the wall surface is y = 0
    z   up from the bottom of the slot (from the street for ground-floor modules)

Modules read their sizes from the shared inputs (bay width, floor height, window size), so they are
rebuilt to fit rather than stretched, and add-ons (shutters, flower boxes, balconies, awnings) line up
with the window they belong to because they read the same numbers.
"""

import math

from ..gn import Group
from .parts import Kit, V, glass_attrs, val, vmax, vmin, xyz

MOD_INPUTS = [
    ("Bay", "float", {"default": 3.0}), ("Floor", "float", {"default": 3.0}),
    ("Ground", "float", {"default": 3.6}), ("Plinth", "float", {"default": 0.45}),
    ("Win W", "float", {"default": 1.25}), ("Win H", "float", {"default": 1.75}),
    ("Sill", "float", {"default": 0.65}), ("Detail", "float", {"default": 1.0}),
]

FRAME_T, FRAME_D = 0.11, 0.15   # architrave width and how far it stands proud of the wall
GLASS_Y = (-0.045, -0.025)      # the pane sits back in the frame


def _dims(i):
    return V(i("Bay")), V(i("Win W")), V(i("Win H")), V(i("Sill"))


def frame(k, x0, x1, z0, z1, t=FRAME_T, d=FRAME_D, mat="OC Trim", top=True, bottom=True):
    """Four bars around the opening [x0, x1] x [z0, z1]."""
    if top:
        k.box(V(x0) - t, V(x1) + t, -d, 0.02, z1, V(z1) + t, mat, 0.015)
    if bottom:
        k.box(V(x0) - t, V(x1) + t, -d, 0.02, V(z0) - t, z0, mat, 0.015)
    k.box(V(x0) - t, x0, -d, 0.02, z0, z1, mat, 0.015)
    k.box(x1, V(x1) + t, -d, 0.02, z0, z1, mat, 0.015)


def glass(k, x0, x1, z0, z1, shop=0.0):
    geo = k.raw_box(x0, x1, GLASS_Y[0], GLASS_Y[1], z0, z1)
    return k.add(glass_attrs(k.g, geo, x0, x1, z0, z1, shop), "OC Glass")


def bars(k, x0, x1, z0, z1, cols=2, rows=2, w=0.055, mat="OC Trim"):
    """Glazing bars: `cols` panes across and `rows` panes up."""
    x0, x1, z0, z1 = V(x0), V(x1), V(z0), V(z1)
    for c in range(1, cols):
        x = x0 + (x1 - x0) * (c / cols)
        k.box(x - w / 2, x + w / 2, -0.085, -0.02, z0, z1, mat)
    for r in range(1, rows):
        z = z0 + (z1 - z0) * (r / rows)
        k.box(x0, x1, -0.085, -0.02, z - w / 2, z + w / 2, mat)


def sill(k, ww, z, wide=0.22, mat="OC Trim", detail=None):
    k.box(-ww / 2 - wide, ww / 2 + wide, -0.27, 0.03, z - FRAME_T - 0.16, z - FRAME_T + 0.005, mat, 0.03)
    if detail is not None:
        def corbels():
            k.sym(ww / 2 - 0.02, ww / 2 + 0.12, -0.2, 0.03, z - FRAME_T - 0.4, z - FRAME_T - 0.16, mat, 0.02)
        k.when(V.g.gt(val(detail), 0.5), corbels)


def lintel(k, ww, z, detail):
    """A stone head over the window, with a keystone on detailed facades."""
    k.box(-ww / 2 - 0.2, ww / 2 + 0.2, -0.22, 0.03, z + FRAME_T, z + FRAME_T + 0.26, "OC Trim", 0.03)
    k.box(-ww / 2 - 0.26, ww / 2 + 0.26, -0.27, 0.03, z + FRAME_T + 0.26, z + FRAME_T + 0.33, "OC Trim", 0.02)
    k.when(V.g.gt(val(detail), 0.5),
           lambda: k.box(-0.12, 0.12, -0.28, 0.03, z + FRAME_T - 0.04, z + FRAME_T + 0.38, "OC Trim", 0.02))


# -- window assemblies ---------------------------------------------------------------------------------
def sash(k, ww, wh, zs, detail):
    """A tall two-by-two sash window with architrave, sill and lintel (reference: brick townhouses)."""
    x0, x1, z1 = -ww / 2, ww / 2, zs + wh
    glass(k, x0, x1, zs, z1)
    frame(k, x0, x1, zs, z1)
    bars(k, x0, x1, zs, z1, 2, 2)
    k.box(x0, x1, -0.1, -0.02, zs + wh * 0.5 - 0.045, zs + wh * 0.5 + 0.045, "OC Trim")  # meeting rail
    sill(k, ww, zs, detail=detail)
    lintel(k, ww, z1, detail)


def arched(k, ww, wh, zs, detail, ring=9):
    """A round-headed window under a ring of voussoirs with a keystone."""
    g = k.g
    r = ww / 2
    zr = zs + wh - r                 # spring line of the arch
    glass(k, -r, r, zs, zr)
    # the fan light: half a disc of glass
    disc = g.out("GeometryNodeMeshCircle", {"Vertices": 24, "Radius": val(r)}, output="Mesh",
                 fill_type="TRIANGLE_FAN")
    disc = g.transform(disc, rotation=g.euler(math.pi / 2, 0.0, 0.0))
    _x, _y, dz = g.split(g.position())
    disc = g.delete(disc, g.lt(dz, -0.001), domain="POINT")
    disc = g.transform(disc, translation=xyz(0.0, sum(GLASS_Y) / 2, zr))
    k.add(glass_attrs(g, disc, -r, r, zs, zs + wh), "OC Glass")
    frame(k, -r, r, zs, zr, top=False)
    bars(k, -r, r, zs, zr, 2, 2)
    # voussoirs on a half ring
    rm = r + 0.13
    idx = g.index()
    theta = g.mul(g.add(idx, 0.5), math.pi / ring)
    pts = g.points(ring, xyz(V(g.cos(theta)) * rm, -0.08, V(g.sin(theta)) * rm + zr))
    stone = k.raw_box(-(rm * (math.pi / ring) * 0.46), rm * (math.pi / ring) * 0.46, -0.08, 0.1, -0.13, 0.13,
                      bevel=0.02)
    rot = g.euler(0.0, g.sub(math.pi / 2, theta), 0.0)
    k.add(g.realize(g.instance(pts, stone, rotation=rot)), "OC Trim")
    k.box(-0.13, 0.13, -0.24, 0.03, zr + r - 0.02, zr + r + 0.34, "OC Trim", 0.02)   # keystone
    sill(k, ww, zs, detail=detail)


def wide(k, ww, wh, zs, detail):
    """A broad three-light casement in a deep box surround (colourful European facades)."""
    x0, x1, z1 = -ww / 2, ww / 2, zs + wh
    glass(k, x0, x1, zs, z1)
    frame(k, x0, x1, zs, z1, t=0.13, d=0.24)
    bars(k, x0, x1, zs, z1, 3, 1, w=0.07)
    k.box(x0, x1, -0.1, -0.02, z1 - wh * 0.26 - 0.035, z1 - wh * 0.26 + 0.035, "OC Trim")
    k.box(x0 - 0.2, x1 + 0.2, -0.3, 0.03, zs - 0.13 - 0.1, zs - 0.12, "OC Trim", 0.025)


def french(k, ww, wh, zs, detail):
    """A pair of glazed doors from the floor to the window head, for balconies."""
    x0, x1, z0, z1 = -ww / 2, ww / 2, V(0.08), zs + wh
    kick = z0 + 0.5
    glass(k, x0, x1, kick, z1)
    k.box(x0, x1, -0.07, 0.0, z0, kick, "OC Trim", 0.01)
    frame(k, x0, x1, z0, z1, bottom=False)
    bars(k, x0, x1, kick, z1, 2, 3)
    lintel(k, ww, z1, detail)


def small(k, ww, wh, zs, detail):
    """A small square window for side walls, backs and attics."""
    w = ww * 0.66
    h = vmin(wh * 0.55, 1.0)
    z1 = zs + wh
    z0 = z1 - h
    glass(k, -w / 2, w / 2, z0, z1)
    frame(k, -w / 2, w / 2, z0, z1, t=0.09, d=0.12)
    bars(k, -w / 2, w / 2, z0, z1, 2, 1)
    k.box(-w / 2 - 0.14, w / 2 + 0.14, -0.2, 0.03, z0 - 0.09 - 0.12, z0 - 0.085, "OC Trim", 0.02)


WINDOWS = (sash, arched, wide)        # by the building's Window Style


def _module(name, build, ground=False):
    G = Group(name, MOD_INPUTS, [("Geometry", "geometry")])
    i = G.i
    k = Kit(G.g)
    build(k, i)
    return G.finish(Geometry=k.result())


def ground_window_dims(i):
    """A ground-floor window sits higher, above the plinth, and is no taller than the floor allows."""
    P, Gh = V(i("Plinth")), V(i("Ground"))
    zs = P + 0.85
    wh = vmin(V(i("Win H")), Gh - 1.35)
    return zs, wh


# -- storefronts and doors ------------------------------------------------------------------------------
def piers(k, B, P, top):
    """Half piers at both edges of a shop bay: neighbouring bays complete each other's pier."""
    k.sym(B / 2 - 0.24, B / 2, -0.15, 0.02, P, top, "OC Trim", 0.02)
    k.sym(B / 2 - 0.27, B / 2, -0.19, 0.02, P, P + 0.32, "OC Stone", 0.02)
    k.sym(B / 2 - 0.28, B / 2, -0.21, 0.02, top - 0.14, top, "OC Trim", 0.02)


def shop_top(i):
    return V(i("Plinth")) + V(i("Ground")) - 0.98


def shop_window(k, i):
    B, P = V(i("Bay")), V(i("Plinth"))
    top = shop_top(i)
    piers(k, B, P, top)
    xi = B / 2 - 0.24
    k.box(-xi, xi, -0.1, 0.02, P, P + 0.55, "OC Accent", 0.02)              # stall riser
    k.box(-xi + 0.14, xi - 0.14, -0.13, -0.05, P + 0.1, P + 0.45, "OC Accent", 0.015)
    k.box(-xi - 0.02, xi + 0.02, -0.21, 0.02, P + 0.55, P + 0.65, "OC Trim", 0.02)
    gx = xi - 0.08
    g0, g1 = P + 0.65, top - 0.1
    glass(k, -gx, gx, g0, g1, shop=1.0)
    frame(k, -gx, gx, g0, g1, t=0.08, d=0.11, mat="OC Accent", bottom=False)
    tz = g1 - 0.45
    k.box(-gx, gx, -0.11, -0.02, tz - 0.04, tz + 0.04, "OC Accent")         # transom bar
    for f in (-1 / 3, 0.0, 1 / 3):
        x = gx * (2 * f)
        k.box(x - 0.025, x + 0.025, -0.1, -0.02, tz, g1, "OC Accent")


def shop_door(k, i):
    B, P = V(i("Bay")), V(i("Plinth"))
    top = shop_top(i)
    piers(k, B, P, top)
    dh = vmin(top - P - 0.55, 2.35)
    xi = B / 2 - 0.24
    # the door: a glazed leaf in a dark frame
    k.box(-0.5, 0.5, -0.06, 0.02, P, P + dh, "OC Accent", 0.02)
    glass(k, -0.36, 0.36, P + 0.85, P + dh - 0.18, shop=1.0)
    frame(k, -0.5, 0.5, P, P + dh, t=0.09, d=0.12, mat="OC Accent", bottom=False)
    k.box(0.28, 0.33, -0.16, -0.05, P + 0.95, P + 1.25, "OC Chrome")
    # side lights and the transom over everything
    k.sym(0.59, xi, -0.1, 0.02, P, P + 0.55, "OC Accent", 0.02)
    glass(k, 0.65, xi - 0.06, P + 0.6, P + dh, shop=1.0)
    glass(k, -(xi - 0.06), -0.65, P + 0.6, P + dh, shop=1.0)
    k.sym(xi - 0.08, xi, -0.11, 0.02, P + 0.55, top, "OC Accent")
    k.box(-xi, xi, -0.12, 0.02, P + dh + 0.09, P + dh + 0.17, "OC Accent")
    glass(k, -(xi - 0.06), xi - 0.06, P + dh + 0.17, top - 0.1, shop=1.0)
    k.box(-xi, xi, -0.11, 0.02, top - 0.1, top, "OC Accent")
    k.when(V.g.gt(val(P), 0.03), lambda: k.box(-0.8, 0.8, -0.45, 0.02, 0.0, P, "OC Stone", 0.02))


def _stoop(k, P, width=0.75, landing=0.75):
    """Front steps up to the door with sloping cheek walls (reference: brick townhouses)."""
    g = k.g
    n = vmax(V(g.math("CEIL", val(P / 0.18))), 1.0)
    rise = P / n
    k.box(-width, width, -landing, 0.02, 0.0, P, "OC Stone", 0.015)
    idx = g.index()
    j = V(g.add(idx, 1.0))
    top = P - rise * j
    pts = g.points(val(n - 1), xyz(0.0, -(V(landing) + (j - 0.5) * 0.3), top * 0.5))
    step = g.out("GeometryNodeMeshCube", {"Size": (1.0, 1.0, 1.0)}, output="Mesh")
    steps = g.realize(g.instance(pts, step, scale=xyz(width * 2, 0.3, top)))
    k.add(steps, "OC Stone")
    run = V(landing) + (n - 1) * 0.3
    for side in (-1.0, 1.0):
        xa, xb = side * (width + 0.02), side * (width + 0.22)
        k.hull([(xa, 0.02, 0.0), (xb, 0.02, 0.0), (xa, 0.02, P + 0.3), (xb, 0.02, P + 0.3),
                (xa, -run, 0.0), (xb, -run, 0.0), (xa, -run, 0.42), (xb, -run, 0.42)], "OC Concrete")


def wall_lamp(k, x, z):
    k.box(x - 0.03, x + 0.03, -0.32, 0.02, z + 0.22, z + 0.27, "OC Iron")
    k.box(x - 0.1, x + 0.1, -0.42, -0.22, z - 0.1, z + 0.2, "OC Lamp Glow", 0.02)
    k.box(x - 0.13, x + 0.13, -0.45, -0.19, z + 0.2, z + 0.27, "OC Iron", 0.02)
    k.box(x - 0.08, x + 0.08, -0.4, -0.24, z - 0.16, z - 0.1, "OC Iron", 0.01)


def res_door(k, i):
    """A panelled front door with transom, pilasters, a hood and a stoop."""
    P, Gh, detail = V(i("Plinth")), V(i("Ground")), V(i("Detail"))
    dh = vmin(Gh - 1.0, 2.35)
    k.when(V.g.gt(val(P), 0.08), lambda: _stoop(k, P))
    k.box(-0.52, 0.52, -0.05, 0.02, P, P + dh, "OC Accent", 0.02)
    k.box(-0.4, -0.04, -0.09, -0.03, P + 0.18, P + dh * 0.45, "OC Accent", 0.02)
    k.box(0.04, 0.4, -0.09, -0.03, P + 0.18, P + dh * 0.45, "OC Accent", 0.02)
    k.box(-0.4, -0.04, -0.09, -0.03, P + dh * 0.52, P + dh - 0.15, "OC Accent", 0.02)
    k.box(0.04, 0.4, -0.09, -0.03, P + dh * 0.52, P + dh - 0.15, "OC Accent", 0.02)
    k.box(0.3, 0.36, -0.15, -0.05, P + 1.0, P + 1.08, "OC Chrome")
    frame(k, -0.52, 0.52, P, P + dh, t=0.1, d=0.14, bottom=False)
    tz = P + dh + 0.1
    t1 = vmin(tz + 0.4, P + Gh - 0.55)
    glass(k, -0.52, 0.52, tz, t1)
    frame(k, -0.52, 0.52, tz, t1, t=0.08, d=0.12, bottom=False)
    bars(k, -0.52, 0.52, tz, t1, 3, 1, w=0.04)
    hood = t1 + 0.08
    k.sym(0.64, 0.86, -0.15, 0.02, P, hood, "OC Trim", 0.02)
    k.box(-1.0, 1.0, -0.24, 0.02, hood, hood + 0.2, "OC Trim", 0.025)
    k.box(-1.1, 1.1, -0.34, 0.02, hood + 0.2, hood + 0.3, "OC Trim", 0.025)
    k.when(V.g.gt(val(detail), 0.5), lambda: k.sym(0.7, 0.8, -0.3, 0.02, hood - 0.25, hood, "OC Trim", 0.015))
    wall_lamp(k, 1.2, P + 2.0)


def back_door(k, i):
    P = V(i("Plinth"))
    k.box(-0.48, 0.48, -0.05, 0.02, P, P + 2.2, "OC Accent", 0.02)
    k.box(-0.3, 0.3, -0.08, -0.03, P + 1.3, P + 2.0, "OC Accent", 0.015)
    frame(k, -0.48, 0.48, P, P + 2.2, t=0.08, d=0.1, bottom=False)
    k.box(-0.8, 0.8, -0.55, 0.02, P + 2.36, P + 2.48, "OC Trim", 0.02)
    k.when(V.g.gt(val(P), 0.03), lambda: k.box(-0.7, 0.7, -0.6, 0.02, 0.0, P, "OC Concrete", 0.015))


# -- add-ons: built for a given window size, so they fit the window they belong to ----------------------
def shutters(k, B, ww, wh, zs):
    room = B / 2 - ww / 2 - FRAME_T - 0.06
    sw = vmax(vmin(ww / 2 + 0.02, room), 0.05)
    x0 = ww / 2 + FRAME_T
    k.sym(x0, x0 + sw, -0.08, 0.02, zs, zs + wh, "OC Shutter", 0.015)
    k.sym(x0 + 0.04, x0 + 0.08, -0.12, -0.06, zs + wh * 0.2, zs + wh * 0.24, "OC Iron")


def flower_box(k, ww, zs):
    g = k.g
    z = zs - FRAME_T + 0.005
    k.box(-ww / 2 - 0.06, ww / 2 + 0.06, -0.46, -0.16, z, z + 0.24, "OC Accent", 0.025)
    k.sym(ww / 2 - 0.18, ww / 2 - 0.08, -0.38, 0.0, z - 0.2, z, "OC Iron")
    # foliage clumps along the box and a scatter of blooms on top
    n = 5
    for c in range(n):
        x = (-ww / 2) + (ww * ((c + 0.5) / n))
        k.ico(0.17, xyz(x, -0.31, z + 0.3), "OC Leaves", scale=(1.15, 0.85, 0.75))
    blooms = []
    for c in range(9):
        x = (-ww / 2 + 0.08) + (ww - 0.16) * (((c * 0.618) % 1.0))
        y = -0.24 - 0.14 * ((c * 0.37) % 1.0)
        blooms.append(g.transform(g.out("GeometryNodeMeshIcoSphere", {"Radius": 0.055, "Subdivisions": 1},
                                        output="Mesh"), translation=xyz(x, y, z + 0.4 + 0.06 * ((c * 0.53) % 1.0))))
    k.add(g.join(*blooms), "OC Flowers")


def railing(k, x0, x1, y_front, z0, height, iron=True, sides=True, depth=None):
    """A balcony railing: posts, rails and evenly spaced balusters."""
    g = k.g
    mat = "OC Iron" if iron else "OC Trim"
    bw = 0.03 if iron else 0.075
    top = V(z0) + height
    k.box(x0, x1, V(y_front) - (0.035 if iron else 0.07), V(y_front) + (0.035 if iron else 0.07),
          top - (0.05 if iron else 0.1), top, mat, 0.01)
    k.box(x0, x1, V(y_front) - 0.025, V(y_front) + 0.025, V(z0) + 0.06, V(z0) + 0.11, mat)
    span = V(x1) - x0
    count = vmax(V(g.floor(val(span / (0.13 if iron else 0.2)))), 2.0)
    idx = g.index()
    x = V(x0) + (V(g.add(idx, 0.5)) / count) * span
    pts = g.points(val(count), xyz(x, y_front, V(z0) + 0.11))
    post = k.raw_box(-bw / 2, bw / 2, -bw / 2, bw / 2, 0.0, V(height) - 0.16 - (0.0 if iron else 0.05))
    k.add(g.realize(g.instance(pts, post)), mat)
    if sides:
        for x in (x0, x1):
            k.box(V(x) - 0.04, V(x) + 0.04, y_front, 0.02, z0, top, mat, 0.01)
            k.box(V(x) - 0.03, V(x) + 0.03, y_front, 0.02, top - 0.05, top, mat)
            k.box(V(x) - 0.012, V(x) + 0.012, V(y_front) * 0.5 - 0.012, V(y_front) * 0.5 + 0.012, z0, top, mat)


def balcony(k, B, ww, style):
    """0: a full balcony on brackets, 1: the same with a stone balustrade, 2: a shallow Juliet balcony."""
    if style == 2:
        w = ww / 2 + 0.2
        k.box(-w, w, -0.34, 0.03, -0.12, 0.0, "OC Trim", 0.02)
        railing(k, -w + 0.03, w - 0.03, -0.3, 0.0, 0.95)
        return
    w = vmin(B / 2 - 0.18, ww / 2 + 0.55)
    k.box(-w, w, -1.0, 0.03, -0.2, 0.0, "OC Trim", 0.03)
    k.box(-w - 0.04, w + 0.04, -1.04, -0.9, -0.24, -0.16, "OC Trim", 0.02)
    for x in (w - 0.3, -(w - 0.3)):
        k.hull([(V(x) - 0.08, 0.02, -0.2), (V(x) + 0.08, 0.02, -0.2), (V(x) - 0.08, -0.8, -0.2),
                (V(x) + 0.08, -0.8, -0.2), (V(x) - 0.08, 0.02, -0.7), (V(x) + 0.08, 0.02, -0.7)], "OC Trim")
    railing(k, -w + 0.04, w - 0.04, -0.94, 0.0, 1.0, iron=(style == 0))


def awning(k, B, P, Gh):
    """A sloping fabric awning with a valance, over one shop bay."""
    g = k.g
    w = B / 2 - 0.22
    zt = P + Gh - 1.02
    reach, drop = 1.05, 0.55
    parts = []
    parts.append(g.hull(g.join(*[g.points(1, xyz(*p)) for p in (
        (-w, 0.02, zt), (w, 0.02, zt), (-w, 0.02, zt - 0.05), (w, 0.02, zt - 0.05),
        (-w, -reach, zt - drop), (w, -reach, zt - drop), (-w, -reach, zt - drop - 0.05),
        (w, -reach, zt - drop - 0.05))])))
    parts.append(k.raw_box(-w, w, -reach - 0.03, -reach + 0.01, zt - drop - 0.3, zt - drop))
    for s in (-1.0, 1.0):
        x = w * s
        parts.append(g.hull(g.join(*[g.points(1, xyz(*p)) for p in (
            (x - 0.01, 0.0, zt), (x + 0.01, 0.0, zt), (x - 0.01, -reach, zt - drop),
            (x + 0.01, -reach, zt - drop), (x - 0.01, -reach, zt - drop - 0.3),
            (x + 0.01, -reach, zt - drop - 0.3))])))
    cloth = g.join(*parts)
    px, _py, _pz = g.split(g.position())
    cloth = g.store(cloth, "oc_u", g.add(px, 50.0), domain="POINT")
    k.add(cloth, "OC Awning")
    for s in (-1.0, 1.0):
        x = (w - 0.1) * s
        k.box(V(x) - 0.02, V(x) + 0.02, -reach + 0.05, 0.02, zt - drop * 0.5 - 0.02, zt - drop * 0.5 + 0.02,
              "OC Iron")


# -- registry ---------------------------------------------------------------------------------------------
# Base modules, in library order. The building picks one per slot by index.
SASH, ARCH, WIDE, FRENCH, SMALL, SASH_G, ARCH_G, WIDE_G, SHOP_WIN, SHOP_DOOR, RES_DOOR, BACK_DOOR, EMPTY = range(13)


def _upper(fn):
    def build(k, i):
        B, ww, wh, zs = _dims(i)
        fn(k, ww, wh, zs, V(i("Detail")))
    return build


def _lower(fn):
    def build(k, i):
        _B, ww, _wh, _zs = _dims(i)
        zs, wh = ground_window_dims(i)
        fn(k, ww, wh, zs, V(i("Detail")))
    return build


BASE = [
    ("OC Kit Window Sash", _upper(sash)),
    ("OC Kit Window Arched", _upper(arched)),
    ("OC Kit Window Wide", _upper(wide)),
    ("OC Kit French Door", _upper(french)),
    ("OC Kit Window Small", _upper(small)),
    ("OC Kit Ground Window Sash", _lower(sash)),
    ("OC Kit Ground Window Arched", _lower(arched)),
    ("OC Kit Ground Window Wide", _lower(wide)),
    ("OC Kit Shop Window", shop_window),
    ("OC Kit Shop Door", shop_door),
    ("OC Kit Front Door", res_door),
    ("OC Kit Back Door", back_door),
    ("OC Kit Empty", lambda k, i: None),
]


def _addon(fn):
    def build(k, i):
        B, ww, wh, zs = _dims(i)
        fn(k, B, ww, wh, zs)
    return build


def _addon_ground(fn):
    def build(k, i):
        B, ww, _wh, _zs = _dims(i)
        zs, wh = ground_window_dims(i)
        fn(k, B, ww, wh, zs)
    return build


# Add-ons: (upper version, ground-floor version) pairs, picked by floor
ADDONS = [
    ("OC Kit Shutters", _addon(shutters)),
    ("OC Kit Shutters Ground", _addon_ground(shutters)),
    ("OC Kit Flower Box", _addon(lambda k, B, ww, wh, zs: flower_box(k, ww, zs))),
    ("OC Kit Flower Box Ground", _addon_ground(lambda k, B, ww, wh, zs: flower_box(k, ww, zs))),
    ("OC Kit Balcony", lambda k, i: balcony(k, V(i("Bay")), V(i("Win W")), 0)),
    ("OC Kit Balcony Stone", lambda k, i: balcony(k, V(i("Bay")), V(i("Win W")), 1)),
    ("OC Kit Balcony Juliet", lambda k, i: balcony(k, V(i("Bay")), V(i("Win W")), 2)),
    ("OC Kit Awning", lambda k, i: awning(k, V(i("Bay")), V(i("Plinth")), V(i("Ground")))),
]


def build_all():
    """Build every facade module group. Returns {name: tree}."""
    return {name: _module(name, fn) for name, fn in BASE + ADDONS}
