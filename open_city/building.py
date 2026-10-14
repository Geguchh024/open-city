# SPDX-License-Identifier: GPL-3.0-or-later
"""Parametric building assembly and facade generation: the `OC Building` node group.

A building is a grid of slots: bays across each of its four walls times floors. Every slot gets one
base module (a window, French door, storefront, door, or nothing) and any number of add-ons stacked in
the same place (shutters, flower boxes, balconies, awnings). Walls, bands, cornices, corners and the
roof are built to the exact footprint around that grid. Changing the width adds bays, changing the
floors adds rows of slots and moves every band and the roof; nothing is ever stretched.

The work is split over four sub-groups that share the building's inputs:

    OC Building Shell    walls, plinth, belt course, string courses, cornice, quoins or pilasters
    OC Building Facade   the slot grid: base modules, add-ons, shop fascia and lettering
    OC Building Roof     parapet, gable, hip or mansard roof, dormers, chimneys, rooftop clutter
    OC Building Tower    a corner turret or a clock tower
    OC Building          the master: calls the four and stores the palette for the shaders

Local frame: the front wall faces -Y and runs along X, centred on x = 0; the building stands on z = 0
and reaches back to y = depth.
"""

import math

from . import params as P
from .gn import Group
from .kit import openings as O
from .kit import roofs as R
from .kit.parts import Kit, V, val, vclamp, vfloor, vmax, vmin, xyz

BUILDING = "OC Building"
SHELL, FACADE, ROOF, TOWER = ("OC Building Shell", "OC Building Facade", "OC Building Roof",
                              "OC Building Tower")
SUBGROUPS = (SHELL, FACADE, ROOF, TOWER)

FRONT, RIGHT, BACK, LEFT = range(4)


def _inputs():
    out = []
    for name, kind, default, opts in P.BUILDING_PARAMS:
        o = {k: v for k, v in opts.items() if k in ("panel", "min", "max", "subtype", "tip")}
        o["default"] = default
        out.append((name, kind, o))
    return out


def _call(g, tree, values):
    n = g.nodes.new("GeometryNodeGroup")
    n.node_tree = tree
    for s in n.inputs:
        if s.name in values:
            g.set(n, s.name, val(values[s.name]))
    return n


class Ctx:
    """Everything a building sub-group needs: the graph, the inputs, sizes in metres and common flags."""

    def __init__(self, G):
        self.G = G
        g, i = self.g, self.i = G.g, G.i
        self.k = Kit(g)
        self.B, self.F = V(i("Bay Width")), V(i("Floor Height"))
        self.Gh, self.P = V(i("Ground Height")), V(i("Plinth Height"))
        self.nx, self.ny, self.nf = V(i("Bays Wide")), V(i("Bays Deep")), V(i("Floors"))
        self.W, self.D = self.nx * self.B, self.ny * self.B
        self.hw = self.W / 2
        self.zg = self.P + self.Gh                          # top of the ground floor
        self.H = self.zg + (self.nf - 1) * self.F           # top of the walls
        self.ww = vclamp(self.B * 0.42, 0.75, 1.6)          # window size, shared by every module
        self.wh = vclamp(self.F * 0.58, 1.1, 2.3)
        self.zs = vmax(V(0.55), self.F - self.wh - 0.62)
        self.detail = V(i("Detail"))
        self.has_detail = g.gt(val(self.detail), 0.5)
        self.roof_t = i("Roof Type")
        self.flatish = g.any_of(g.lt(self.roof_t, 1.5), g.eq(self.roof_t, 4.0))
        self.pitched = g.lnot(self.flatish)
        self.shop = g.eq(i("Ground Use"), 1.0)
        self.upper = g.gt(val(self.nf), 1.5)
        self.att_l, self.att_r = i("Attached Left"), i("Attached Right")
        self.tower = i("Tower")
        self.corner_side = i("Corner Side")
        self.turret_right = g.lnot(g.eq(self.corner_side, 1.0))
        self.Hc = self.H + self.sel(self.pitched, 0.14, 0.28)   # top of the main cornice
        self.mod_values = {"Bay": self.B, "Floor": self.F, "Ground": self.Gh, "Plinth": self.P,
                           "Win W": self.ww, "Win H": self.wh, "Sill": self.zs, "Detail": self.detail}

    def sel(self, cond, if_true, if_false, kind="FLOAT"):
        return V(self.g.select(cond, val(if_false), val(if_true), kind))

    def side_len(self, s):
        return self.W if s in (FRONT, BACK) else self.D

    def side_bays(self, s):
        return self.nx if s in (FRONT, BACK) else self.ny

    def on_side(self, s, t, z, inset=0.0):
        """Position `t` along side `s` (left to right as seen from outside), `inset` into the wall."""
        hw, D = self.hw, self.D
        if s == FRONT:
            return xyz(t, inset, z)
        if s == RIGHT:
            return xyz(hw - inset, D / 2 + t, z)
        if s == BACK:
            return xyz(-V(t), D - inset, z)
        return xyz(-hw + inset, D / 2 - t, z)

    def spin(self, s):
        return self.g.euler(0.0, 0.0, s * math.pi / 2)

    def wall_part(self, geo, upper=True):
        i = self.i
        color, kind = (i("Wall Color"), i("Wall Kind")) if upper else (i("Ground Color"), i("Ground Kind"))
        geo = self.g.store_color(geo, "oc_wall", color)
        geo = self.g.store(geo, "oc_wallkind", kind, domain="POINT")
        return self.k.paint(geo, "OC Wall")

    def finish(self):
        return self.G.finish(Geometry=self.k.result())


