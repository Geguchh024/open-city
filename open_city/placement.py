# SPDX-License-Identifier: GPL-3.0-or-later
"""Environmental prop placement. No bpy.

Props are placed by rules, not scattered: every sidewalk is split into a kerb zone (lamps, trees, bins,
benches, hydrants, the bus stop) and a facade zone (cafe tables, sandwich boards, planters), and each
zone keeps a list of what it has given away, so nothing blocks a door, a stoop, a corner or a crossing.
Parked cars follow the kerbs and face the way the traffic flows; parks get paths, a fountain, benches,
lamps, flower beds and trees; courtyards and gardens get trees and shrubs away from the walls.
"""

import math
import random

from . import ground
from .layout import CORNER_RADIUS, CURB, N, S, W

# The prop library, in instance order (the scatter node group builds its library in this order).
PROP_KEYS = (
    "lamp", "park_lamp", "bench", "bin", "mailbox", "hydrant", "bollard", "stop_sign", "street_sign",
    "traffic_light", "bus_shelter", "bike_rack", "cafe_set", "cafe_table", "sandwich_board", "planter",
    "potted_plant",
    "tree_round", "tree_tall", "tree_pine", "shrub", "hedge", "flower_bed", "fence", "tree_grate", "fountain",
    "hatchback", "sedan", "city_car", "van",
)
TREES = {"tree_round", "tree_tall", "tree_pine", "shrub", "hedge", "flower_bed"}
CARS = {"hatchback", "sedan", "city_car", "van"}
CAR_LEN = {"hatchback": 4.0, "sedan": 4.7, "city_car": 3.4, "van": 5.2}


def layer_of(key):
    """Which scatter object a prop belongs to."""
    if key in CARS:
        return "Cars"
    if key in TREES:
        return "Greenery"
    return "Street Furniture"


class Prop:
    __slots__ = ("key", "x", "y", "z", "rot", "scale", "tint")

    def __init__(self, key, x, y, z, rot=0.0, scale=(1.0, 1.0, 1.0), tint=0.0):
        self.key, self.x, self.y, self.z, self.rot, self.scale, self.tint = key, x, y, z, rot, scale, tint


class Zone:
    """Occupied stretches along one sidewalk zone."""

    def __init__(self, length):
        self.length = length
        self.taken = []

    def free(self, a0, a1):
        if a0 < 0 or a1 > self.length:
            return False
        return all(a1 <= t0 or a0 >= t1 for t0, t1 in self.taken)

    def take(self, a0, a1):
        self.taken.append((a0, a1))

    def try_take(self, a0, a1):
        if self.free(a0, a1):
            self.take(a0, a1)
            return True
        return False


class Side:
    """One sidewalk of a block: an edge from kerb (d = 0) to building line (d = sidewalk width)."""

    def __init__(self, block, key, plan):
        sw = plan.settings["Sidewalk Width"]
        e = block.edges[key]
        # the kerb line runs parallel to the building line, `sw` further out
        self.edge = e
        self.key = key
        self.sw = sw
        self.length = e.length + 2 * sw
        self.start = (e.start[0] - e.u[0] * sw - e.n[0] * sw, e.start[1] - e.u[1] * sw - e.n[1] * sw)
        self.u, self.n, self.rot = e.u, e.n, e.rot
        self.kerb = Zone(self.length)
        self.facade = Zone(self.length)
        self.street = e.street
        # which kerb of its street this is: the block lies on the street's +y (+x) side for S (W) edges
        self.kerb_side = 1 if key in (S, W) else -1
        margin = CORNER_RADIUS + 1.6
        for z in (self.kerb, self.facade):
            z.take(-1.0, margin)
            z.take(self.length - margin, self.length + 1.0)

    def at(self, a, d):
        return (self.start[0] + self.u[0] * a + self.n[0] * d, self.start[1] + self.u[1] * a + self.n[1] * d)

    def a_of_building(self, a_build):
        return a_build + self.sw


