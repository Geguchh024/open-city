# SPDX-License-Identifier: GPL-3.0-or-later
"""Small DSL for building geometry node trees from Python.

Every helper accepts plain values or sockets and returns an output socket,
so graphs read like expressions:

    g = GB(tree)
    h = g.mul(g.named("oc_density"), g.value(30.0))
    mesh = g.extrude(mesh, offset_scale=h)["mesh"]
"""

import math

import bpy

SOCKET_TYPES = {
    "geometry": "NodeSocketGeometry",
    "float": "NodeSocketFloat",
    "int": "NodeSocketInt",
    "bool": "NodeSocketBool",
    "vector": "NodeSocketVector",
    "rotation": "NodeSocketRotation",
    "material": "NodeSocketMaterial",
    "collection": "NodeSocketCollection",
    "object": "NodeSocketObject",
    "string": "NodeSocketString",
    "color": "NodeSocketColor",
}


def _available(sockets):
    for s in sockets:
        if not getattr(s, "enabled", True) or getattr(s, "is_unavailable", False):
            continue
        yield s


def find_input(node, key):
    avail = list(_available(node.inputs))
    if isinstance(key, int):
        return avail[key]
    for s in avail:
        if s.name == key or s.identifier == key:
            return s
    raise KeyError(f"{node.bl_idname} has no input {key!r}: {[s.name for s in avail]}")


def find_output(node, key=0):
    avail = list(_available(node.outputs))
    if isinstance(key, int):
        return avail[key]
    for s in avail:
        if s.name == key or s.identifier == key:
            return s
    raise KeyError(f"{node.bl_idname} has no output {key!r}: {[s.name for s in avail]}")


def _is_socket(v):
    return isinstance(v, bpy.types.NodeSocket)


_FOLD = {
    "ADD": lambda a, b: a + b,
    "SUBTRACT": lambda a, b: a - b,
    "MULTIPLY": lambda a, b: a * b,
    "DIVIDE": lambda a, b: a / b if b else 0.0,
    "MULTIPLY_ADD": lambda a, b, c: a * b + c,
    "POWER": lambda a, b: a ** b,
    "MINIMUM": min,
    "MAXIMUM": max,
    "FLOOR": math.floor,
    "ABSOLUTE": abs,
    "SQRT": lambda a: math.sqrt(max(a, 0.0)),
    "SINE": math.sin,
    "COSINE": math.cos,
}