def _subgroup(name, build, trees):
    c = Ctx(Group(name, _inputs(), [("Geometry", "geometry")]))
    build(c, trees)
    return c.finish()


# -- walls, bands, cornices, corners ------------------------------------------------------------------------
def _shell(c, _trees):
    g, i, k = c.g, c.i, c.k
    hw, D, H, F = c.hw, c.D, c.H, c.F

    k.add(c.wall_part(k.raw_box(-hw, hw, 0.0, D, 0.0, c.zg), upper=False))
    k.when(c.upper, lambda: k.add(c.wall_part(k.raw_box(-hw, hw, 0.0, D, c.zg - 0.01, H))))
    k.box(-hw - 0.07, hw + 0.07, -0.07, D + 0.07, 0.0, vmax(c.P, 0.12), "OC Stone", 0.03)

    def ring(out, z0, z1, bevel=0.0):
        k.box(-hw - out, hw + out, -V(out), D + out, z0, z1, "OC Trim", bevel)

    def dentils(z0, z1, out=0.13, spacing=0.42):
        parts = []
        block = k.raw_box(-0.085, 0.085, -V(out), 0.02, z0, z1, 0.015)
        for s in range(4):
            n = vmax(vfloor((c.side_len(s) - 0.3) / spacing), 1.0)
            t = (V(g.index()) - (n - 1) / 2) * spacing
            pts = g.points(val(n), c.on_side(s, t, 0.0))
            skip = {LEFT: c.att_l, RIGHT: c.att_r}.get(s)
            parts.append(g.realize(g.instance(pts, block, rotation=c.spin(s),
                                              selection=g.lnot(skip) if skip is not None else None)))
        k.add(g.join(*parts), "OC Trim")

    def belt():
        zb = c.zg
        ring(0.04, zb - 0.3, zb - 0.02)
        k.when(c.has_detail, lambda: dentils(zb - 0.19, zb - 0.02, 0.12))
        ring(0.17, zb - 0.02, zb + 0.17, bevel=0.03)
    k.when(c.upper, belt)

    def courses():
        band = k.raw_box(-hw - 0.05, hw + 0.05, -0.05, D + 0.05, -0.06, 0.06, 0.02)
        pts = g.points(val(vmax(c.nf - 2, 0.0)), xyz(0.0, 0.0, c.zg + F * (V(g.index()) + 1)))
        k.add(g.realize(g.instance(pts, band)), "OC Trim")
    k.when(c.has_detail, courses)

    def big_cornice():
        ring(0.05, H - 0.5, H - 0.05)
        k.when(c.has_detail, lambda: dentils(H - 0.25, H - 0.05, 0.16, 0.4))
        ring(0.34, H - 0.05, H + 0.2, bevel=0.04)
        ring(0.26, H + 0.2, H + 0.28, bevel=0.02)

    def eave_cornice():
        ring(0.04, H - 0.32, H - 0.02)
        ring(0.14, H - 0.02, H + 0.14, bevel=0.025)
    k.when(c.flatish, big_cornice)
    k.when(c.pitched, eave_cornice)

    # quoins or pilasters on every free corner; corners 0..3: front left, front right, back right, back left
    qz0 = c.sel(c.shop, c.zg, c.P)
    idx = g.index()
    is_left = g.lor(g.eq(idx, 0.0), g.eq(idx, 3.0))
    corner_pts = g.points(4, xyz(c.sel(is_left, -hw, hw), c.sel(g.lt(idx, 1.5), 0.0, D), 0.0))
    turret_corner = g.land(g.eq(c.tower, 1.0), g.eq(idx, val(c.sel(c.turret_right, 1.0, 0.0))))
    corner_sel = g.lnot(g.any_of(g.land(is_left, c.att_l), g.land(g.lnot(is_left), c.att_r), turret_corner))
    corner_rot = g.euler(0.0, 0.0, g.mul(idx, math.pi / 2))

    def quoins():
        top = H - 0.5
        n = vmax(vfloor((top - qz0) / 0.44), 0.0)
        pts = g.points(val(n), xyz(0.0, 0.0, qz0 + (V(g.index()) + 0.5) * 0.44))
        a = k.raw_box(-0.06, 0.62, -0.06, 0.36, -0.19, 0.19, 0.03)
        b = k.raw_box(-0.06, 0.36, -0.06, 0.62, -0.19, 0.19, 0.03)
        stack = g.realize(g.instance(pts, g.library([a, b]), pick=True, index=g.mod(g.index(), 2.0)))
        k.add(g.realize(g.instance(corner_pts, stack, rotation=corner_rot, selection=corner_sel)), "OC Trim")

    def pilasters():
        top = H - 0.5
        col = g.join(k.raw_box(-0.07, 0.45, -0.07, 0.45, qz0, top, 0.03),
                     k.raw_box(-0.12, 0.52, -0.12, 0.52, qz0, qz0 + 0.42, 0.03),
                     k.raw_box(-0.12, 0.52, -0.12, 0.52, top - 0.26, top, 0.03))
        k.add(g.realize(g.instance(corner_pts, col, rotation=corner_rot, selection=corner_sel)), "OC Trim")
    k.when(g.eq(i("Corner Style"), 1.0), quoins)
    k.when(g.eq(i("Corner Style"), 2.0), pilasters)