def place_props(plan):
    """Every prop of the town as a list of `Prop`."""
    s = plan.settings
    rng = random.Random(int(s["Seed"]) * 104729 + 3)
    out = []
    sides = {}
    for b in plan.blocks:
        for key in b.edges:
            sides[(b.index, key)] = Side(b, key, plan)

    _reserve_entrances(plan, sides)
    _corners(plan, sides, rng, out)
    if s["Furniture"] > 0:
        _bus_stop(plan, sides, rng, out)
        _shop_fronts(plan, sides, rng, out)
    _street_lights_and_trees(plan, sides, rng, out)
    if s["Furniture"] > 0:
        _kerb_furniture(plan, sides, rng, out)
    _gardens(plan, rng, out)
    for b in plan.blocks:
        if b.kind == "park":
            _park(plan, b, rng, out)
        else:
            _courtyard(plan, b, rng, out)
    _verge(plan, rng, out)
    _forest(plan, out)
    out += _cars(plan, sides, rng)
    return out


# -- sidewalks -----------------------------------------------------------------------------------------------
def _reserve_entrances(plan, sides):
    for b in plan.blocks:
        for bd in b.buildings:
            side = sides[(b.index, bd.edge.key)]
            a, stoop = bd.entrance()
            a = side.a_of_building(a)
            if bd.setback < 0.5:
                side.facade.take(a - 1.3, a + 1.3)
                side.kerb.take(a - 0.9, a + 0.9)
            if bd.role == "house":
                continue
            if bd.params["Ground Use"] == 1 and bd.params["Awnings"]:
                # awnings reach a metre out: keep tall things (trees) out of the kerb zone below them
                pass


def _corners(plan, sides, rng, out):
    s = plan.settings
    for b in plan.blocks:
        for (k0, k1) in ((S, "E"), ("E", N), (N, "W"), ("W", S)):
            side = sides[(b.index, k0)]
            nxt = sides[(b.index, k1)]
            # the corner where side k0 ends and side k1 begins
            x, y = side.at(side.length, 0.0)
            ux, uy = side.u
            nx_, ny_ = nxt.u
            px = x - ux * 1.25 + nx_ * 1.25
            py = y - uy * 1.25 + ny_ * 1.25
            main = side.street.main or nxt.street.main
            diag = side.rot + math.pi / 4
            z = CURB
            if main and side.street.main and s["Furniture"] > 0:
                out.append(Prop("traffic_light", px, py, z, side.rot))
                bx, by = side.at(side.length - CORNER_RADIUS - 2.4, 0.45)
                out.append(Prop("bollard", bx, by, z))
                bx, by = nxt.at(CORNER_RADIUS + 2.4, 0.45)
                out.append(Prop("bollard", bx, by, z))
            elif s["Furniture"] > 0.2:
                pick = rng.random()
                if pick < 0.4:
                    out.append(Prop("stop_sign", px, py, z, side.rot + math.pi / 2))
                elif pick < 0.75:
                    out.append(Prop("street_sign", px, py, z, diag))
            if rng.random() < 0.3 * s["Furniture"]:
                hx, hy = side.at(side.length - CORNER_RADIUS - 3.2, 0.4)
                if side.kerb.try_take(side.length - CORNER_RADIUS - 3.6, side.length - CORNER_RADIUS - 2.8):
                    out.append(Prop("hydrant", hx, hy, z, side.rot))


def _bus_stop(plan, sides, rng, out):
    cands = [sd for sd in sides.values() if sd.street.main]
    rng.shuffle(cands)
    for sd in cands:
        for _ in range(12):
            a = rng.uniform(8.0, sd.length - 8.0)
            if sd.kerb.free(a - 2.6, a + 2.6) and sd.facade.free(a - 2.2, a + 2.2):
                sd.kerb.take(a - 2.6, a + 2.6)
                x, y = sd.at(a, 1.15)
                out.append(Prop("bus_shelter", x, y, CURB, sd.rot))
                bx, by = sd.at(a + 3.2, 0.45)
                out.append(Prop("bin", bx, by, CURB, sd.rot))
                sd.kerb.take(a + 2.8, a + 3.6)
                sd.bus_stop = a
                return


