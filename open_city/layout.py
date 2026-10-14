# SPDX-License-Identifier: GPL-3.0-or-later
"""Street and block layout, zoning, lot packing and building-type selection. No bpy.

`plan_town(settings)` turns the town settings into a `Plan`: streets, blocks and one record per
building (its footprint, where it stands, which way it faces and every input of its building module).
The same settings always give the same plan.

The town is a small grid of blocks. Each block is a raised island (sidewalk all round) with streets on
every side; one street is the main street. Blocks are zoned:

    mixed        on the main street: corner buildings, a continuous row of shops and apartments
    rows         quiet streets at high density: townhouses with stoops, the odd corner shop
    houses       quiet streets at low density: detached houses in gardens
    park         paths, lawns, trees, a fountain

Buildings line the edge of the buildable area (inside the sidewalk). Every edge is filled from left to
right with whole bays; the bay width of a row is adjusted a little so the row fills its frontage
exactly, so there are no slivers between buildings and nothing is stretched.
"""

import math
import random

from . import styles

CURB = 0.15            # kerb height: islands and sidewalks stand this high above the road
CORNER_RADIUS = 2.2    # rounded kerbs at the corners of a block
ROW_GAP = 0.8          # between neighbours in a row: clears their cornices, belt courses and eaves
PARK_STRIP = 2.2       # a lane of parked cars along a kerb
TWO_SIDED = 8.2        # narrower streets park on one side only, so two lanes of traffic still pass

S, E, N, W = "S", "E", "N", "W"


class Edge:
    """One side of a block's buildable area, seen from the street.

    `start` is the end on the viewer's left, `u` runs to the right along the edge, `n` points into the
    block. A building module's local +X is `u` and its local +Y is `n`, so `rot` is its turn about Z.
    """

    def __init__(self, key, start, u, length, street):
        self.key = key
        self.start = start
        self.u = u
        self.n = (-u[1], u[0])
        self.length = length
        self.rot = math.atan2(u[1], u[0])
        self.street = street

    def at(self, a, d=0.0):
        """World (x, y) of a point `a` along the edge and `d` into the block."""
        return (self.start[0] + self.u[0] * a + self.n[0] * d, self.start[1] + self.u[1] * a + self.n[1] * d)


class Street:
    def __init__(self, axis, index, centre, lo, hi, width, main=False):
        self.axis = axis          # "x": runs along x (a horizontal street), "y": runs along y
        self.index = index
        self.centre = centre      # y of a horizontal street, x of a vertical one
        self.lo, self.hi = lo, hi
        self.width = width
        self.main = main
        self.parking = set()      # kerbs with parked cars: +1 is the +y (or +x) side, -1 the other

    def carriageway(self):
        """(centre, lane spacing) of the moving traffic, off the street centre, clear of parked cars."""
        lo = -self.width / 2 + (PARK_STRIP if -1 in self.parking else 0.0)
        hi = self.width / 2 - (PARK_STRIP if 1 in self.parking else 0.0)
        return (lo + hi) / 2, (hi - lo) / 4

    def lane(self, heading):
        """Offset off the street centre of the lane driving along +axis (heading +1) or back (-1).
        Traffic keeps right."""
        c, q = self.carriageway()
        right = -1 if self.axis == "x" else 1     # the driver's right when heading +axis
        return c + right * heading * q


class Block:
    def __init__(self, index, ix, iy, x0, x1, y0, y1):
        self.index, self.ix, self.iy = index, ix, iy
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.kind = "rows"
        self.edges = {}
        self.buildings = []
        self.gaps = []            # (edge key, a0, a1, kind) unbuilt frontage: "garden" or "alley"

    def inner(self, sw):
        return self.x0 + sw, self.x1 - sw, self.y0 + sw, self.y1 - sw


