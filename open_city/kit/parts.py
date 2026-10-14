# SPDX-License-Identifier: GPL-3.0-or-later
"""The smallest pieces of the kit: chamfered boxes, an expression helper and a part builder.

Every architectural module is assembled from these, so trims, sills, frames and props all share the
same crisp bevel. A chamfered box is the convex hull of a smaller box grown by an octahedron: exact,
cheap and with no bevel modifier.

`V` wraps a number or a node socket and overloads arithmetic, so module code reads like geometry:

    w = V(i("Win W")) / 2
    k.box(-w - 0.1, w + 0.1, -0.25, 0.03, sill - 0.16, sill, "OC Trim", bevel=0.03)

Plain numbers fold away, so a module written mostly with constants stays a small graph.
"""

import math

import bpy

from .. import materials
from ..gn import Group

CBOX = "OC Kit CBox"


class V:
    """A number or a socket with arithmetic. `V.g` is the graph being built."""

    g = None
    __slots__ = ("x",)

    def __init__(self, x):
        self.x = x.x if isinstance(x, V) else x

    def _op(self, op, other, swap=False):
        a, b = self.x, val(other)
        if swap:
            a, b = b, a
        return V(V.g.math(op, a, b))

    def __add__(self, o):
        return self._op("ADD", o)

    __radd__ = __add__

    def __sub__(self, o):
        return self._op("SUBTRACT", o)

    def __rsub__(self, o):
        return self._op("SUBTRACT", o, True)

    def __mul__(self, o):
        return self._op("MULTIPLY", o)

    __rmul__ = __mul__

    def __truediv__(self, o):
        return self._op("DIVIDE", o)

    def __rtruediv__(self, o):
        return self._op("DIVIDE", o, True)

    def __neg__(self):
        return V(V.g.math("MULTIPLY", self.x, -1.0))


def val(x):
    """The raw number or socket inside `x`."""
    return x.x if isinstance(x, V) else x


def vmin(a, b):
    return V(V.g.min(val(a), val(b)))


def vmax(a, b):
    return V(V.g.max(val(a), val(b)))


def vclamp(a, lo, hi):
    return V(V.g.clamp(val(a), val(lo), val(hi)))


def vfloor(a):
    return V(V.g.floor(val(a)))


def xyz(x=0.0, y=0.0, z=0.0):
    return V.g.xyz(val(x), val(y), val(z))


def build_cbox():
    G = Group(CBOX, [("Size", "vector"), ("Center", "vector"), ("Bevel", "float", {"default": 0.02})],
              [("Mesh", "geometry")])
    g, i = G.g, G.i
    sx, sy, sz = g.split(i("Size"))
    # never let the bevel eat the box
    b = g.min(i("Bevel"), g.mul(g.min(g.min(sx, sy), sz), 0.45))
    b = g.max(b, 0.0005)
    b2 = g.mul(b, 2.0)
    inner = g.out("GeometryNodeMeshCube", {"Size": g.vmath("MAXIMUM", g.vsub(i("Size"), g.xyz(b2, b2, b2)),
                                                           (0.0005, 0.0005, 0.0005))}, output="Mesh")
    idx = g.index()
    axis = g.floor(g.div(idx, 2.0))
    sign = g.sub(1.0, g.mul(g.mod(idx, 2.0), 2.0))
    unit = g.xyz(g.tofloat(g.eq(axis, 0.0)), g.tofloat(g.eq(axis, 1.0)), g.tofloat(g.eq(axis, 2.0)))
    octa = g.points(6, g.vscale(unit, g.mul(sign, b)))
    grown = g.realize(g.instance(inner, octa))
    mesh = g.transform(g.hull(grown), translation=i("Center"))
    return G.finish(Mesh=mesh)