def _shop_fronts(plan, sides, rng, out):
    s = plan.settings
    f = s["Furniture"]
    for b in plan.blocks:
        for bd in b.buildings:
            if bd.params["Ground Use"] != 1 or bd.setback > 0.5:
                continue
            side = sides[(b.index, bd.edge.key)]
            a_door = side.a_of_building(bd.entrance()[0])
            a0, a1 = side.a_of_building(bd.a0), side.a_of_building(bd.a0 + bd.width)
            sw = side.sw
            if bd.shop_kind() == "cafe" and sw >= 2.4:
                # under awnings the tables go without parasols, which would hit the canvas
                parasol = not bd.params["Awnings"] and sw >= 2.8
                kind, d = ("cafe_set", sw - 1.15) if parasol else ("cafe_table", sw - 0.85)
                a = a0 + 1.4
                while a < a1 - 1.2:
                    if (abs(a - a_door) > 1.6 and side.facade.try_take(a - 1.0, a + 1.0)
                            and rng.random() < 0.6 + 0.4 * f):
                        x, y = side.at(a, d)
                        out.append(Prop(kind, x, y, CURB, side.rot, tint=rng.random()))
                    a += 2.5
            elif rng.random() < 0.7 * f:
                a = a_door + rng.choice((-1.6, 1.6))
                if side.facade.try_take(a - 0.45, a + 0.45):
                    x, y = side.at(a, sw - 0.75)
                    out.append(Prop("sandwich_board", x, y, CURB, side.rot + rng.uniform(-0.3, 0.3)))
            # planters at the ends of the shopfront
            for a in (a0 + 0.8, a1 - 0.8):
                if rng.random() < 0.45 * f and side.facade.try_take(a - 0.6, a + 0.6):
                    x, y = side.at(a, sw - 0.32)
                    out.append(Prop("planter", x, y, CURB, side.rot, tint=rng.random()))
            # keep street trees from growing into the awnings
            side.kerb_trees_off = getattr(side, "kerb_trees_off", []) + [(a0, a1)]


def _street_lights_and_trees(plan, sides, rng, out):
    s = plan.settings
    lights, trees = s["Street Lights"], s["Trees"]
    for sd in sides.values():
        spacing = 30.0 - 16.0 * lights
        start = CORNER_RADIUS + 2.5 + rng.uniform(0.0, 2.0)
        lamp_at = []
        if lights > 0.01:
            a = start
            while a < sd.length - CORNER_RADIUS - 2.0:
                if sd.kerb.try_take(a - 0.4, a + 0.4):
                    x, y = sd.at(a, 0.45)
                    out.append(Prop("lamp", x, y, CURB, sd.rot))
                    lamp_at.append(a)
                a += spacing
        if trees < 0.01 or sd.sw < 2.4:
            continue
        no_trees = getattr(sd, "kerb_trees_off", [])
        step = 16.0 - 8.0 * trees
        a = start + step / 2
        kind = rng.choice(("tree_round", "tree_round", "tree_tall"))
        while a < sd.length - CORNER_RADIUS - 2.5:
            under_awning = any(t0 - 1.0 < a < t1 + 1.0 for t0, t1 in no_trees)
            if not under_awning and sd.kerb.try_take(a - 0.8, a + 0.8):
                x, y = sd.at(a, 1.0)
                out.append(Prop("tree_grate", x, y, CURB, sd.rot))
                sc = rng.uniform(0.85, 1.1)
                out.append(Prop(kind, x, y, CURB, rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))
            a += step


def _kerb_furniture(plan, sides, rng, out):
    s = plan.settings
    f = s["Furniture"]
    mail = 0
    for sd in sides.values():
        busy = sd.street.main
        n = int((sd.length / 18.0) * f * (1.6 if busy else 0.7))
        for _ in range(n):
            a = rng.uniform(CORNER_RADIUS + 3.0, sd.length - CORNER_RADIUS - 3.0)
            r = rng.random()
            if r < 0.4 and sd.kerb.try_take(a - 1.0, a + 1.0):
                x, y = sd.at(a, 0.75)
                out.append(Prop("bench", x, y, CURB, sd.rot + math.pi))
                if sd.kerb.try_take(a + 1.1, a + 1.6):
                    x, y = sd.at(a + 1.35, 0.6)
                    out.append(Prop("bin", x, y, CURB, sd.rot))
            elif r < 0.65 and sd.kerb.try_take(a - 0.4, a + 0.4):
                x, y = sd.at(a, 0.6)
                out.append(Prop("bin", x, y, CURB, sd.rot))
            elif r < 0.8 and busy and sd.kerb.try_take(a - 1.2, a + 1.2):
                x, y = sd.at(a, 0.75)
                out.append(Prop("bike_rack", x, y, CURB, sd.rot))
            elif r < 0.9 and mail < 2 and sd.kerb.try_take(a - 0.4, a + 0.4):
                x, y = sd.at(a, 0.55)
                out.append(Prop("mailbox", x, y, CURB, sd.rot))
                mail += 1