class Building:
    """One building of the plan: where it stands and every input of its `OC Building` modifier."""

    def __init__(self, lot, role, edge, a0, width, depth, setback, params):
        self.lot = lot
        self.role = role
        self.edge = edge
        self.a0 = a0
        self.width = width
        self.depth = depth
        self.setback = setback
        self.params = params
        cx, cy = edge.at(a0 + width / 2, setback)
        self.x, self.y = cx, cy
        self.rot = edge.rot

    @property
    def bay(self):
        return self.params["Bay Width"]

    def footprint(self):
        """World-space corners of the footprint (counter-clockwise)."""
        e = self.edge
        a0, a1 = self.a0, self.a0 + self.width
        d0, d1 = self.setback, self.setback + self.depth
        return [e.at(a0, d0), e.at(a1, d0), e.at(a1, d1), e.at(a0, d1)]

    def bbox(self):
        pts = self.footprint()
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        return min(xs), max(xs), min(ys), max(ys)

    def entrance(self):
        """(a, depth of the stoop) of the front door along the edge, or None."""
        e = styles.entrance_bay(self.params)
        a = self.a0 + (e + 0.5) * self.bay
        p = self.params
        if p["Ground Use"] == 1:
            stoop = 0.5
        else:
            steps = max(1, math.ceil(p["Plinth Height"] / 0.18))
            stoop = 0.8 + (steps - 1) * 0.3
        return a, stoop

    def shop_kind(self):
        return self.params.get("Shop Kind", "") if self.params["Ground Use"] == 1 else ""

    def module_inputs(self):
        """Only the values the building node group takes."""
        from .params import BY_NAME
        return {k: v for k, v in self.params.items() if k in BY_NAME}


class Plan:
    def __init__(self, settings):
        self.settings = settings
        self.streets = []
        self.blocks = []
        self.buildings = []
        self.extent = (0.0, 0.0, 0.0, 0.0)    # the road network, x0 x1 y0 y1
        self.main = None

    def summary(self):
        kinds = {}
        for b in self.blocks:
            kinds[b.kind] = kinds.get(b.kind, 0) + 1
        return (f"{len(self.buildings)} buildings on {len(self.blocks)} blocks "
                f"({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))})")


# -- packing ------------------------------------------------------------------------------------------------
def _partition(rng, total, lo, hi):
    """Split `total` bays into building widths in [lo, hi]; never leaves a sliver."""
    out = []
    left = total
    while left > 0:
        if left <= hi:
            if left >= lo:
                out.append(left)
                break
            if out:
                out[-1] += left
                break
            out.append(left)
            break
        k = rng.randint(lo, hi)
        if 0 < left - k < lo:
            k = left - lo if left - lo >= lo else left
        out.append(k)
        left -= k
    return out


def _fit(length, bay):
    """Whole bays filling `length` with a bay width close to `bay`: (count, bay width)."""
    n = max(1, int(round(length / bay)))
    w = length / n
    while w > bay * 1.18 and length / (n + 1) >= bay * 0.86:
        n += 1
        w = length / n
    while w < bay * 0.86 and n > 1:
        n -= 1
        w = length / n
    return n, w


def _pack_row(rng, length, bay, lo, hi, alley_chance):
    """Runs of buildings filling a frontage: [("b", a0, bays, bay_w) | ("gap", a0, width, kind)]."""
    pieces = [(0.0, length)]
    if length > 22 and rng.random() < alley_chance:
        aw = rng.uniform(2.4, 3.2)
        cut = rng.uniform(0.35, 0.65) * (length - aw)
        pieces = [(0.0, cut), (cut + aw, length - cut - aw)]
    out = []
    for i, (a0, plen) in enumerate(pieces):
        if i:
            out.append(("gap", pieces[i - 1][0] + pieces[i - 1][1], a0 - (pieces[i - 1][0] + pieces[i - 1][1]),
                        "alley"))
        if plen < bay * 0.86 * lo:
            out.append(("gap", a0, plen, "garden"))
            continue
        n, _w = _fit(plen, bay)
        # the small gaps between neighbours come out of the bays, so the row still fills its frontage;
        # a bay may vary a little from the town's, never so much that the windows look out of place
        best = None
        for k in (n, n - 1, n + 1):
            if k < 1:
                continue
            counts = _partition(rng, k, lo, hi)
            w = (plen - (len(counts) - 1) * ROW_GAP) / k
            if 0.85 * bay <= w <= 1.2 * bay and (best is None or abs(w - bay) < abs(best[1] - bay)):
                best = (counts, w)
        if best is None:
            out.append(("gap", a0, plen, "garden"))
            continue
        counts, w = best
        a = a0
        for bays in counts:
            out.append(("b", a, bays, w))
            a += bays * w + ROW_GAP
    return out