# -- facade generation: the slot grid ---------------------------------------------------------------------------
def _facade(c, trees):
    g, i, k = c.g, c.i, c.k
    sel = c.sel
    base_lib = g.library([_call(g, trees[name], c.mod_values).outputs[0] for name, _fn in O.BASE])
    addon = {name: _call(g, trees[name], c.mod_values).outputs[0] for name, _fn in O.ADDONS}

    clouds = []
    for s in range(4):
        n = c.side_bays(s)
        idx = V(g.index())
        b = V(g.mod(val(idx), val(n)))
        fl = vfloor(idx / n)
        t = -c.side_len(s) / 2 + (b + 0.5) * c.B
        z = sel(g.lt(val(fl), 0.5), 0.0, c.zg + (fl - 1) * c.F)
        pts = g.points(val(n * c.nf), c.on_side(s, t, z))
        clouds.append(g.store_many(pts, [("oc_s", float(s)), ("oc_b", val(b)), ("oc_f", val(fl)),
                                         ("oc_n", val(n))], domain="POINT"))
    slots = g.join(*clouds)
    s, b, fl, n = (V(g.named(a)) for a in ("oc_s", "oc_b", "oc_f", "oc_n"))
    sv, bv, fv = val(s), val(b), val(fl)
    seed = i("Seed")

    def is_(x, v):
        return g.eq(val(x), float(v))

    front = is_(s, FRONT)
    street = g.any_of(front, g.land(is_(s, LEFT), g.eq(c.corner_side, 1.0)),
                      g.land(is_(s, RIGHT), g.eq(c.corner_side, 2.0)))
    skip = g.lor(g.land(is_(s, LEFT), c.att_l), g.land(is_(s, RIGHT), c.att_r))
    ground = g.lt(fv, 0.5)
    ent_in = i("Entrance Bay")
    ent = sel(g.lor(g.lt(ent_in, -0.5), g.ge(ent_in, val(c.nx))), vfloor((c.nx - 1) / 2), V(ent_in))
    is_ent = g.land(front, g.eq(bv, val(ent)))
    # randomness per mirrored column keeps facades symmetric
    col_id = val(vmin(b, n - 1 - b) + s * 32.0)
    r_col = g.rand(0.0, 1.0, seed=g.add(seed, 11), id=g.math("ROUND", col_id))
    r_slot = g.rand(0.0, 1.0, seed=g.add(seed, 23), id=g.index())
    r_flower = g.rand(0.0, 1.0, seed=g.add(seed, 37), id=g.math("ROUND", val(V(col_id) + fl * 100.0)))
    style = V(i("Window Style"))

    # near a corner turret the upper windows give way to the turret
    tr = c.turret_right
    by_turret = g.all_of(
        g.eq(c.tower, 1.0), g.gt(fv, 0.5),
        g.any_of(g.land(front, g.eq(bv, val(sel(tr, c.nx - 1, 0.0)))),
                 g.all_of(is_(s, RIGHT), tr, g.eq(bv, 0.0)),
                 g.all_of(is_(s, LEFT), g.lnot(tr), g.eq(bv, val(c.ny - 1)))))

    balcony = g.all_of(street, g.lnot(ground), g.lt(r_col, i("Balconies")), g.gt(val(c.nx), 1.5))
    win_up = sel(street, style, sel(g.lt(r_slot, 0.3), float(O.SMALL), style))
    win_up = sel(balcony, float(O.FRENCH), win_up)
    win_low = style + float(O.SASH_G)
    shop_front = sel(is_ent, float(O.SHOP_DOOR), float(O.SHOP_WIN))
    res_front = sel(is_ent, float(O.RES_DOOR), win_low)
    g_street = sel(front, sel(c.shop, shop_front, res_front), sel(c.shop, float(O.SHOP_WIN), win_low))
    back_door = g.land(is_(s, BACK), g.eq(bv, val(vfloor((n - 1) / 2))))
    g_other = sel(back_door, float(O.BACK_DOOR), sel(g.lt(r_slot, 0.55), win_low, float(O.EMPTY)))
    base = sel(ground, sel(street, g_street, g_other), win_up)
    base = sel(by_turret, float(O.EMPTY), base)
    keep = g.land(g.lnot(skip), g.lnot(g.eq(val(base), float(O.EMPTY))))

    slots = g.store(slots, "oc_slot", r_slot, domain="POINT")
    rot = g.euler(0.0, 0.0, g.mul(sv, math.pi / 2))
    k.add(g.realize(g.instance(slots, base_lib, pick=True, index=g.math("ROUND", val(base)), rotation=rot,
                               selection=keep)))

    bv_ = val(base)
    is_window = g.any_of(*[g.eq(bv_, float(m)) for m in (O.SASH, O.ARCH, O.SASH_G, O.ARCH_G)])
    any_window = g.lor(is_window, g.any_of(g.eq(bv_, float(O.WIDE)), g.eq(bv_, float(O.WIDE_G))))

    def stack(lib_names, pick_index, selection):
        lib = g.library([addon[nm] for nm in lib_names])
        k.add(g.realize(g.instance(slots, lib, pick=True, index=pick_index, rotation=rot,
                                   selection=g.land(keep, selection))))

    ground_i = g.tofloat(ground)
    stack(("OC Kit Shutters", "OC Kit Shutters Ground"), ground_i, g.land(is_window, i("Shutters")))
    stack(("OC Kit Flower Box", "OC Kit Flower Box Ground"), ground_i,
          g.all_of(any_window, g.lt(r_flower, i("Flower Boxes"))))
    stack(("OC Kit Balcony", "OC Kit Balcony Stone", "OC Kit Balcony Juliet"), i("Balcony Style"),
          g.eq(bv_, float(O.FRENCH)))
    stack(("OC Kit Awning",), 0, g.all_of(g.gt(i("Awnings"), 0.5),
                                          g.lor(g.eq(bv_, float(O.SHOP_WIN)), g.eq(bv_, float(O.SHOP_DOOR)))))

    # shop fascia with raised lettering, on the front and on a corner's side street
    def fascia(side):
        L = c.side_len(side)
        z0, z1 = c.zg - 0.98, c.zg - 0.32
        parts = [
            k.paint(k.raw_box(-L / 2 + 0.02, L / 2 - 0.02, -0.2, 0.02, z0, z1, 0.02), "OC Accent"),
            k.paint(k.raw_box(-L / 2, L / 2, -0.27, 0.02, z1, z1 + 0.09, 0.02), "OC Trim"),
            k.paint(k.raw_box(-L / 2 + 0.02, L / 2 - 0.02, -0.24, 0.02, z0 - 0.05, z0, 0.01), "OC Trim"),
        ]
        text = g.node("GeometryNodeStringToCurves", {"String": i("Shop Name")})
        g.set(text, "Align X", "Center")
        g.set(text, "Align Y", "Middle")
        length = g.out("FunctionNodeStringLength", {"String": i("Shop Name")})
        g.set(text, "Size", val(vmin(V(0.44), (L - 1.4) / (vmax(V(length), 1.0) * 0.68))))
        fill = g.out("GeometryNodeFillCurve", {"Curve": g.realize(text.outputs["Curve Instances"]),
                                               "Mode": "N-gons"})
        letters, _top, _side = g.extrude(fill, offset_scale=0.05, individual=False)
        letters = g.transform(letters, rotation=g.euler(math.pi / 2, 0.0, 0.0))
        letters = g.transform(letters, translation=xyz(0.0, -0.19, (z0 + z1) / 2))
        parts.append(k.paint(letters, "OC Sign Text"))
        return g.transform(g.join(*parts), translation=c.on_side(side, 0.0, 0.0), rotation=c.spin(side))

    k.when(c.shop, lambda: k.add(fascia(FRONT)))
    k.when(g.land(c.shop, g.eq(c.corner_side, 1.0)), lambda: k.add(fascia(LEFT)))
    k.when(g.land(c.shop, g.eq(c.corner_side, 2.0)), lambda: k.add(fascia(RIGHT)))