# -- gardens, courtyards, parks --------------------------------------------------------------------------------
def _gardens(plan, rng, out):
    """Front gardens of houses (hedge or picket fence, a path gap, flower beds, shrubs), and the empty lots."""
    s = plan.settings
    z = CURB + 0.02
    for b in plan.blocks:
        for bd in b.buildings:
            if bd.setback < 1.0:
                continue
            e = bd.edge
            a0, a1 = bd.a0 - 1.0, bd.a0 + bd.width + 1.0
            a_door = bd.entrance()[0]
            fence = rng.random() < 0.4
            _boundary(out, e, a0, a1, 0.35, z, fence, gap=(a_door - 0.7, a_door + 0.7), rng=rng)
            # flower beds under the front windows
            for a in (bd.a0 + 0.9, bd.a0 + bd.width - 0.9):
                if abs(a - a_door) > 1.3 and rng.random() < 0.8:
                    x, y = e.at(a, bd.setback - 0.6)
                    out.append(Prop("flower_bed", x, y, z, e.rot, (1.0, 0.9, 1.0), rng.random()))
            for a in (a0 + 0.4, a1 - 0.4):
                if rng.random() < 0.6:
                    x, y = e.at(a, bd.setback + bd.depth * rng.uniform(0.2, 0.8))
                    out.append(Prop("shrub", x, y, z, rng.uniform(0, math.tau), (1.1, 1.1, 1.1), rng.random()))
            # a tree in the back garden
            if rng.random() < 0.4 + 0.5 * s["Trees"]:
                x, y = e.at(bd.a0 + bd.width * rng.uniform(0.2, 0.8), bd.setback + bd.depth + 3.0)
                if _inside_block(b, plan, x, y, 2.0) and not _hits(plan, b, x, y, 2.2):
                    sc = rng.uniform(0.85, 1.2)
                    out.append(Prop(rng.choice(("tree_round", "tree_pine", "tree_tall")), x, y, z,
                                    rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))
        for key, a0, a1, kind in b.gaps:
            e = b.edges[key]
            if kind == "alley" or a1 - a0 < 2.0:
                continue
            _boundary(out, e, a0 + 0.3, a1 - 0.3, 0.35, z, rng.random() < 0.3, gap=None, rng=rng)
            if a1 - a0 > 5.0 and rng.random() < 0.8:
                x, y = e.at((a0 + a1) / 2, 4.0)
                if not _hits(plan, b, x, y, 2.0):
                    sc = rng.uniform(0.9, 1.2)
                    out.append(Prop("tree_round", x, y, z, rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))


def _boundary(out, e, a0, a1, d, z, fence, gap, rng):
    """A hedge or a picket fence from a0 to a1 along an edge, `d` inside it, with an optional gap."""
    unit = 2.0 if fence else 1.0
    key = "fence" if fence else "hedge"
    spans = [(a0, a1)] if gap is None else [(a0, gap[0]), (gap[1], a1)]
    for s0, s1 in spans:
        length = s1 - s0
        if length < 0.6:
            continue
        n = max(1, int(round(length / unit)))
        seg = length / n
        for k in range(n):
            x, y = e.at(s0 + seg * (k + 0.5), d)
            out.append(Prop(key, x, y, z, e.rot, (seg / unit, 1.0, 1.0), rng.random()))


def _inside_block(b, plan, x, y, margin):
    ix0, ix1, iy0, iy1 = b.inner(plan.settings["Sidewalk Width"])
    return ix0 + margin < x < ix1 - margin and iy0 + margin < y < iy1 - margin


def _hits(plan, b, x, y, r):
    """Does a circle of radius r at (x, y) touch any building of the block?"""
    for bd in b.buildings:
        x0, x1, y0, y1 = bd.bbox()
        if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
            return True
    return False


