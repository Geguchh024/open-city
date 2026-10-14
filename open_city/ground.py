# SPDX-License-Identifier: GPL-3.0-or-later
"""The street surface as plain mesh data: asphalt, kerbed block islands with rounded corners, lawns,
alleys, garden paths, park paths and plaza, lane markings, crossings, parking bays, manholes, the
countryside round the town and the diorama base. No bpy: `build(plan)` returns vertices, faces, a material
name per face and which faces are shaded smooth.

The countryside closes off the edge of town, so the streets never run out into a void: open fields, or a
valley whose wooded hills rise behind the last houses (`terrain_height` is shared with the forest planting).
"""

import math
import random

from .layout import CORNER_RADIUS, CURB

Z_MARK = 0.006
VERGE = 5.0            # grass between the outer sidewalk and the countryside
HILLS = 30.0           # height of the hills round the valley
HILL_RISE = 65.0       # how far out they reach their full height
FAR = 650.0            # the countryside runs this far out, past the horizon of any town view
DIORAMA_FAR = 45.0     # ... or this far on a diorama base


class MeshData:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []
        self.smooth = []

    def face(self, idx, mat, smooth=False):
        self.faces.append(idx)
        self.mats.append(mat)
        self.smooth.append(smooth)

    def poly(self, pts, z, mat, flip=False):
        """A flat polygon (counter-clockwise from above) at height z."""
        base = len(self.verts)
        self.verts += [(p[0], p[1], z) for p in pts]
        idx = list(range(base, base + len(pts)))
        self.face(idx[::-1] if flip else idx, mat)

    def quad3(self, a, b, c, d, mat):
        base = len(self.verts)
        self.verts += [a, b, c, d]
        self.face([base, base + 1, base + 2, base + 3], mat)

    def rect(self, x0, x1, y0, y1, z, mat):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z, mat)

    def oriented_rect(self, cx, cy, ang, length, width, z, mat):
        c, s = math.cos(ang), math.sin(ang)
        hl, hw = length / 2, width / 2
        pts = [(cx + c * x - s * y, cy + s * x + c * y) for x, y in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]
        self.poly(pts, z, mat)

    def walls(self, pts, z0, z1, mat):
        """Vertical faces along a closed outline (counter-clockwise), facing outwards."""
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            self.quad3((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1), mat)

    def ring(self, outer, inner, z, mat):
        """The flat band between two outlines with the same number of points."""
        n = len(outer)
        for i in range(n):
            j = (i + 1) % n
            self.poly([outer[i], outer[j], inner[j], inner[i]], z, mat)


def rounded_rect(x0, x1, y0, y1, r, segs=5):
    """Corner points of a rectangle with rounded corners, counter-clockwise."""
    r = max(0.0, min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01))
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -math.pi / 2), (x1 - r, y1 - r, 0.0), (x0 + r, y1 - r, math.pi / 2),
                       (x0 + r, y0 + r, math.pi)):
        for k in range(segs + 1):
            a = a0 + (math.pi / 2) * k / segs
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def build(plan):
    s = plan.settings
    m = MeshData()
    rng = random.Random(int(s["Seed"]) * 31 + 5)
    sw = s["Sidewalk Width"]
    X0, X1, Y0, Y1 = plan.extent

    # the road network and the edge of town
    m.rect(X0, X1, Y0, Y1, 0.0, "OC Asphalt")
    outer = town_edge(plan)
    kerb_out = [(X0, Y0), (X0, Y1), (X1, Y1), (X1, Y0)]            # clockwise: the walls face the road
    m.walls(kerb_out, 0.0, CURB, "OC Curb")
    walk = (X0 - sw, X1 + sw, Y0 - sw, Y1 + sw)
    # outer sidewalk ring and grass verge, each as four strips
    _frame(m, (X0, X1, Y0, Y1), walk, CURB, "OC Sidewalk")
    _frame(m, walk, outer, CURB, "OC Grass")
    if s["Surroundings"] or not s["Diorama Base"]:
        _countryside(m, plan)
    else:
        ox0, ox1, oy0, oy1 = outer
        m.walls([(ox0, oy0), (ox1, oy0), (ox1, oy1), (ox0, oy1)], -2.4, CURB, "OC Base")
        m.poly([(ox0, oy0), (ox1, oy0), (ox1, oy1), (ox0, oy1)], -2.4, "OC Base", flip=True)

    for b in plan.blocks:
        _island(m, b, plan)
    _markings(m, plan, rng)
    return m


def town_edge(plan):
    """The rectangle the town (streets, outer sidewalk and verge) fills; the countryside starts here."""
    X0, X1, Y0, Y1 = plan.extent
    v = plan.settings["Sidewalk Width"] + VERGE
    return X0 - v, X1 + v, Y0 - v, Y1 + v


def country_reach(plan):
    """How far the countryside runs out from the edge of town."""
    return DIORAMA_FAR if plan.settings["Diorama Base"] else FAR