# -- roofs ---------------------------------------------------------------------------------------------------------
def _roof(c, trees):
    g, i, k = c.g, c.i, c.k
    sel = c.sel
    hw, W, D, Hc, roof_t = c.hw, c.W, c.D, c.Hc, c.roof_t
    seed = i("Seed")

    def parapet():
        z0, z1 = Hc - 0.02, Hc + 0.62
        t = 0.28
        walls = g.join(k.raw_box(-hw, hw, 0.0, t, z0, z1), k.raw_box(-hw, hw, D - t, D, z0, z1),
                       k.raw_box(-hw, -hw + t, t, D - t, z0, z1), k.raw_box(hw - t, hw, t, D - t, z0, z1))
        k.add(c.wall_part(walls))
        e = 0.07
        k.box(-hw - e, hw + e, -e, t + e, z1, z1 + 0.12, "OC Trim", 0.025)
        k.box(-hw - e, hw + e, D - t - e, D + e, z1, z1 + 0.12, "OC Trim", 0.025)
        k.box(-hw - e, -hw + t + e, t + e, D - t - e, z1, z1 + 0.12, "OC Trim", 0.025)
        k.box(hw - t - e, hw + e, t + e, D - t - e, z1, z1 + 0.12, "OC Trim", 0.025)
        k.box(-hw + t, hw - t, t, D - t, Hc - 0.1, Hc + 0.06, "OC Roof Flat")

    k.when(g.eq(roof_t, 0.0), parapet)
    k.when(g.eq(roof_t, 1.0), lambda: k.box(-hw - 0.2, hw + 0.2, -0.2, D + 0.2, Hc - 0.02, Hc + 0.03,
                                            "OC Roof Flat"))

    pitch = V(i("Roof Pitch"))
    gable_front = i("Gable Front")
    centre = xyz(0.0, D / 2, 0.0)
    span = sel(gable_front, W, D)
    gable = _call(g, trees[R.GABLE], {
        "Length": sel(gable_front, D, W), "Span": span, "Base": Hc, "Pitch": pitch, "Overhang": 0.42,
        "End L": sel(g.land(c.att_l, g.lnot(gable_front)), 0.0, 0.32),
        "End R": sel(g.land(c.att_r, g.lnot(gable_front)), 0.0, 0.32)})

    def gable_roof():
        geo = g.join(gable.outputs["Roof"], c.wall_part(gable.outputs["Gable"]))
        turn = g.euler(0.0, 0.0, val(sel(gable_front, math.pi / 2, 0.0)))
        k.add(g.transform(g.transform(geo, rotation=turn), translation=centre))
        # a small window high in each free gable end
        rise = span / 2 * V(g.math("TANGENT", g.math("RADIANS", val(pitch))))
        win = _call(g, trees["OC Kit Window Small"], c.mod_values).outputs[0]
        small_bottom = c.zs + c.wh - vmin(c.wh * 0.55, 1.0)
        z = Hc + rise * 0.22 - small_bottom
        gi = V(g.index())
        side = sel(gable_front, gi * 2.0, gi * 2.0 + 1.0)      # front/back or right/left
        pos = xyz(sel(gable_front, 0.0, sel(g.eq(val(gi), 0.0), hw, -hw)),
                  sel(gable_front, sel(g.eq(val(gi), 0.0), 0.0, D), D / 2), z)
        attached = g.select(g.eq(val(gi), 0.0), c.att_l, c.att_r, "BOOLEAN")   # right end first
        free = g.lor(gable_front, g.lnot(attached))
        pts = g.points(2, pos)
        k.add(g.realize(g.instance(pts, win, rotation=g.euler(0.0, 0.0, val(side * (math.pi / 2))),
                                   selection=g.land(free, g.gt(val(rise), 1.7)))))
    k.when(g.eq(roof_t, 2.0), gable_roof)

    hip = _call(g, trees[R.HIP], {"Length": W, "Span": D, "Base": Hc, "Pitch": pitch, "Overhang": 0.42})
    k.when(g.eq(roof_t, 3.0), lambda: k.add(g.transform(hip.outputs["Roof"], translation=centre)))

    mansard = _call(g, trees[R.MANSARD], {"Length": W, "Span": D, "Base": Hc, "Height": c.F * 0.9,
                                          "Inset": 0.7})

    def mansard_roof():
        k.add(g.transform(mansard.outputs["Roof"], translation=centre))
        dormer = _call(g, trees[R.DORMER], {}).outputs[0]
        parts = []
        for s in (FRONT, BACK):
            t = -W / 2 + (V(g.index()) + 0.5) * c.B
            pts = g.points(val(c.nx), c.on_side(s, t, Hc + 0.1, inset=0.06))
            parts.append(g.realize(g.instance(pts, dormer, rotation=c.spin(s))))
        k.add(g.join(*parts))
    k.when(g.eq(roof_t, 4.0), mansard_roof)

    top = sel(g.eq(roof_t, 2.0), V(gable.outputs["Top"]),
              sel(g.eq(roof_t, 3.0), V(hip.outputs["Top"]),
                  sel(g.eq(roof_t, 4.0), V(mansard.outputs["Top"]), Hc + 0.75)))

    # chimneys stand near the side walls and clear the ridge
    cbase = Hc - 0.6
    chimney = _call(g, trees[R.CHIMNEY], {"Height": top + 0.85 - cbase}).outputs[0]
    ci = V(g.index())
    cx = sel(g.eq(val(ci), 0.0), -hw + 0.7, sel(g.eq(val(ci), 1.0), hw - 0.7, 0.0))
    cy = sel(g.lt(val(ci), 1.5), D * 0.58, D * 0.8)
    k.add(g.realize(g.instance(g.points(i("Chimneys"), xyz(cx, cy, cbase)), chimney)))

    # rooftop clutter on flat roofs, one item per cell so nothing overlaps
    def clutter():
        cell = 2.6
        cxn = vmax(vfloor((W - 2.0) / cell), 1.0)
        cyn = vmax(vfloor((D - 2.0) / cell), 1.0)
        q = V(g.index())
        ix = V(g.mod(val(q), val(cxn)))
        iy = vfloor(q / cxn)
        px = -hw + 1.0 + (ix + 0.5) * ((W - 2.0) / cxn)
        py = 1.0 + (iy + 0.5) * ((D - 2.0) / cyn)
        pts = g.points(val(cxn * cyn), xyz(px, py, Hc + 0.06))
        lib = g.library([_call(g, trees[nm], {}).outputs[0] for nm in R.ROOFTOP])
        r1 = g.rand(0.0, 1.0, seed=g.add(seed, 51), id=g.index())
        pick = g.rand(0, 3, seed=g.add(seed, 52), id=g.index(), kind="INT")
        spin = g.euler(0.0, 0.0, g.mul(g.rand(0, 3, seed=g.add(seed, 53), id=g.index(), kind="INT"), math.pi / 2))
        k.add(g.realize(g.instance(pts, lib, pick=True, index=pick, rotation=spin, selection=g.lt(r1, 0.4))))
    k.when(g.all_of(g.lt(roof_t, 1.5), i("Rooftop Units"), g.lnot(g.eq(c.tower, 2.0))), clutter)