def _courtyard(plan, b, rng, out):
    s = plan.settings
    z = CURB + 0.02
    ix0, ix1, iy0, iy1 = b.inner(s["Sidewalk Width"])
    area = (ix1 - ix0) * (iy1 - iy0)
    want = int(area / 140.0 * s["Trees"])
    placed = []
    for _ in range(want * 8):
        if len(placed) >= want:
            break
        x, y = rng.uniform(ix0 + 1.8, ix1 - 1.8), rng.uniform(iy0 + 1.8, iy1 - 1.8)
        if _hits(plan, b, x, y, 2.3) or any(math.hypot(x - px, y - py) < 4.2 for px, py in placed):
            continue
        # keep the front gardens of houses for the garden rules
        placed.append((x, y))
        kind = rng.choice(("tree_round", "tree_round", "tree_tall", "tree_pine", "shrub"))
        sc = rng.uniform(0.8, 1.2)
        out.append(Prop(kind, x, y, z, rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))


def _park(plan, b, rng, out):
    """Cross paths to a round plaza with a fountain, flower beds round it, trees in the lawns."""
    s = plan.settings
    z = CURB + 0.02
    ix0, ix1, iy0, iy1 = b.inner(s["Sidewalk Width"])
    cx, cy = (ix0 + ix1) / 2, (iy0 + iy1) / 2
    plaza = b.plaza = min(5.5, (min(ix1 - ix0, iy1 - iy0)) / 2 - 3.0)
    b.path_w = 2.4
    out.append(Prop("fountain", cx, cy, z, 0.0))
    # flower beds in a broken ring round the plaza
    for k in range(12):
        ang = (k + 0.5) * math.tau / 12
        # leave the four paths clear
        if min(abs(((ang - q * math.pi / 2 + math.pi) % math.tau) - math.pi) for q in range(4)) < 0.45:
            continue
        r = plaza + 0.9
        out.append(Prop("flower_bed", cx + r * math.cos(ang), cy + r * math.sin(ang), z, ang, (1.2, 1.0, 1.0),
                        rng.random()))
    # benches and lamps along the four paths
    for q in range(4):
        ang = q * math.pi / 2
        ux, uy = math.cos(ang), math.sin(ang)
        reach = (ix1 - cx) if q % 2 == 0 else (iy1 - cy)
        for t in (plaza + 4.0, plaza + 9.0):
            if t > reach - 3.0:
                continue
            for side in (-1, 1):
                px, py = cx + ux * t - uy * side * (b.path_w / 2 + 0.7), cy + uy * t + ux * side * (b.path_w / 2 + 0.7)
                out.append(Prop("bench", px, py, z, ang if side > 0 else ang + math.pi))   # facing the path
            off = b.path_w / 2 + 0.5
            lx, ly = cx + ux * (t + 2.2) + uy * off, cy + uy * (t + 2.2) - ux * off
            out.append(Prop("park_lamp", lx, ly, z))
        off = b.path_w / 2 + 0.6
        bx, by = cx + ux * (plaza + 6.5) - uy * off, cy + uy * (plaza + 6.5) + ux * off
        out.append(Prop("bin", bx, by, z))
    # trees in the four lawns, and a hedge round the edge with gaps for the paths
    placed = []
    want = int((ix1 - ix0) * (iy1 - iy0) / 90.0 * (0.4 + 0.6 * s["Trees"]))
    for _ in range(want * 10):
        if len(placed) >= want:
            break
        x, y = rng.uniform(ix0 + 2.0, ix1 - 2.0), rng.uniform(iy0 + 2.0, iy1 - 2.0)
        if abs(x - cx) < b.path_w / 2 + 2.0 or abs(y - cy) < b.path_w / 2 + 2.0:
            continue
        if math.hypot(x - cx, y - cy) < plaza + 3.0:
            continue
        if any(math.hypot(x - px, y - py) < 4.0 for px, py in placed):
            continue
        placed.append((x, y))
        kind = rng.choice(("tree_round", "tree_round", "tree_tall", "tree_pine", "shrub", "shrub"))
        sc = rng.uniform(0.8, 1.25)
        out.append(Prop(kind, x, y, z, rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))
    for key, e in b.edges.items():
        mid = e.length / 2
        _boundary(out, e, 0.6, e.length - 0.6, 0.4, z, False, gap=(mid - b.path_w / 2 - 0.4, mid + b.path_w / 2 + 0.4),
                  rng=rng)


