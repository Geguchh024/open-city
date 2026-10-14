# SPDX-License-Identifier: GPL-3.0-or-later
"""Material and colour variation: the stylized materials the kit assigns.

All procedural, nothing to pack. A handful of shared materials serve every building: each building
stores its palette on its geometry (`oc_wall`, `oc_trim`, `oc_accent`, `oc_roof`, `oc_awning`) and the
shaders read it, so a town of differently coloured houses still uses one wall material. Props read
`oc_tint` from their instancer for per-instance variation (car paint, leaves, flowers). Windows, lamps, signs
and tail lights also read the town's night switch (`lights.NIGHT`) and light up after dark.
"""

import bpy

from . import lights
from .gn import GB
from .styles import hexlin

# name -> viewport colour for Solid shading
SOLID = {}


def _new(name, solid=(0.6, 0.6, 0.6)):
    """A fresh node tree for the material; an existing material is rebuilt in place to keep its users."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    if not mat.use_nodes:
        mat.use_nodes = True
    mat.node_tree.nodes.clear()
    mat.diffuse_color = (*solid[:3], 1.0)
    SOLID[name] = solid
    return mat


def _out(g, shader):
    o = g.node("ShaderNodeOutputMaterial")
    g.links.new(shader, o.inputs["Surface"])


def _bsdf(g, color, rough=0.7, metal=0.0, emit=None, strength=0.0, spec=0.5, coat=0.0):
    n = g.node("ShaderNodeBsdfPrincipled", {"Base Color": color, "Roughness": rough, "Metallic": metal,
                                            "Specular IOR Level": spec})
    if emit is not None:
        g.set(n, "Emission Color", emit)
        g.set(n, "Emission Strength", strength)
    if coat:
        g.set(n, "Coat Weight", coat)
    _out(g, n.outputs["BSDF"])
    return n


def _attr(g, name, kind="GEOMETRY", output="Color"):
    return g.out("ShaderNodeAttribute", output=output, attribute_name=name, attribute_type=kind)


def _attr_any(g, name, output="Color"):
    """An attribute from the geometry itself or, for instances, from the instancer (whichever is set)."""
    if output == "Color":
        return _mix(g, 0.5, _attr(g, name, "GEOMETRY"), _attr(g, name, "INSTANCER"), "ADD")
    return g.add(_attr(g, name, "GEOMETRY", "Fac"), _attr(g, name, "INSTANCER", "Fac"))


def _mix(g, fac, a, b, blend="MIX"):
    if blend == "ADD":
        return g.out("ShaderNodeMix", {"Factor": 1.0, "A": a, "B": b}, output="Result", data_type="RGBA",
                     blend_type="ADD")
    return g.out("ShaderNodeMix", {"Factor": fac, "A": a, "B": b}, output="Result", data_type="RGBA",
                 blend_type=blend)


def _scale(g, color, f):
    b = (f, f, f, 1.0) if isinstance(f, (int, float)) else f   # a float socket converts to grey
    return g.out("ShaderNodeMix", {"Factor": 1.0, "A": color, "B": b}, output="Result",
                 data_type="RGBA", blend_type="MULTIPLY")


def _ramp(g, fac, colors, constant=True):
    n = g.node("ShaderNodeValToRGB", {"Fac": fac})
    n.color_ramp.interpolation = "CONSTANT" if constant else "LINEAR"
    els = n.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for i, c in enumerate(colors):
        els[i].position = i / len(colors) if constant else i / max(len(colors) - 1, 1)
        els[i].color = (*c[:3], 1.0)
    return n.outputs["Color"]


def _night(g):
    """0 by day, 1 by night: the town-wide switch."""
    n = g.node("ShaderNodeGroup")
    n.node_tree = lights.night_group()
    return n.outputs[0]


def _geo(g):
    n = g.node("ShaderNodeNewGeometry")
    return n.outputs["Position"], n.outputs["Normal"]


def _wall_uv(g):
    """(u, z) on a vertical surface: u runs along the wall, whatever way it faces."""
    pos, nrm = _geo(g)
    nx, ny, _nz = g.split(nrm)
    tang = g.vmath("NORMALIZE", g.xyz(g.mul(ny, -1.0), nx, 0.0))
    u = g.vmath("DOT_PRODUCT", pos, tang, output="Value")
    _px, _py, pz = g.split(pos)
    return u, pz, pos


def _noise(g, vec, scale, detail=2.0):
    return g.out("ShaderNodeTexNoise", {"Vector": vec, "Scale": scale, "Detail": detail}, output="Fac")


def _vary(g, color, pos, amount=0.08, scale=1.2):
    """Gentle large-scale tone variation so flat colours do not look printed."""
    n = _noise(g, pos, scale, 3.0)
    return _scale(g, color, g.map_range(n, 0.3, 0.7, 1.0 - amount, 1.0 + amount * 0.5))


def _ao(g, color, amount=0.55, distance=0.5):
    n = g.node("ShaderNodeAmbientOcclusion", {"Color": color, "Distance": distance})
    n.samples = 8
    return _mix(g, amount, color, n.outputs["Color"])


def _brick(g, vec, c1, c2, mortar, width, height, mortar_size=0.012, offset=0.5):
    n = g.node("ShaderNodeTexBrick", {"Vector": vec, "Color1": c1, "Color2": c2, "Mortar": mortar, "Scale": 1.0,
                                       "Mortar Size": mortar_size, "Mortar Smooth": 0.2, "Bias": 0.0,
                                       "Brick Width": width, "Row Height": height}, offset=offset)
    return n.outputs["Color"], n.outputs["Fac"]


# -- building materials ----------------------------------------------------------------------------
def _wall():
    mat = _new("OC Wall", (0.6, 0.25, 0.18))
    g = GB(mat.node_tree)
    col = _attr(g, "oc_wall")
    kind = _attr(g, "oc_wallkind", output="Fac")
    u, z, pos = _wall_uv(g)
    uvz = g.xyz(u, z, 0.0)
    plaster = _vary(g, col, pos, 0.07, 0.9)
    # brick: stylized, the courses show in soft patches rather than as a print
    bc, _bf = _brick(g, uvz, col, _scale(g, col, 0.84), _scale(g, col, 1.28), 0.46, 0.165, 0.014)
    patch = g.map_range(_noise(g, g.vscale(pos, 0.55), 1.0, 2.0), 0.38, 0.62, 0.25, 1.0)
    brick = _mix(g, patch, plaster, bc)
    # dressed stone: big ashlar blocks with thin dark joints
    sc, _sf = _brick(g, uvz, col, _scale(g, col, 0.9), _scale(g, col, 0.72), 1.15, 0.44, 0.012)
    stone = _vary(g, sc, pos, 0.05, 2.0)
    # painted clapboard siding: one soft shadow line per board
    board = g.fract(g.div(z, 0.24))
    siding = _scale(g, plaster, g.map_range(board, 0.0, 0.18, 0.8, 1.0))
    c = _mix(g, g.math("GREATER_THAN", kind, 0.5), plaster, brick)
    c = _mix(g, g.math("GREATER_THAN", kind, 1.5), c, stone)
    c = _mix(g, g.math("GREATER_THAN", kind, 2.5), c, siding)
    # a little grime where the walls meet the street
    c = _scale(g, c, g.map_range(z, 0.0, 1.4, 0.82, 1.0))
    _bsdf(g, _ao(g, c), rough=0.82, spec=0.35)
    return mat


def _flat_attr(name, attr, solid, rough=0.6, vary=0.05, ao=0.5):
    mat = _new(name, solid)
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    c = _vary(g, _attr(g, attr), pos, vary, 2.5)
    _bsdf(g, _ao(g, c, ao), rough=rough)
    return mat


def _shutter():
    mat = _new("OC Shutter", (0.15, 0.35, 0.25))
    g = GB(mat.node_tree)
    _u, z, pos = _wall_uv(g)
    louver = g.map_range(g.fract(g.div(z, 0.075)), 0.0, 0.35, 0.62, 1.0)
    c = _scale(g, _attr(g, "oc_accent"), louver)
    _bsdf(g, _ao(g, c), rough=0.55)
    return mat


def _awning():
    mat = _new("OC Awning", (0.9, 0.75, 0.3))
    g = GB(mat.node_tree)
    col = _attr(g, "oc_awning")
    u = _attr(g, "oc_u", output="Fac")
    stripes = _attr(g, "oc_stripes", output="Fac")
    band = g.math("LESS_THAN", g.fract(g.div(u, 0.42)), 0.5)
    on = g.mul(band, stripes)
    c = _mix(g, on, col, (0.93, 0.88, 0.78, 1.0))
    _bsdf(g, _ao(g, c, 0.4), rough=0.75, spec=0.3)
    return mat


def _glass():
    mat = _new("OC Glass", (0.3, 0.55, 0.75))
    g = GB(mat.node_tree)
    gu = _attr(g, "oc_gu", output="Fac")
    gv = _attr(g, "oc_gv", output="Fac")
    slot = _attr(g, "oc_slot", output="Fac")
    shop = _attr(g, "oc_shop", output="Fac")
    deep, light = hexlin("#3E7FAE"), hexlin("#9FD3E8")
    base = _mix(g, g.map_range(gv, 0.0, 1.0, 0.0, 0.85), (*deep, 1), (*light, 1))
    # the stylized diagonal glint of the references
    d = g.fract(g.add(g.mul(gu, 1.1), g.mul(gv, 0.9)))
    glint = g.mul(g.math("GREATER_THAN", d, 0.62), g.math("LESS_THAN", d, 0.74))
    glint = g.add(glint, g.mul(g.math("GREATER_THAN", d, 0.8), g.math("LESS_THAN", d, 0.84)))
    base = _mix(g, g.mul(glint, 0.45), base, (0.95, 0.98, 1.0, 1.0))
    # blinds and curtains drawn to a different height in every window
    blind = g.mul(g.map_range(slot, 0.0, 1.0, -0.25, 0.62), g.sub(1.0, shop))
    drawn = g.math("GREATER_THAN", gv, g.sub(1.0, blind))
    tones = [hexlin(h) for h in ("#F2D98A", "#F4E9C9", "#E9B9A8", "#D9E3B5", "#F2D98A", "#EED7A3")]
    curtain = _ramp(g, g.fract(g.mul(slot, 7.31)), tones)
    curtain = _scale(g, curtain, g.map_range(g.fract(g.mul(gu, 6.0)), 0.0, 1.0, 0.92, 1.0))
    c = _mix(g, drawn, base, curtain)
    # shop windows look into a warm, darker interior
    interior = _mix(g, g.map_range(gv, 0.0, 1.0, 0.0, 1.0), (*hexlin("#3A3A44"), 1), (*hexlin("#6F8FA5"), 1))
    interior = _mix(g, g.mul(glint, 0.4), interior, (0.9, 0.95, 1.0, 1.0))
    c = _mix(g, shop, c, interior)
    # after dark: most windows are lit, warm behind the curtains; shop windows are lit bright; the rest
    # go dark instead of reflecting a daylight sky
    night = _night(g)
    lit = g.math("MAXIMUM", g.math("LESS_THAN", g.fract(g.mul(slot, 13.37)), 0.62), shop)
    glow = _mix(g, shop, _mix(g, 0.55, curtain, (*hexlin("#FFB35C"), 1)), (*hexlin("#FFE0A6"), 1))
    glow = _scale(g, glow, g.map_range(gv, 0.0, 1.0, 1.0, 0.7))
    c = _mix(g, g.mul(night, 0.85), c, _scale(g, c, 0.12))
    strength = g.mul(g.mul(night, lit), g.lerp(2.6, 6.0, shop))
    _bsdf(g, c, rough=g.lerp(0.08, 0.6, drawn), spec=0.9, coat=0.0, emit=glow, strength=strength)
    return mat


def _roof_tiles():
    mat = _new("OC Roof Tiles", (0.55, 0.25, 0.15))
    g = GB(mat.node_tree)
    col = _attr(g, "oc_roof")
    u, z, pos = _wall_uv(g)
    # courses follow the slope; nearly flat tops fall back to plan coordinates
    _gp, nrm = _geo(g)
    _nx, _ny, nz = g.split(nrm)
    px, py, _pz = g.split(pos)
    flat = g.math("GREATER_THAN", nz, 0.85)
    tu = g.lerp(u, px, flat)
    tv = g.lerp(g.mul(z, 1.6), py, flat)
    tc, _tf = _brick(g, g.xyz(tu, tv, 0.0), col, _scale(g, col, 0.82), _scale(g, col, 0.55),
                     0.34, 0.2, 0.018)
    c = _vary(g, tc, pos, 0.1, 0.8)
    _bsdf(g, _ao(g, c, 0.5), rough=0.72)
    return mat


def _roof_flat():
    mat = _new("OC Roof Flat", (0.2, 0.2, 0.22))
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    base = (*hexlin("#4B4F57"), 1.0)
    c = _vary(g, base, pos, 0.12, 4.0)
    gravel = g.out("ShaderNodeTexNoise", {"Vector": pos, "Scale": 60.0, "Detail": 1.0}, output="Fac")
    c = _scale(g, c, g.map_range(gravel, 0.3, 0.7, 0.9, 1.08))
    _bsdf(g, _ao(g, c, 0.6), rough=0.92)
    return mat


def _stone():
    mat = _new("OC Stone", (0.55, 0.52, 0.47))
    g = GB(mat.node_tree)
    u, z, pos = _wall_uv(g)
    trim = _attr(g, "oc_trim")
    base = _mix(g, 0.45, (*hexlin("#A8A296"), 1.0), trim)
    c, _f = _brick(g, g.xyz(u, z, 0.0), base, _scale(g, base, 0.88), _scale(g, base, 0.62), 0.78, 0.3, 0.016)
    _bsdf(g, _ao(g, _vary(g, c, pos, 0.06, 3.0)), rough=0.88)
    return mat


def _chimney_brick():
    mat = _new("OC Brick", (0.5, 0.2, 0.14))
    g = GB(mat.node_tree)
    u, z, pos = _wall_uv(g)
    base = (*hexlin("#9C4A35"), 1.0)
    c, _f = _brick(g, g.xyz(u, z, 0.0), base, _scale(g, base, 0.82), (*hexlin("#C9B9A2"), 1.0), 0.3, 0.11, 0.015)
    _bsdf(g, _ao(g, c), rough=0.85)
    return mat


def _sign_text():
    """Gilded letters on a dark fascia, dark letters on a light one."""
    mat = _new("OC Sign Text", (0.95, 0.85, 0.5))
    g = GB(mat.node_tree)
    lum = g.out("ShaderNodeRGBToBW", {"Color": _attr(g, "oc_accent")})
    light = g.math("GREATER_THAN", lum, 0.3)
    c = _mix(g, light, (*hexlin("#F6E3A6"), 1.0), (*hexlin("#2A2C33"), 1.0))
    # gilded letters are lit at night
    _bsdf(g, c, rough=0.35, metal=g.mul(g.sub(1.0, light), 0.35), emit=(*hexlin("#FFF1C8"), 1.0),
          strength=g.mul(g.sub(1.0, light), g.madd(_night(g), 3.0, 0.15)))
    return mat


def _tinted(name, palette, solid, rough=0.7, attr="oc_tint", ao=0.4):
    """Per-instance colour picked from a palette by `oc_tint` (from the instancer or the geometry)."""
    mat = _new(name, solid)
    g = GB(mat.node_tree)
    t = _attr_any(g, attr, "Fac")
    pos, _n = _geo(g)
    c = _ramp(g, g.fract(t), [hexlin(h) for h in palette])
    c = _vary(g, c, pos, 0.06, 1.5)
    _bsdf(g, _ao(g, c, ao), rough=rough)
    return mat


def _leaves():
    mat = _new("OC Leaves", (0.25, 0.5, 0.18))
    g = GB(mat.node_tree)
    t = g.add(_attr_any(g, "oc_tint", "Fac"), _attr(g, "oc_slot", output="Fac"))
    pos, nrm = _geo(g)
    pal = [hexlin(h) for h in ("#5FA83A", "#4E9A35", "#78B843", "#3F8A3A", "#8DBF4A", "#5A9E44")]
    c = _ramp(g, g.fract(t), pal)
    _nx, _ny, nz = g.split(nrm)
    # light from above: the tops of the clumps catch the sun
    c = _scale(g, c, g.map_range(nz, -1.0, 1.0, 0.7, 1.15))
    c = _vary(g, c, pos, 0.1, 2.5)
    _bsdf(g, _ao(g, c, 0.6, 0.8), rough=0.8, spec=0.3)
    return mat


def _simple(name, hexcol, rough=0.7, metal=0.0, noise=0.05, ao=0.4, emit=None, strength=0.0, coat=0.0):
    col = hexlin(hexcol)
    mat = _new(name, col)
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    c = (*col, 1.0)
    if noise:
        c = _vary(g, c, pos, noise, 2.0)
    if ao:
        c = _ao(g, c, ao)
    _bsdf(g, c, rough=rough, metal=metal, emit=(*hexlin(emit), 1.0) if emit else None, strength=strength,
          coat=coat)
    return mat


# -- the street ---------------------------------------------------------------------------------------
def _asphalt():
    mat = _new("OC Asphalt", (0.17, 0.17, 0.18))
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    base = (*hexlin("#5A5C62"), 1.0)
    c = _vary(g, base, pos, 0.08, 0.4)
    grain = _noise(g, pos, 90.0, 1.0)
    c = _scale(g, c, g.map_range(grain, 0.3, 0.7, 0.92, 1.06))
    patches = _noise(g, pos, 0.15, 2.0)
    c = _scale(g, c, g.map_range(patches, 0.45, 0.6, 1.0, 0.93))
    _bsdf(g, _ao(g, c, 0.5, 0.6), rough=0.9, spec=0.3)
    return mat


def _paving(name, hexcol, tile, joint=0.02, offset=0.0, solid=None):
    col = hexlin(hexcol)
    mat = _new(name, solid or col)
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    px, py, _pz = g.split(pos)
    c, _f = _brick(g, g.xyz(px, py, 0.0), (*col, 1.0), _scale(g, (*col, 1.0), 0.93),
                   _scale(g, (*col, 1.0), 0.78), tile[0], tile[1], joint, offset)
    c = _vary(g, c, pos, 0.06, 0.6)
    _bsdf(g, _ao(g, c, 0.55, 0.6), rough=0.88, spec=0.3)
    return mat


def _grass():
    mat = _new("OC Grass", (0.3, 0.55, 0.2))
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    a, b = hexlin("#6DB33F"), hexlin("#4F9A35")
    n = _noise(g, pos, 0.5, 3.0)
    c = _mix(g, g.map_range(n, 0.35, 0.65, 0.0, 1.0), (*a, 1.0), (*b, 1.0))
    fine = _noise(g, pos, 25.0, 1.0)
    c = _scale(g, c, g.map_range(fine, 0.3, 0.7, 0.93, 1.06))
    _bsdf(g, _ao(g, c, 0.55, 0.8), rough=0.9, spec=0.25)
    return mat


def _water():
    mat = _new("OC Water", (0.3, 0.6, 0.85))
    g = GB(mat.node_tree)
    pos, _n = _geo(g)
    n = _noise(g, pos, 3.0, 2.0)
    c = _mix(g, g.map_range(n, 0.4, 0.6, 0.0, 1.0), (*hexlin("#4FA9D6"), 1.0), (*hexlin("#8FD3EE"), 1.0))
    _bsdf(g, c, rough=0.05, spec=0.8)
    return mat


def _lamp_glow():
    mat = _new("OC Lamp Glow", (1.0, 0.9, 0.6))
    g = GB(mat.node_tree)
    _bsdf(g, (*hexlin("#FFF4D6"), 1.0), rough=0.2, emit=(*hexlin("#FFD891"), 1.0),
          strength=g.madd(_night(g), 22.0, 1.5))
    return mat


def _rear_light():
    mat = _new("OC Rear Light", hexlin("#C8302B"))
    g = GB(mat.node_tree)
    _bsdf(g, (*hexlin("#C8302B"), 1.0), rough=0.3, emit=(*hexlin("#FF2A1A"), 1.0), strength=g.mul(_night(g), 8.0))
    return mat


CAR_PALETTE = ("#D9473B", "#3D74C4", "#F2F0EA", "#F2C94C", "#4FA36B", "#A9B4BF", "#2F3E59", "#E58A3A",
               "#6FB7D9", "#8C3B4A")
FLOWERS = ("#E8546A", "#F2C94C", "#F28DB2", "#FFFFFF", "#E8743B", "#B98AE0")

BUILDERS = {
    "OC Wall": _wall,
    "OC Trim": lambda: _flat_attr("OC Trim", "oc_trim", (0.9, 0.85, 0.75), rough=0.62),
    "OC Accent": lambda: _flat_attr("OC Accent", "oc_accent", (0.15, 0.3, 0.25), rough=0.5),
    "OC Shutter": _shutter,
    "OC Awning": _awning,
    "OC Glass": _glass,
    "OC Roof Tiles": _roof_tiles,
    "OC Roof Flat": _roof_flat,
    "OC Stone": _stone,
    "OC Brick": _chimney_brick,
    "OC Sign Text": _sign_text,
    "OC Metal": lambda: _simple("OC Metal", "#2E3236", 0.45, 0.6, noise=0.0),
    "OC Iron": lambda: _simple("OC Iron", "#23302A", 0.5, 0.4, noise=0.0),
    "OC Wood": lambda: _simple("OC Wood", "#8A5A34", 0.75, noise=0.08),
    "OC Concrete": lambda: _simple("OC Concrete", "#B9B4AA", 0.85),
    "OC Soil": lambda: _simple("OC Soil", "#6B4A32", 0.95, noise=0.12),
    "OC Leaves": _leaves,
    "OC Trunk": lambda: _simple("OC Trunk", "#7A5236", 0.9, noise=0.1),
    "OC Flowers": lambda: _tinted("OC Flowers", FLOWERS, (0.9, 0.4, 0.5), rough=0.6, attr="oc_slot"),
    "OC Lamp Glow": _lamp_glow,
    "OC Asphalt": _asphalt,
    "OC Sidewalk": lambda: _paving("OC Sidewalk", "#C9C2B4", (0.6, 0.6), 0.025, 0.0),
    "OC Paving": lambda: _paving("OC Paving", "#D8C7A6", (0.42, 0.21), 0.03, 0.5),
    "OC Curb": lambda: _simple("OC Curb", "#DCD6CA", 0.8, noise=0.04),
    "OC Grass": _grass,
    "OC Marking": lambda: _simple("OC Marking", "#F4F1E8", 0.6, noise=0.04, ao=0.0),
    "OC Marking Yellow": lambda: _simple("OC Marking Yellow", "#F0C24B", 0.6, noise=0.04, ao=0.0),
    "OC Water": _water,
    "OC Base": lambda: _simple("OC Base", "#7B6A58", 0.9, noise=0.05, ao=0.0),
    "OC Car Paint": lambda: _tinted("OC Car Paint", CAR_PALETTE, (0.7, 0.2, 0.2), rough=0.28),
    "OC Car Glass": lambda: _simple("OC Car Glass", "#2B3A4A", 0.12, noise=0.0, ao=0.0),
    "OC Tyre": lambda: _simple("OC Tyre", "#1E1F22", 0.8, noise=0.0, ao=0.3),
    "OC Chrome": lambda: _simple("OC Chrome", "#D9DDE2", 0.25, 0.8, noise=0.0, ao=0.0),
    "OC Rear Light": _rear_light,
    "OC Prop Green": lambda: _simple("OC Prop Green", "#2F5A45", 0.5, 0.3, noise=0.0),
    "OC Prop Red": lambda: _simple("OC Prop Red", "#C93A2E", 0.45, noise=0.0),
    "OC Prop Blue": lambda: _simple("OC Prop Blue", "#2F66B3", 0.45, noise=0.0),
    "OC Prop Yellow": lambda: _simple("OC Prop Yellow", "#F2C230", 0.5, noise=0.0),
    "OC Prop White": lambda: _simple("OC Prop White", "#F4F2EC", 0.5, noise=0.0),
    "OC Fabric": lambda: _tinted("OC Fabric", ("#E35D4F", "#F2F0E6", "#3E8E5C", "#F2C94C", "#3D6FA8"),
                                 (0.9, 0.4, 0.3), rough=0.8),
}

NAMES = tuple(BUILDERS)


def get(name):
    """The material, built on first use."""
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = BUILDERS[name]()
    return mat


def ensure_all():
    for name in NAMES:
        get(name)


def rebuild_all():
    for name in NAMES:
        BUILDERS[name]()