# -- towers -------------------------------------------------------------------------------------------------------
def _tower(c, trees):
    g, k = c.g, c.k
    sel = c.sel
    hw, H, Hc, B, F = c.hw, c.H, c.Hc, c.B, c.F

    def turret():
        right = c.turret_right
        r = 1.45
        z0, z1 = c.zg + 0.25, Hc + 1.1
        body = g.out("GeometryNodeMeshCylinder", {"Vertices": 8, "Radius": r, "Depth": val(z1 - z0)},
                     output="Mesh")
        body = c.wall_part(g.transform(body, translation=xyz(0.0, 0.0, (z0 + z1) / 2)))
        corbel = g.out("GeometryNodeMeshCone", {"Vertices": 8, "Radius Top": r + 0.08, "Radius Bottom": 0.35,
                                                "Depth": 1.1}, output="Mesh")
        corbel = k.paint(g.transform(corbel, translation=xyz(0.0, 0.0, z0 - 1.08)), "OC Trim")   # cones sit on z = 0
        band = g.out("GeometryNodeMeshCylinder", {"Vertices": 8, "Radius": r + 0.14, "Depth": 0.3}, output="Mesh")
        band = k.paint(g.transform(band, translation=xyz(0.0, 0.0, z1 + 0.1)), "OC Trim")
        cone = g.out("GeometryNodeMeshCone", {"Vertices": 8, "Radius Top": 0.0, "Radius Bottom": r + 0.3,
                                              "Depth": 3.6}, output="Mesh")
        cone = k.paint(g.transform(cone, translation=xyz(0.0, 0.0, z1 + 0.25)), "OC Roof Tiles")
        finial = k.paint(g.join(
            g.cyl(0.05, 0.9, verts=6, at=xyz(0.0, 0.0, z1 + 3.65)),
            g.transform(g.out("GeometryNodeMeshIcoSphere", {"Radius": 0.14, "Subdivisions": 1}, output="Mesh"),
                        translation=xyz(0.0, 0.0, z1 + 4.0))), "OC Iron")
        # windows on the four faces that look out over the corner, on every upper floor
        win = _call(g, trees["OC Kit Window Small"], c.mod_values).outputs[0]
        wi = V(g.index())
        face = V(g.mod(val(wi), 4.0))
        ang = (face * 45.0 - 112.5) * (math.pi / 180)
        ang = sel(right, ang, math.pi - ang)
        rin = r * math.cos(math.pi / 8)
        wz = c.zg + vfloor(wi / 4.0) * F
        wpts = g.points(val(vmax(c.nf - 1, 0.0) * 4), xyz(V(g.cos(val(ang))) * rin, V(g.sin(val(ang))) * rin, wz))
        wins = g.realize(g.instance(wpts, win, rotation=g.euler(0.0, 0.0, val(ang + math.pi / 2)),
                                    scale=(0.85, 1.0, 1.0)))
        geo = g.join(body, corbel, band, cone, finial, wins)
        k.add(g.transform(geo, translation=xyz(sel(right, hw - 0.3, -hw + 0.3), 0.3, 0.0)))

    def clock_tower():
        T = vclamp(B * 1.3, 3.0, 4.4)
        h = T / 2
        y0 = 0.25
        cy = y0 + h
        z1 = Hc + 2.8
        k.add(c.wall_part(k.raw_box(-h, h, y0, y0 + T, H - 0.4, z1)))
        k.box(-h - 0.14, h + 0.14, y0 - 0.14, y0 + T + 0.14, z1, z1 + 0.25, "OC Trim", 0.03)
        zc0, zc1 = z1 + 0.25, z1 + 0.25 + T * 0.95
        k.box(-h + 0.06, h - 0.06, y0 + 0.06, y0 + T - 0.06, zc0, zc1, "OC Trim", 0.03)
        for x0, y_ in ((-h + 0.02, y0 + 0.02), (h - 0.32, y0 + 0.02), (-h + 0.02, y0 + T - 0.32),
                       (h - 0.32, y0 + T - 0.32)):
            k.box(x0, V(x0) + 0.3, y_, V(y_) + 0.3, zc0, zc1, "OC Stone", 0.02)
        k.box(-h - 0.25, h + 0.25, y0 - 0.25, y0 + T + 0.25, zc1, zc1 + 0.3, "OC Trim", 0.04)
        # a clock face on every side
        rc = T * 0.33
        stand = g.euler(math.pi / 2, 0.0, 0.0)
        dial = g.out("GeometryNodeMeshCylinder", {"Vertices": 24, "Radius": val(rc), "Depth": 0.08}, output="Mesh")
        rim = g.out("GeometryNodeMeshCylinder", {"Vertices": 24, "Radius": val(rc + 0.1), "Depth": 0.05},
                    output="Mesh")
        clock = g.join(
            k.paint(g.transform(dial, rotation=stand, translation=xyz(0.0, -0.06, 0.0)), "OC Prop White"),
            k.paint(g.transform(rim, rotation=stand, translation=xyz(0.0, -0.03, 0.0)), "OC Iron"),
            k.paint(k.raw_box(-0.04, 0.04, -0.14, -0.1, -0.05, rc * 0.8), "OC Iron"),
            k.paint(g.transform(k.raw_box(-0.05, 0.05, -0.16, -0.12, -0.05, rc * 0.6),
                                rotation=g.euler(0.0, 2.1, 0.0)), "OC Iron"))
        ang = V(g.index()) * (math.pi / 2)
        cpos = xyz(V(g.sin(val(ang))) * h, cy - V(g.cos(val(ang))) * h, (zc0 + zc1) / 2)
        k.add(g.realize(g.instance(g.points(4, cpos), clock, rotation=g.euler(0.0, 0.0, val(ang)))))
        pyramid = g.out("GeometryNodeMeshCone", {"Vertices": 4, "Radius Top": 0.0,
                                                 "Radius Bottom": val((h + 0.3) * math.sqrt(2)),
                                                 "Depth": val(T * 1.15)}, output="Mesh")
        pyramid = g.transform(pyramid, rotation=g.euler(0.0, 0.0, math.pi / 4),
                              translation=xyz(0.0, cy, zc1 + 0.3))
        k.add(pyramid, "OC Roof Tiles")
        k.add(g.cyl(0.06, 1.2, verts=6, at=xyz(0.0, cy, zc1 + 0.3 + T * 1.1)), "OC Iron")
        k.ico(0.16, xyz(0.0, cy, zc1 + 0.3 + T * 1.15 + 0.5), "OC Sign Text")

    k.when(g.eq(c.tower, 1.0), turret)
    k.when(g.eq(c.tower, 2.0), clock_tower)


def build_building(trees):
    """Build the four sub-groups and the master `OC Building` group. Returns the master."""
    subs = [_subgroup(SHELL, _shell, trees), _subgroup(FACADE, _facade, trees),
            _subgroup(ROOF, _roof, trees), _subgroup(TOWER, _tower, trees)]
    G = Group(BUILDING, _inputs(), [("Geometry", "geometry")])
    g, i = G.g, G.i
    names = [p[0] for p in P.BUILDING_PARAMS]
    parts = []
    for tree in subs:
        n = g.nodes.new("GeometryNodeGroup")
        n.node_tree = tree
        for name in names:
            g.links.new(i(name), n.inputs[name])
        parts.append(n.outputs[0])
    geo = g.join(*parts)
    # the palette, for the shared materials
    geo = g.store_color(geo, "oc_trim", i("Trim Color"))
    geo = g.store_color(geo, "oc_accent", i("Accent Color"))
    geo = g.store_color(geo, "oc_roof", i("Roof Color"))
    geo = g.store_color(geo, "oc_awning", i("Awning Color"))
    geo = g.store(geo, "oc_stripes", g.tofloat(g.eq(i("Awnings"), 1.0)), domain="POINT")
    return G.finish(Geometry=geo)