def _verge(plan, rng, out):
    """Trees along the grass verge round the edge of town."""
    s = plan.settings
    if s["Trees"] < 0.01:
        return
    X0, X1, Y0, Y1 = plan.extent
    sw = s["Sidewalk Width"]
    off = sw + 2.2
    step = 13.0 - 5.0 * s["Trees"]
    z = CURB + 0.02
    for (x0, y0, x1, y1) in ((X0, Y0 - off, X1, Y0 - off), (X0, Y1 + off, X1, Y1 + off),
                             (X0 - off, Y0, X0 - off, Y1), (X1 + off, Y0, X1 + off, Y1)):
        length = math.hypot(x1 - x0, y1 - y0)
        n = int(length / step)
        for k in range(n):
            t = (k + 0.5) / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            sc = rng.uniform(0.85, 1.25)
            out.append(Prop(rng.choice(("tree_round", "tree_pine", "tree_tall", "tree_round")), x, y, z,
                            rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))


FOREST_DEPTH = (34.0, 120.0)     # how deep the woods run: on the flat, and up the hills


def _forest(plan, out):
    """Woods round the town: dense at the edge so the view down every street ends in trees, thinning out up
    the hillsides. A jittered grid, so the trees never clump or leave holes."""
    s = plan.settings
    kind = int(s["Surroundings"])
    if kind == 0:
        return
    rng = random.Random(int(s["Seed"]) * 2477 + 29)
    depth = min(FOREST_DEPTH[kind - 1], ground.country_reach(plan) - 2.0)
    ox0, ox1, oy0, oy1 = ground.town_edge(plan)
    step = 4.2
    hills = kind == 2
    kinds = ("tree_round", "tree_pine", "tree_tall", "tree_pine", "tree_round", "shrub")
    y = oy0 - depth
    while y < oy1 + depth:
        x = ox0 - depth
        while x < ox1 + depth:
            px, py = x + rng.uniform(-1.6, 1.6), y + rng.uniform(-1.6, 1.6)
            d = ground.outside(plan, px, py)
            x += step
            if d < 1.2 or d > depth:
                continue
            # the first rows stand close; further out the wood opens into clumps and glades
            keep = 1.0 if d < 14.0 else max(0.25, 1.0 - (d - 14.0) / (depth * 1.1))
            if rng.random() > keep:
                continue
            z = ground.terrain_height(plan, px, py) - 0.08
            sc = rng.uniform(0.95, 1.45) if d > 6.0 else rng.uniform(0.85, 1.15)
            if hills and d > 20.0:
                sc *= 1.15
            out.append(Prop(rng.choice(kinds), px, py, z, rng.uniform(0, math.tau), (sc, sc, sc), rng.random()))
        y += step


# -- vehicles ------------------------------------------------------------------------------------------------------
def _cars(plan, sides, rng):
    s = plan.settings
    out = []
    plan.parking = []           # (x, y, rot) of every parking bay, for the road markings
    shops = {}
    for b in plan.blocks:
        for bd in b.buildings:
            deliveries = ("GROCERY", "MARKET", "BAKERY", "HARDWARE", "FLOWERS")
            if bd.params["Ground Use"] == 1 and bd.params.get("Shop Name") in deliveries:
                shops.setdefault((b.index, bd.edge.key), []).append(bd)
    for (bi, key), sd in sides.items():
        if sd.kerb_side not in sd.street.parking:
            continue
        heading = sd.rot + math.pi            # parked cars face against the kerb's direction
        a = CORNER_RADIUS + 5.0
        end = sd.length - CORNER_RADIUS - 5.0
        bus = getattr(sd, "bus_stop", None)
        van_spots = [sd.a_of_building(bd.a0 + bd.width / 2) for bd in shops.get((bi, key), [])]
        while a + 5.6 < end:
            mid = a + 2.8
            if bus is not None and abs(mid - bus) < 7.0:
                a += 5.8
                continue
            plan.parking.append(sd.at(a, -1.1) + (sd.rot,))
            if rng.random() < s["Parking"]:
                kind = rng.choice(("hatchback", "sedan", "city_car", "hatchback", "sedan"))
                if any(abs(mid - v) < 4.0 for v in van_spots) and rng.random() < 0.6:
                    kind = "van"
                x, y = sd.at(mid, -1.15)
                out.append(Prop(kind, x, y, 0.0, heading, tint=rng.random()))
            a += 5.8
        plan.parking.append(sd.at(a, -1.1) + (sd.rot,))
    return out