def outside(plan, x, y):
    """Distance from a point to the edge of town (0 inside it)."""
    ox0, ox1, oy0, oy1 = town_edge(plan)
    dx = max(ox0 - x, 0.0, x - ox1)
    dy = max(oy0 - y, 0.0, y - oy1)
    return math.hypot(dx, dy)


def terrain_height(plan, x, y):
    """Height of the countryside at (x, y): kerb height at the edge of town, rising into hills in a valley."""
    s = plan.settings
    if s["Surroundings"] < 2:
        return CURB
    d = outside(plan, x, y)
    if d <= 0.0:
        return CURB
    t = min(d / HILL_RISE, 1.0)
    rise = t * t * (3.0 - 2.0 * t)
    k = int(s["Seed"]) % 997
    # rolling crests: a few long waves, so the skyline is never a flat wall
    wave = (math.sin(x * 0.031 + k) * math.cos(y * 0.027 - k * 0.7) + 0.6 * math.sin((x - y) * 0.052 + k * 1.3)
            + 0.3 * math.sin(x * 0.11 - k) * math.sin(y * 0.097 + k))
    crest = HILLS * (0.72 + 0.2 * wave)
    bumps = 0.6 * math.sin(x * 0.21 + y * 0.17 + k) * min(d / 12.0, 1.0)
    return CURB + crest * rise + bumps * (1.0 - rise * 0.5)


def _ticks(a, b, step):
    n = max(1, int(math.ceil((b - a) / step)))
    return [a + (b - a) * i / n for i in range(n + 1)]


def _outward(edge, reach, sign):
    """Coordinates from the edge of town outwards, fine near town and coarser further out."""
    out, d, step = [], 0.0, 3.0
    while d < reach:
        d = min(reach, d + step)
        out.append(edge + sign * d)
        step *= 1.09
    return out