class Kit:
    """Builds one module: parts are added by extents (numbers, sockets or `V`) and joined at the end."""

    def __init__(self, g):
        self.g = g
        V.g = g
        self.parts = []
        self._mats = {}

    # -- materials ---------------------------------------------------------------------
    def mat(self, name):
        sock = self._mats.get(name)
        if sock is None:
            n = self.g.node("GeometryNodeInputMaterial")
            n.material = materials.get(name)
            sock = self._mats[name] = n.outputs[0]
        return sock

    def paint(self, geo, name, selection=None):
        return self.g.material(geo, self.mat(name), selection=selection)

    # -- parts ---------------------------------------------------------------------------
    def raw_box(self, x0, x1, y0, y1, z0, z1, bevel=0.0):
        """A box mesh between the given extents (not added to the module)."""
        g = self.g
        x0, x1, y0, y1, z0, z1 = (V(v) for v in (x0, x1, y0, y1, z0, z1))
        size = xyz(x1 - x0, y1 - y0, z1 - z0)
        centre = xyz((x0 + x1) * 0.5, (y0 + y1) * 0.5, (z0 + z1) * 0.5)
        if bevel:
            n = g.nodes.new("GeometryNodeGroup")
            n.node_tree = bpy.data.node_groups[CBOX]
            g.set(n, "Size", size)
            g.set(n, "Center", centre)
            g.set(n, "Bevel", val(bevel))
            return n.outputs[0]
        return g.box(size, at=centre)

    def box(self, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
        return self.add(self.raw_box(x0, x1, y0, y1, z0, z1, bevel), mat)

    def sym(self, x0, x1, y0, y1, z0, z1, mat, bevel=0.0):
        """Two boxes mirrored across x = 0; give the extents of the one on the positive side."""
        self.box(x0, x1, y0, y1, z0, z1, mat, bevel)
        self.box(-V(x1), -V(x0), y0, y1, z0, z1, mat, bevel)

    def cyl(self, radius, depth, at, mat, verts=12):
        return self.add(self.g.cyl(val(radius), val(depth), verts=verts, at=at), mat)

    def ico(self, radius, at, mat, scale=(1.0, 1.0, 1.0), subdiv=1):
        geo = self.g.out("GeometryNodeMeshIcoSphere", {"Radius": val(radius), "Subdivisions": subdiv},
                         output="Mesh")
        geo = self.g.transform(geo, translation=at, scale=scale)
        return self.add(geo, mat)

    def hull(self, pts, mat):
        """Convex hull of a list of (x, y, z) points (numbers, sockets or V)."""
        g = self.g
        geos = [g.points(1, xyz(*p)) for p in pts]
        return self.add(g.hull(g.join(*geos)), mat)

    def add(self, geo, mat=None):
        if mat is not None:
            geo = self.paint(geo, mat)
        self.parts.append(geo)
        return geo

    def when(self, cond, build):
        """Add the parts made by `build()` only where `cond` (a boolean socket) holds."""
        before = len(self.parts)
        build()
        made = self.parts[before:]
        del self.parts[before:]
        if made:
            self.parts.append(self.g.switch_geo(cond, self.g.join(*made)))

    def result(self):
        if not self.parts:
            return self.g.points(0)
        return self.g.join(*self.parts)


def glass_attrs(g, geo, x0, x1, z0, z1, shop=0.0):
    """Store the pane coordinates (`oc_gu`, `oc_gv`) the glass shader draws blinds and glints from."""
    px, _py, pz = g.split(g.position())
    gu = g.div(g.sub(px, val(x0)), val(V(x1) - x0))
    gv = g.div(g.sub(pz, val(z0)), val(V(z1) - z0))
    geo = g.store(geo, "oc_gu", gu, domain="POINT")
    geo = g.store(geo, "oc_gv", gv, domain="POINT")
    if shop:
        geo = g.store(geo, "oc_shop", shop, domain="POINT")
    return geo


def rot_z(angle):
    return V.g.euler(0.0, 0.0, val(angle))


TAU = math.tau