class GB:
    """Node builder bound to a geometry (or shader) node tree."""

    def __init__(self, tree):
        self.tree = tree
        self.nodes = tree.nodes
        self.links = tree.links

    # -- core -------------------------------------------------------------------
    def node(self, idname, inputs=None, **props):
        n = self.nodes.new(idname)
        for k, v in props.items():
            setattr(n, k, v)
        for k, v in (inputs or {}).items():
            self.set(n, k, v)
        return n

    def set(self, node, key, value):
        if value is None:
            return
        sock = find_input(node, key)
        if _is_socket(value):
            self.links.new(value, sock)
            return
        if sock.type == "RGBA":
            if isinstance(value, (int, float)):
                value = (value, value, value, 1.0)
            elif len(value) == 3:
                value = (*value, 1.0)
        elif sock.type == "VECTOR":
            if isinstance(value, (int, float)):
                value = (value,) * len(sock.default_value)
            elif len(value) != len(sock.default_value):
                n = len(sock.default_value)
                value = tuple(value[:n]) + (0.0,) * (n - len(value))
        elif sock.type == "ROTATION" and len(value) == 3:
            pass
        sock.default_value = value

    def out(self, idname, inputs=None, output=0, **props):
        return find_output(self.node(idname, inputs, **props), output)

    def outs(self, idname, inputs=None, **props):
        """All outputs of a node as a dict keyed by lower-case socket name."""
        n = self.node(idname, inputs, **props)
        return {s.name.lower().replace(" ", "_"): s for s in _available(n.outputs)}

    # -- scalar math ------------------------------------------------------------
    def math(self, op, a, b=None, c=None, clamp=False):
        # constant folding keeps graphs small: plain numbers in, plain number out
        if op in _FOLD and all(isinstance(v, (int, float)) for v in (a, b, c) if v is not None):
            r = _FOLD[op](*(v for v in (a, b, c) if v is not None))
            return min(max(r, 0.0), 1.0) if clamp else r
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(n, i, v)
        return n.outputs[0]

    def add(self, a, b):
        return self.math("ADD", a, b)

    def sub(self, a, b):
        return self.math("SUBTRACT", a, b)

    def mul(self, a, b):
        return self.math("MULTIPLY", a, b)

    def div(self, a, b):
        return self.math("DIVIDE", a, b)

    def madd(self, a, b, c):
        return self.math("MULTIPLY_ADD", a, b, c)

    def pow(self, a, b):
        return self.math("POWER", a, b)

    def min(self, a, b):
        return self.math("MINIMUM", a, b)

    def max(self, a, b):
        return self.math("MAXIMUM", a, b)

    def floor(self, a):
        return self.math("FLOOR", a)

    def fract(self, a):
        return self.math("FRACT", a)

    def mod(self, a, b):
        return self.math("FLOORED_MODULO", a, b)

    def abs(self, a):
        return self.math("ABSOLUTE", a)

    def sqrt(self, a):
        return self.math("SQRT", a)

    def sin(self, a):
        return self.math("SINE", a)

    def cos(self, a):
        return self.math("COSINE", a)

    def atan2(self, a, b):
        return self.math("ARCTAN2", a, b)

    def clamp01(self, a):
        return self.math("ADD", a, 0.0, clamp=True)

    def clamp(self, a, lo, hi):
        if all(isinstance(v, (int, float)) for v in (a, lo, hi)):
            return min(max(a, lo), hi)
        return self.out("ShaderNodeClamp", {"Value": a, "Min": lo, "Max": hi})

    def value(self, v):
        n = self.nodes.new("ShaderNodeValue")
        n.outputs[0].default_value = v
        return n.outputs[0]

    def lerp(self, a, b, t):
        return self.out("ShaderNodeMix", {"Factor": t, "A": a, "B": b}, data_type="FLOAT")

    def map_range(self, v, a0, a1, b0, b1, clamp=True):
        return self.out("ShaderNodeMapRange", {"Value": v, "From Min": a0, "From Max": a1,
                                                "To Min": b0, "To Max": b1}, clamp=clamp)

    # -- comparisons and logic --------------------------------------------------
    def cmp(self, op, a, b, kind="FLOAT"):
        """Comparison field: op is GREATER_THAN, LESS_THAN, GREATER_EQUAL, LESS_EQUAL, EQUAL."""
        n = self.node("FunctionNodeCompare", data_type=kind, operation=op)
        self.set(n, "A", a)
        self.set(n, "B", b)
        return n.outputs["Result"]

    def gt(self, a, b):
        return self.cmp("GREATER_THAN", a, b)

    def lt(self, a, b):
        return self.cmp("LESS_THAN", a, b)

    def ge(self, a, b):
        return self.cmp("GREATER_EQUAL", a, b)

    def le(self, a, b):
        return self.cmp("LESS_EQUAL", a, b)

    def eq(self, a, b):
        return self.cmp("EQUAL", a, b)

    def land(self, a, b):
        return self.out("FunctionNodeBooleanMath", {0: a, 1: b}, operation="AND")

    def lor(self, a, b):
        return self.out("FunctionNodeBooleanMath", {0: a, 1: b}, operation="OR")

    def lnot(self, a):
        return self.out("FunctionNodeBooleanMath", {0: a}, operation="NOT")

    def all_of(self, *xs):
        r = xs[0]
        for x in xs[1:]:
            r = self.land(r, x)
        return r

    def any_of(self, *xs):
        r = xs[0]
        for x in xs[1:]:
            r = self.lor(r, x)
        return r

    def select(self, cond, a_false, b_true, kind="FLOAT"):
        n = self.node("GeometryNodeSwitch", input_type=kind)
        self.set(n, "Switch", cond)
        self.set(n, "False", a_false)
        self.set(n, "True", b_true)
        return n.outputs["Output"]

    def tobool(self, f):
        """A float (0/1) as a boolean field."""
        return self.gt(f, 0.5)

    def tofloat(self, b):
        return self.select(b, 0.0, 1.0)

    # -- vectors ----------------------------------------------------------------
    def xyz(self, x=0.0, y=0.0, z=0.0):
        if all(isinstance(v, (int, float)) for v in (x, y, z)):
            return (float(x), float(y), float(z))
        return self.out("ShaderNodeCombineXYZ", {"X": x, "Y": y, "Z": z})

    def split(self, v):
        if isinstance(v, tuple):
            return v[0], v[1], v[2]
        n = self.node("ShaderNodeSeparateXYZ", {"Vector": v})
        return n.outputs["X"], n.outputs["Y"], n.outputs["Z"]

    def vmath(self, op, a, b=None, c=None, scale=None, output="Vector"):
        if isinstance(a, tuple) and (b is None or isinstance(b, tuple)) and c is None:
            if op == "ADD":
                return tuple(x + y for x, y in zip(a, b))
            if op == "SUBTRACT":
                return tuple(x - y for x, y in zip(a, b))
            if op == "MULTIPLY":
                return tuple(x * y for x, y in zip(a, b))
            if op == "SCALE" and isinstance(scale, (int, float)):
                return tuple(x * scale for x in a)
        n = self.node("ShaderNodeVectorMath", operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.set(n, i, v)
        if scale is not None:
            self.set(n, "Scale", scale)
        return n.outputs[output]

    def vadd(self, a, b):
        return self.vmath("ADD", a, b)

    def vsub(self, a, b):
        return self.vmath("SUBTRACT", a, b)

    def vscale(self, a, s):
        return self.vmath("SCALE", a, scale=s)

    def vmul(self, a, b):
        return self.vmath("MULTIPLY", a, b)

    def vlen(self, a):
        return self.vmath("LENGTH", a, output="Value")

    def noise(self, vec, scale=1.0, detail=2.0, roughness=0.5, w=None):
        d = {"Vector": vec, "Scale": scale, "Detail": detail, "Roughness": roughness}
        if w is not None:
            d["W"] = w
        return self.out("ShaderNodeTexNoise", d, output="Fac", noise_dimensions="3D" if w is None else "4D")

    def euler(self, x=0.0, y=0.0, z=0.0):
        return self.out("FunctionNodeEulerToRotation", {"Euler": self.xyz(x, y, z)})

    # -- randomness -------------------------------------------------------------
    def rand(self, lo=0.0, hi=1.0, seed=0, id=None, kind="FLOAT"):
        n = self.node("FunctionNodeRandomValue", data_type=kind)
        if kind == "FLOAT":
            self.set(n, "Min", lo)
            self.set(n, "Max", hi)
        elif kind == "INT":
            self.set(n, "Min", int(lo))
            self.set(n, "Max", int(hi))
        else:
            self.set(n, "Probability", lo)
        self.set(n, "Seed", seed)
        if id is not None:
            self.set(n, "ID", id)
        return n.outputs["Value"]

    # -- fields and attributes --------------------------------------------------
    def position(self):
        return self.out("GeometryNodeInputPosition")

    def index(self):
        return self.out("GeometryNodeInputIndex")

    def normal(self):
        return self.out("GeometryNodeInputNormal")

    def named(self, name, kind="FLOAT"):
        return self.out("GeometryNodeInputNamedAttribute", {"Name": name}, output="Attribute", data_type=kind)

    def store(self, geo, name, value, domain="FACE", kind="FLOAT", selection=None):
        return self.out("GeometryNodeStoreNamedAttribute",
                        {"Geometry": geo, "Name": name, "Value": value, "Selection": selection},
                        data_type=kind, domain=domain)

    def store_many(self, geo, items, domain="FACE"):
        for name, value in items:
            geo = self.store(geo, name, value, domain)
        return geo

    # -- geometry ---------------------------------------------------------------
    def join(self, *geos):
        n = self.node("GeometryNodeJoinGeometry")
        for g in geos:
            if g is not None:
                self.links.new(g, n.inputs[0])
        return n.outputs[0]

    def separate(self, geo, selection, domain="FACE"):
        n = self.node("GeometryNodeSeparateGeometry", {"Geometry": geo, "Selection": selection}, domain=domain)
        return n.outputs["Selection"], n.outputs["Inverted"]

    def delete(self, geo, selection, domain="FACE"):
        return self.out("GeometryNodeDeleteGeometry", {"Geometry": geo, "Selection": selection}, domain=domain)

    def set_pos(self, geo, position=None, offset=None, selection=None):
        return self.out("GeometryNodeSetPosition", {"Geometry": geo, "Position": position,
                                                     "Offset": offset, "Selection": selection})

    def material(self, geo, mat, selection=None):
        return self.out("GeometryNodeSetMaterial", {"Geometry": geo, "Material": mat, "Selection": selection})

    def extrude(self, mesh, offset_scale=None, selection=None, individual=True, offset=None, mode="FACES"):
        o = self.outs("GeometryNodeExtrudeMesh", {"Mesh": mesh, "Selection": selection,
                                                   "Offset Scale": offset_scale, "Offset": offset,
                                                   "Individual": individual}, mode=mode)
        return o["mesh"], o["top"], o["side"]

    def scale_el(self, geo, scale, selection=None, domain="FACE"):
        return self.out("GeometryNodeScaleElements", {"Geometry": geo, "Selection": selection, "Scale": scale},
                        domain=domain)

    def transform(self, geo, translation=None, rotation=None, scale=None):
        return self.out("GeometryNodeTransform", {"Geometry": geo, "Translation": translation,
                                                   "Rotation": rotation, "Scale": scale})

    def mesh_to_points(self, mesh, selection=None, mode="FACES", position=None):
        return self.out("GeometryNodeMeshToPoints", {"Mesh": mesh, "Selection": selection, "Position": position},
                        mode=mode)

    def instance(self, points, geo, rotation=None, scale=None, selection=None, pick=False, index=None):
        return self.out("GeometryNodeInstanceOnPoints",
                        {"Points": points, "Selection": selection, "Instance": geo, "Pick Instance": pick,
                         "Instance Index": index, "Rotation": rotation, "Scale": scale})

    def realize(self, geo):
        return self.out("GeometryNodeRealizeInstances", {"Geometry": geo})

    def smooth(self, geo, on):
        return self.out("GeometryNodeSetShadeSmooth", {"Geometry": geo, "Shade Smooth": on}, domain="FACE")

    def box(self, size, at=None):
        """A cube mesh of the given (x, y, z) size, optionally moved to `at`."""
        m = self.out("GeometryNodeMeshCube", {"Size": size})
        if at is not None:
            m = self.transform(m, translation=at)
        return m

    def cyl(self, radius, depth, verts=12, at=None, rot=None):
        """A cylinder standing on the XY plane at `at` (its base, not its middle)."""
        m = self.out("GeometryNodeMeshCylinder", {"Vertices": verts, "Radius": radius, "Depth": depth},
                     output="Mesh")
        m = self.transform(m, translation=self.vadd(self.xyz(0.0, 0.0, self.mul(depth, 0.5)), at or (0, 0, 0)))
        if rot is not None:
            m = self.transform(m, rotation=rot)
        return m

    def points(self, count, position=None):
        return self.out("GeometryNodePoints", {"Count": count, "Position": position})

    def hull(self, geo):
        return self.out("GeometryNodeConvexHull", {"Geometry": geo})

    def library(self, geos):
        """Geometry to Instance: one instance per geometry, in order, for Pick Instance."""
        n = self.node("GeometryNodeGeometryToInstance")
        # a multi-input socket lists its newest link first, so link in reverse to keep the order
        for geo in reversed(geos):
            self.links.new(geo, n.inputs[0])
        return n.outputs[0]

    def switch_geo(self, cond, if_true, if_false=None):
        return self.out("GeometryNodeSwitch", {"Switch": cond, "True": if_true, "False": if_false},
                        input_type="GEOMETRY")

    def store_color(self, geo, name, value, domain="POINT"):
        return self.store(geo, name, value, domain=domain, kind="FLOAT_COLOR")

    def store_vec(self, geo, name, value, domain="POINT"):
        return self.store(geo, name, value, domain=domain, kind="FLOAT_VECTOR")

    def group(self, tree, **inputs):
        """Instance a node group, wiring inputs by name. Returns the node."""
        n = self.nodes.new("GeometryNodeGroup")
        n.node_tree = tree
        for k, v in inputs.items():
            self.set(n, k.replace("_", " "), v)
        return n

    def gout(self, node, key=0):
        return find_output(node, key.replace("_", " ") if isinstance(key, str) else key)


# -- group interface ----------------------------------------------------------------
class Group:
    """A node group under construction: interface, input and output nodes."""

    def __init__(self, name, inputs, outputs, tree_type="GeometryNodeTree"):
        old = bpy.data.node_groups.get(name)
        if old is not None:
            bpy.data.node_groups.remove(old)
        self.tree = bpy.data.node_groups.new(name, tree_type)
        self.g = GB(self.tree)
        self.ids = {}
        panels = {}
        iface = self.tree.interface
        for spec in inputs:
            self._socket(iface, panels, spec, "INPUT")
        for spec in outputs:
            self._socket(iface, panels, spec, "OUTPUT")
        self.gin = self.g.node("NodeGroupInput")
        self.gout = self.g.node("NodeGroupOutput")

    def _socket(self, iface, panels, spec, in_out):
        name, kind = spec[0], spec[1]
        opts = spec[2] if len(spec) > 2 else {}
        parent = None
        pname = opts.get("panel")
        if pname:
            if pname not in panels:
                panels[pname] = iface.new_panel(pname, default_closed=opts.get("closed", False))
            parent = panels[pname]
        s = iface.new_socket(name=name, in_out=in_out, socket_type=SOCKET_TYPES[kind], parent=parent)
        if in_out == "INPUT":
            self.ids[name] = s.identifier
        if "default" in opts and hasattr(s, "default_value"):
            s.default_value = opts["default"]
        if "min" in opts:
            s.min_value = opts["min"]
        if "max" in opts:
            s.max_value = opts["max"]
        if "subtype" in opts:
            s.subtype = opts["subtype"]
        if "tip" in opts:
            s.description = opts["tip"]
        if opts.get("hide_value"):
            s.hide_value = True
        if opts.get("single_value"):
            s.default_input = "VALUE"

    def i(self, name):
        """Group input socket by name."""
        return self.gin.outputs[name]

    def finish(self, **outs):
        for k, v in outs.items():
            self.g.links.new(v, self.gout.inputs[k.replace("_", " ")])
        return self.tree


def layout_tree(tree, xstep=240, ystep=190):
    """Rough left-to-right auto layout by link depth so graphs stay readable."""
    depth = {}

    def d(n, seen=()):
        if n in depth:
            return depth[n]
        if n in seen:
            return 0
        best = 0
        for s in n.inputs:
            for link in s.links:
                best = max(best, d(link.from_node, seen + (n,)) + 1)
        depth[n] = best
        return best

    cols = {}
    for n in tree.nodes:
        cols.setdefault(d(n), []).append(n)
    for c, ns in cols.items():
        for r, n in enumerate(ns):
            n.location = (c * xstep, -r * ystep)