# -- the plan -------------------------------------------------------------------------------------------------
def plan_town(settings):
    from .params import town_defaults
    s = town_defaults()
    s.update(settings)
    rng = random.Random(int(s["Seed"]) * 7919 + 17)
    plan = Plan(s)
    road, sw = s["Street Width"], s["Sidewalk Width"]
    nx, ny = int(s["Blocks X"]), int(s["Blocks Y"])
    var = s["Block Variation"]
    bws = [s["Block Width"] * (1 + var * rng.uniform(-0.3, 0.3)) for _ in range(nx)]
    bds = [s["Block Depth"] * (1 + var * rng.uniform(-0.3, 0.3)) for _ in range(ny)]
    tw = sum(bws) + (nx + 1) * road
    td = sum(bds) + (ny + 1) * road
    X0, Y0 = -tw / 2, -td / 2
    plan.extent = (X0, X0 + tw, Y0, Y0 + td)

    xs, cur = [], X0 + road
    for w in bws:
        xs.append((cur, cur + w))
        cur += w + road
    ys, cur = [], Y0 + road
    for d in bds:
        ys.append((cur, cur + d))
        cur += d + road

    main_j = ny // 2 if ny >= 2 else 0
    for j in range(ny + 1):
        yc = (ys[j][0] if j < ny else ys[-1][1] + road) - road / 2
        plan.streets.append(Street("x", j, yc, X0, X0 + tw, road, main=(j == main_j)))
    for i in range(nx + 1):
        xc = (xs[i][0] if i < nx else xs[-1][1] + road) - road / 2
        plan.streets.append(Street("y", i, xc, Y0, Y0 + td, road))
    plan.main = plan.streets[main_j]
    hstreets = {st.index: st for st in plan.streets if st.axis == "x"}
    vstreets = {st.index: st for st in plan.streets if st.axis == "y"}

    for j in range(ny):
        for i in range(nx):
            b = Block(len(plan.blocks), i, j, xs[i][0], xs[i][1], ys[j][0], ys[j][1])
            ix0, ix1, iy0, iy1 = b.inner(sw)
            b.edges = {
                S: Edge(S, (ix0, iy0), (1.0, 0.0), ix1 - ix0, hstreets[j]),
                N: Edge(N, (ix1, iy1), (-1.0, 0.0), ix1 - ix0, hstreets[j + 1]),
                W: Edge(W, (ix0, iy1), (0.0, -1.0), iy1 - iy0, vstreets[i]),
                E: Edge(E, (ix1, iy0), (0.0, 1.0), iy1 - iy0, vstreets[i + 1]),
            }
            plan.blocks.append(b)

    # parked cars line the kerbs of blocks; a narrow street keeps them to one side
    if s["Parking"] > 0.01:
        for st in plan.streets:
            n = nx if st.axis == "y" else ny
            sides = [k for k in (-1, 1) if 0 <= st.index + (k - 1) // 2 < n]
            if len(sides) == 2 and road < TWO_SIDED:
                sides = [1 if st.index % 2 else -1]
            st.parking = set(sides)
    _zone(plan, rng, main_j)
    namer = styles.Namer(rng)
    for b in plan.blocks:
        if b.kind == "park":
            continue
        if b.kind == "houses":
            _fill_houses(plan, b, rng, namer)
        else:
            _fill_rows(plan, b, rng, namer)
    _landmark(plan, rng, namer)
    _resolve_overlaps(plan)
    plan.buildings = [bd for b in plan.blocks for bd in b.buildings]
    return plan


def _zone(plan, rng, main_j):
    s = plan.settings
    blocks = plan.blocks
    n_parks = min(len(blocks) - 1, int(round(s["Parks"] * len(blocks)))) if len(blocks) > 1 else 0
    # parks prefer blocks away from the main street, then the middle of town
    def park_score(b):
        on_main = b.iy == main_j or b.iy + 1 == main_j
        cx, cy = (b.x0 + b.x1) / 2, (b.y0 + b.y1) / 2
        return (on_main, math.hypot(cx, cy) + rng.random() * 25)
    for b in sorted(blocks, key=park_score)[:n_parks]:
        b.kind = "park"
    for b in blocks:
        if b.kind == "park":
            continue
        on_main = b.iy == main_j or b.iy + 1 == main_j
        if on_main and s["Density"] >= 0.5:
            b.kind = "mixed"
        elif s["Density"] >= 0.6:
            b.kind = "rows"
        else:
            b.kind = "houses"


def _add(plan, block, rng, namer, role, edge, a0, bays, bay_w, deep, setback=0.0, **extra):
    town = dict(plan.settings)
    town["Bay Width"] = bay_w
    used = [bd.params.get("Scheme") for bd in block.buildings[-3:]]
    p = styles.style(rng, role, town, bays, deep, namer, used)
    p["Bay Width"] = bay_w
    p.update(extra)
    lot = f"{block.index}{edge.key}{len(block.buildings)}"
    bd = Building(lot, role, edge, a0, bays * bay_w, deep * bay_w, setback, p)
    block.buildings.append(bd)
    return bd


def _fill_rows(plan, block, rng, namer):
    """The main-street edge first (corners and a continuous row), then the quiet edge (a row, or houses in
    gardens), then the short sides (rows in dense towns, gardens otherwise)."""
    s = plan.settings
    B = s["Bay Width"]
    density = s["Density"]
    eS, eN, eW, eE = (block.edges[k] for k in (S, N, W, E))
    Ly = eW.length
    depth_room = (Ly - 3.0) / 2                    # leave a courtyard of at least 3 m
    max_deep = max(1, int(depth_room // B))
    corner = {}                                     # (edge, end) -> (width, depth) reserved, or None
    used = {}
    for e in sorted((eS, eN), key=lambda e: not e.street.main):
        other = N if e.key == S else S
        if block.kind == "mixed" and not e.street.main and density < 0.85:
            room = Ly - used.get(other, depth_room) - 3.0
            used[e.key] = _house_edge(plan, block, e, rng, namer, room)
            corner[(e.key, "L")] = corner[(e.key, "R")] = None
        else:
            used[e.key] = _row_edge(plan, block, e, rng, namer, max_deep, depth_room, corner)
    for e in (eW, eE):
        if e is eW:
            c0, c1 = corner[(N, "R")], corner[(S, "L")]
        else:
            c0, c1 = corner[(S, "R")], corner[(N, "L")]
        a0 = (c0[1] if c0 else used[N if e is eW else S]) + ROW_GAP
        a1 = e.length - (c1[1] if c1 else used[S if e is eW else N]) - ROW_GAP
        if density < 0.8 or not c0 or not c1:
            if a1 - a0 > 0.5:
                block.gaps.append((e.key, a0, a1, "garden"))
            continue
        deep_room = min(c0[0], c1[0])
        deep = max(1, min(3, int(deep_room // (B * 0.86))))
        if a1 - a0 < B * 1.8 or deep < 2:
            if a1 - a0 > 0.5:
                block.gaps.append((e.key, a0, a1, "garden"))
            continue
        for item in _pack_row(rng, a1 - a0, B, 2, 3, 0.3):
            if item[0] == "gap":
                block.gaps.append((e.key, a0 + item[1], a0 + item[1] + item[2], item[3]))
                continue
            _k, a, bays, bw = item
            if rng.random() > 0.3 + 0.6 * density:
                block.gaps.append((e.key, a0 + a, a0 + a + bays * bw, "garden"))
                continue
            _add(plan, block, rng, namer, "row", e, a0 + a, bays, bw, min(deep, max(1, int(deep_room // bw))))
        _attach_run(block, e)


def _row_edge(plan, block, e, rng, namer, max_deep, depth_room, corner):
    """Corner buildings at both ends of an edge and a row between them. Returns the depth used."""
    s = plan.settings
    B = s["Bay Width"]
    density = s["Density"]
    busy = e.street.main
    cw_bays = rng.choice((3, 3, 4)) if e.length > 30 else 3
    cw_bays = min(cw_bays, max(2, int(e.length // (B * 3))))
    cd_bays = min(rng.choice((3, 4)), max_deep)
    cw, cd = cw_bays * B, cd_bays * B
    if e.length < 2 * cw + 2 * B:
        cw = min(cw, e.length / 2)
    ends = {}
    for end in ("L", "R"):
        ends[end] = busy or rng.random() < 0.45 + 0.5 * density
        corner[(e.key, end)] = (cw, cd)
    mid0, mid1 = cw + ROW_GAP, e.length - cw - ROW_GAP
    row_deep = min(cd_bays, max_deep, rng.choice((3, 3, 4)))
    lo, hi = (2, 4) if busy else (2, 3)
    runs = _pack_row(rng, mid1 - mid0, B, lo, hi, 0.12 if busy else 0.3) if mid1 - mid0 > 1.0 else []
    deepest = cd
    for item in runs:
        if item[0] == "gap":
            block.gaps.append((e.key, mid0 + item[1], mid0 + item[1] + item[2], item[3]))
            continue
        _k, a, bays, bw = item
        if not busy and rng.random() > 0.3 + 0.65 * density:
            block.gaps.append((e.key, mid0 + a, mid0 + a + bays * bw, "garden"))
            continue
        role = "shop" if busy else ("shop" if rng.random() < 0.12 * s["Shops"] else "row")
        deep = min(row_deep, max(1, int(depth_room // bw)))
        deepest = max(deepest, deep * bw)
        _add(plan, block, rng, namer, role, e, mid0 + a, bays, bw, deep)
    for end, a0 in (("L", 0.0), ("R", e.length - cw)):
        if not ends[end]:
            block.gaps.append((e.key, a0, a0 + cw, "garden"))
            continue
        bays = max(1, int(round(cw / B)))
        bw = cw / bays
        role = "corner" if (busy or rng.random() < s["Shops"] * 0.4) else "row"
        extra = {"Corner Side": 1 if end == "L" else 2} if role == "corner" else {}
        _add(plan, block, rng, namer, role, e, a0, bays, bw, max(1, int(round(cd / bw))), **extra)
    _attach_run(block, e)
    return deepest


def _house_edge(plan, block, e, rng, namer, room):
    """Detached houses in gardens along one edge, set back behind front gardens. Returns the depth used."""
    s = plan.settings
    B = s["Bay Width"]
    setback = rng.uniform(2.2, 3.4)
    deep = min(3, int((room - setback) // B))
    if deep < 2:
        block.gaps.append((e.key, 0.0, e.length, "garden"))
        return 0.0
    a = 1.2 + rng.uniform(0.0, 1.5)
    while True:
        bays = rng.choice((2, 2, 3))
        w = bays * B
        if a + w > e.length - 1.2:
            break
        if rng.random() < 0.4 + 0.6 * s["Density"]:
            _add(plan, block, rng, namer, "house", e, a, bays, B, deep, setback)
        else:
            block.gaps.append((e.key, a, a + w, "garden"))
        a += w + rng.uniform(2.8, 5.5)
    return setback + deep * B


def _attach_run(block, edge):
    """Neighbours along an edge that touch share a party wall: no windows or quoins there."""
    on = sorted((bd for bd in block.buildings if bd.edge is edge), key=lambda bd: bd.a0)
    for a, b in zip(on, on[1:]):
        if (b.a0 - (a.a0 + a.width)) < ROW_GAP + 0.05:
            a.params["Attached Right"] = True
            b.params["Attached Left"] = True
            # a corner building keeps its street side; the attached side is the inner one
    for bd in on:
        cs = bd.params.get("Corner Side", 0)
        if cs == 1:
            bd.params["Attached Left"] = False
        elif cs == 2:
            bd.params["Attached Right"] = False


def _fill_houses(plan, block, rng, namer):
    """Detached houses with front gardens along the long edges, one on each short side if it fits."""
    s = plan.settings
    B = s["Bay Width"]
    eS, eN, eW, eE = (block.edges[k] for k in (S, N, W, E))
    used = {S: _house_edge(plan, block, eS, rng, namer, eW.length / 2 - 1.5)}
    used[N] = _house_edge(plan, block, eN, rng, namer, eW.length - used[S] - 3.0)
    for e in (eW, eE):
        a0 = (used[N] if e is eW else used[S]) + 1.5
        a1 = e.length - (used[S] if e is eW else used[N]) - 1.5
        w = 2 * B
        deep = 2 if (eS.length / 2 - 4.0) < 3 * B else 3
        if a1 - a0 >= w + 1.0 and rng.random() < 0.3 + 0.5 * s["Density"]:
            mid = (a0 + a1) / 2
            _add(plan, block, rng, namer, "house", e, mid - w / 2, 2, B, deep, rng.uniform(1.8, 2.6))
        elif a1 - a0 > 0.5:
            block.gaps.append((e.key, a0, a1, "garden"))


def _landmark(plan, rng, namer):
    """One taller civic building or turreted corner, if the dice say so."""
    s = plan.settings
    if rng.random() >= s["Landmarks"]:
        return
    cands = [bd for b in plan.blocks for bd in b.buildings if bd.role == "corner"]
    if not cands:
        cands = [bd for b in plan.blocks for bd in b.buildings if bd.role in ("shop", "row") and bd.width >= 9]
    if not cands:
        return
    # prefer a building facing a park, then the main street
    parks = [b for b in plan.blocks if b.kind == "park"]

    def score(bd):
        d = min((math.hypot(bd.x - (p.x0 + p.x1) / 2, bd.y - (p.y0 + p.y1) / 2) for p in parks), default=0.0)
        return (not bd.edge.street.main, bd.params["Bays Wide"] < 4, d + rng.random() * 8)
    bd = sorted(cands, key=score)[0]
    p = bd.params
    keep = {k: p[k] for k in ("Bays Wide", "Bays Deep", "Bay Width", "Attached Left", "Attached Right",
                              "Corner Side")}
    town = dict(s)
    town["Bay Width"] = p["Bay Width"]
    new = styles.style(rng, "landmark", town, p["Bays Wide"], p["Bays Deep"], namer)
    new.update(keep)
    # a clock tower wants a broad civic front; a narrow corner gets a turret instead
    if new["Tower"] == 2 and keep["Bays Wide"] < 4 and keep["Corner Side"]:
        new["Tower"] = 1
        new["Roof Type"] = 4
    elif new["Tower"] == 1 and keep["Corner Side"] == 0:
        new["Tower"] = 2
        new["Roof Type"] = 0
    if new["Tower"] == 2:
        new["Floors"] = max(3, min(new["Floors"] - 1, 4))
        new["Entrance Bay"] = -1
    bd.params = new
    bd.role = "landmark"


def _resolve_overlaps(plan):
    """A last safety net: drop any building whose footprint overlaps an earlier one."""
    kept = []
    for b in plan.blocks:
        out = []
        for bd in b.buildings:
            x0, x1, y0, y1 = bd.bbox()
            clash = False
            for o in kept:
                ox0, ox1, oy0, oy1 = o.bbox()
                if x0 < ox1 - 0.05 and ox0 < x1 - 0.05 and y0 < oy1 - 0.05 and oy0 < y1 - 0.05:
                    clash = True
                    break
            if not clash:
                out.append(bd)
                kept.append(bd)
        b.buildings = out