def _countryside(m, plan):
    """Fields or hills from the edge of town out past the horizon (or to the rim of the diorama base)."""
    ox0, ox1, oy0, oy1 = town_edge(plan)
    reach = country_reach(plan)
    xs = _outward(ox0, reach, -1)[::-1] + _ticks(ox0, ox1, 6.0) + _outward(ox1, reach, 1)
    ys = _outward(oy0, reach, -1)[::-1] + _ticks(oy0, oy1, 6.0) + _outward(oy1, reach, 1)
    base = len(m.verts)
    nx, ny = len(xs), len(ys)
    m.verts += [(x, y, terrain_height(plan, x, y)) for y in ys for x in xs]
    hills = plan.settings["Surroundings"] == 2
    for j in range(ny - 1):
        for i in range(nx - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if ox0 < cx < ox1 and oy0 < cy < oy1:
                continue                                    # the town itself
            a = base + j * nx + i
            m.face([a, a + 1, a + nx + 1, a + nx], "OC Grass", smooth=hills)
    if not plan.settings["Diorama Base"]:
        return
    # the base: walls down from the rim of the land (counter-clockwise, facing out), and a bottom
    rim = ([(i, 0) for i in range(nx)] + [(nx - 1, j) for j in range(1, ny)]
           + [(i, ny - 1) for i in range(nx - 2, -1, -1)] + [(0, j) for j in range(ny - 2, 0, -1)])
    pts = [m.verts[base + j * nx + i] for i, j in rim]
    for k in range(len(pts)):
        a, b = pts[k], pts[(k + 1) % len(pts)]
        m.quad3((a[0], a[1], -2.4), (b[0], b[1], -2.4), b, a, "OC Base")
    m.poly([(xs[0], ys[0]), (xs[-1], ys[0]), (xs[-1], ys[-1]), (xs[0], ys[-1])], -2.4, "OC Base", flip=True)


def _frame(m, inner, outer, z, mat):
    """Four flat strips between an inner and an outer rectangle."""
    ix0, ix1, iy0, iy1 = inner
    ox0, ox1, oy0, oy1 = outer
    m.rect(ox0, ox1, oy0, iy0, z, mat)
    m.rect(ox0, ox1, iy1, oy1, z, mat)
    m.rect(ox0, ix0, iy0, iy1, z, mat)
    m.rect(ix1, ox1, iy0, iy1, z, mat)


def _island(m, b, plan):
    s = plan.settings
    sw = s["Sidewalk Width"]
    outer = rounded_rect(b.x0, b.x1, b.y0, b.y1, CORNER_RADIUS)
    inner = rounded_rect(b.x0 + 0.28, b.x1 - 0.28, b.y0 + 0.28, b.y1 - 0.28, CORNER_RADIUS - 0.28)
    m.walls(outer, 0.0, CURB, "OC Curb")
    m.ring(outer, inner, CURB, "OC Curb")
    m.poly(inner, CURB, "OC Sidewalk")
    ix0, ix1, iy0, iy1 = b.inner(sw)
    zl = CURB + 0.012
    if b.kind == "park":
        _park(m, b, plan, zl)
        return
    m.rect(ix0, ix1, iy0, iy1, zl, "OC Grass")
    zp = CURB + 0.02
    for key, a0, a1, kind in b.gaps:
        if kind != "alley":
            continue
        e = b.edges[key]
        pts = [e.at(a0, 0.0), e.at(a1, 0.0), e.at(a1, 12.0), e.at(a0, 12.0)]
        m.poly(_ccw(pts), zp, "OC Paving")
    for bd in b.buildings:
        if bd.setback < 1.0:
            continue
        e = bd.edge
        a, _stoop = bd.entrance()
        pts = [e.at(a - 0.6, 0.0), e.at(a + 0.6, 0.0), e.at(a + 0.6, bd.setback), e.at(a - 0.6, bd.setback)]
        m.poly(_ccw(pts), zp, "OC Paving")


def _park(m, b, plan, zl):
    s = plan.settings
    ix0, ix1, iy0, iy1 = b.inner(s["Sidewalk Width"])
    cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
    plaza = getattr(b, "plaza", min(5.5, min(ix1 - ix0, iy1 - iy0) / 2 - 3.0))
    pw = getattr(b, "path_w", 2.4) / 2
    m.rect(ix0, ix1, iy0, iy1, zl, "OC Grass")
    zp = CURB + 0.02
    m.rect(ix0, ix1, cy - pw, cy + pw, zp, "OC Paving")
    m.rect(cx - pw, cx + pw, iy0, cy - pw, zp, "OC Paving")
    m.rect(cx - pw, cx + pw, cy + pw, iy1, zp, "OC Paving")
    circle = [(cx + (plaza + 2.0) * math.cos(a * math.tau / 32), cy + (plaza + 2.0) * math.sin(a * math.tau / 32))
              for a in range(32)]
    m.poly(circle, zp + 0.004, "OC Paving")


def _ccw(pts):
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    return pts if area > 0 else pts[::-1]


def _markings(m, plan, rng):
    s = plan.settings
    road = s["Street Width"]
    xs = sorted(st.centre for st in plan.streets if st.axis == "y")
    ys = sorted(st.centre for st in plan.streets if st.axis == "x")
    hw = road / 2
    z = Z_MARK
    for st in plan.streets:
        cross = xs if st.axis == "x" else ys
        c, q = st.carriageway()           # parked cars on one side push the lanes over
        # segments of this street between crossings
        for c0, c1 in zip(cross, cross[1:]):
            t0, t1 = c0 + hw, c1 - hw
            # crossings at both ends: zebra stripes across the carriageway
            for tc, sign in ((t0, 1.0), (t1, -1.0)):
                start = tc + sign * 0.7
                n = int((road - 0.8) / 1.0)
                for k in range(n):
                    off = -hw + 0.4 + 0.25 + k * 1.0 + ((road - 0.8) - n * 1.0) / 2
                    along = start + sign * 1.4
                    _mark(m, st, along, off, 2.8, 0.5, z, "OC Marking")
                # stop line on the approaching lane
                stop = tc + sign * 3.6
                # traffic keeps right: the approaching lane is on the driver's right
                _mark(m, st, stop, st.lane(-sign), 0.35, 2 * q - 0.3, z, "OC Marking")
            # the centre line
            a = t0 + 5.0
            if st.main:
                length = (t1 - 5.0) - a
                if length > 0:
                    _mark(m, st, a + length / 2, c - 0.12, length, 0.12, z, "OC Marking Yellow")
                    _mark(m, st, a + length / 2, c + 0.12, length, 0.12, z, "OC Marking Yellow")
            else:
                while a + 2.0 < t1 - 5.0:
                    _mark(m, st, a + 1.0, c, 2.0, 0.14, z, "OC Marking")
                    a += 4.5
            # a manhole or two
            for _ in range(rng.choice((0, 1, 1, 2))):
                t = rng.uniform(t0 + 6.0, t1 - 6.0) if t1 - t0 > 14 else None
                if t is None:
                    continue
                off = rng.uniform(-hw + 1.2, hw - 1.2)
                cx, cy = (t, st.centre + off) if st.axis == "x" else (st.centre + off, t)
                m.poly([(cx + 0.36 * math.cos(k * math.tau / 12), cy + 0.36 * math.sin(k * math.tau / 12))
                        for k in range(12)], z * 0.7, "OC Metal")
    # parking bays: a short tick at every bay boundary
    for (x, y, rot) in getattr(plan, "parking", []):
        m.oriented_rect(x, y, rot + math.pi / 2, 1.9, 0.1, z, "OC Marking")


def _mark(m, st, along, off, length, width, z, mat):
    """A painted rectangle `along` the street and `off` its centre line."""
    if st.axis == "x":
        m.oriented_rect(along, st.centre + off, 0.0, length, width, z, mat)
    else:
        m.oriented_rect(st.centre + off, along, math.pi / 2, length, width, z, mat)