# -- traffic ------------------------------------------------------------------------------------------------------
class Car:
    """A car driving round a route: where it starts on the loop (0..1) and how fast it goes."""
    __slots__ = ("key", "route", "phase", "speed", "length", "tint")

    def __init__(self, key, route, phase, speed, length, tint):
        self.key, self.route, self.phase, self.speed, self.length, self.tint = key, route, phase, speed, length, tint


def loop_length(pts):
    return sum(math.dist(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts)))


def _rounded_loop(x0, x1, y0, y1, r, clockwise, segs=6):
    pts = []
    r = max(0.5, min(r, (x1 - x0) / 2 - 0.1, (y1 - y0) / 2 - 0.1))
    for cx, cy, a0 in ((x1 - r, y0 + r, -math.pi / 2), (x1 - r, y1 - r, 0.0), (x0 + r, y1 - r, math.pi / 2),
                       (x0 + r, y0 + r, math.pi)):
        for k in range(segs + 1):
            a = a0 + (math.pi / 2) * k / segs
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts[::-1] if clockwise else pts


def routes(plan):
    """Closed loops the traffic drives round, in the right-hand lanes.

    Every block has a loop round it (clockwise, in the lanes next to the block, turning right at every
    corner), and one anticlockwise loop runs round the whole town in the outer lanes of the outer streets.
    So each lane carries one loop and no two loops ever cross: the cars never run into each other.
    """
    xs = sorted((st for st in plan.streets if st.axis == "y"), key=lambda st: st.index)
    ys = sorted((st for st in plan.streets if st.axis == "x"), key=lambda st: st.index)
    out = []
    for b in plan.blocks:
        w, e = xs[b.ix], xs[b.ix + 1]
        sth, nth = ys[b.iy], ys[b.iy + 1]
        x0, x1 = w.centre + w.lane(1), e.centre + e.lane(-1)
        y0, y1 = sth.centre + sth.lane(-1), nth.centre + nth.lane(1)
        # round the corner the same way the kerb does, at the lane's distance from it
        gap = min(b.x0 - x0, x1 - b.x1, b.y0 - y0, y1 - b.y1)
        out.append(_rounded_loop(x0, x1, y0, y1, CORNER_RADIUS + gap, True))
    w, e, sth, nth = xs[0], xs[-1], ys[0], ys[-1]
    out.append(_rounded_loop(w.centre + w.lane(-1), e.centre + e.lane(1),
                             sth.centre + sth.lane(1), nth.centre + nth.lane(-1),
                             plan.settings["Street Width"] * 0.6, False))
    return out


def place_traffic(plan):
    """(routes, cars): the loops and the cars spaced out along them. Cars on a loop share one speed."""
    s = plan.settings
    rng = random.Random(int(s["Seed"]) * 7351 + 11)
    loops = routes(plan)
    cars = []
    if s["Traffic"] <= 0.01:
        return loops, cars
    speed = s["Traffic Speed"]
    for i, pts in enumerate(loops):
        length = loop_length(pts)
        n = min(int(length / 11.0), int(length * s["Traffic"] / 16.0 + rng.random()))
        if n <= 0:
            continue
        start = rng.random()
        for k in range(n):
            phase = (start + (k + rng.uniform(-0.2, 0.2)) / n) % 1.0
            key = rng.choice(("hatchback", "sedan", "city_car", "hatchback", "sedan", "van"))
            cars.append(Car(key, i, phase, speed, length, rng.random()))
    return loops, cars


def car_at(loop, length, t):
    """(x, y, heading) of a car `t` (0..1) of the way round a loop: the same sampling the node group does."""
    d = (t % 1.0) * length
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        seg = math.dist(a, b)
        if d <= seg or i == n - 1:
            f = d / seg if seg else 0.0
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, math.atan2(b[1] - a[1], b[0] - a[0])
        d -= seg
