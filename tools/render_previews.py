# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the README images into docs/images.

    blender -b --factory-startup --python tools/render_previews.py

hero.png      the Main Street preset from the air
street.png    standing on the main street
corner.png    a street corner close up: storefronts, signs, crossings, street furniture
modular.png   one building kit at different sizes, and the roof and tower variants
presets.png   every preset in one sheet
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

import open_city  # noqa: E402
from open_city import layout, params, stage, styles, town  # noqa: E402

open_city.register()
OUT = os.path.join(ROOT, "docs", "images")
os.makedirs(OUT, exist_ok=True)


def new_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if not hasattr(bpy.types.Object, "open_city_town"):
        open_city.register()
    stage.setup(bpy.context.scene)
    bpy.context.scene.render.film_transparent = False


def make_town(preset, seed, **overrides):
    values = params.preset_values(preset)
    values["Seed"] = seed
    values.update(overrides)
    root = town.new_town(bpy.context, values, preset)
    return root, layout.plan_town(town.settings_of(root))


def camera(loc, target, lens=35, ortho=None):
    sc = bpy.context.scene
    cam = sc.camera
    if cam is None:
        cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        sc.collection.objects.link(cam)
        sc.camera = cam
    cam.data.clip_end = 3000
    cam.data.lens = lens
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def render(path, res=(1600, 900)):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = path
    sc.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("wrote", path)
    return path


def aerial(plan, scale=1.0):
    X0, X1, Y0, Y1 = plan.extent
    cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
    r = max(X1 - X0, Y1 - Y0) / 2 * scale
    camera((cx - r * 0.95, cy - r * 1.25, r * 1.05), (cx, cy - r * 0.05, 0.0))


def load(path):
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def save(px, path):
    h, w = px.shape[:2]
    img = bpy.data.images.new("out", w, h)
    img.pixels.foreach_set(np.ascontiguousarray(px).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def sheet(paths, cols, path, gap=8):
    tiles = [load(p) for p in paths]
    h, w = tiles[0].shape[:2]
    rows = math.ceil(len(tiles) / cols)
    out = np.full((rows * h + (rows + 1) * gap, cols * w + (cols + 1) * gap, 4), 0.96, np.float32)
    out[..., 3] = 1.0
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        y = out.shape[0] - gap - (r + 1) * h - r * gap
        x = gap + c * (w + gap)
        out[y:y + h, x:x + w] = t
    save(out, path)
    print("wrote", path)


def building(values, x):
    """One standalone building at (x, 0) with a strip of sidewalk under it."""
    from open_city import groups, inputs
    groups.ensure()
    ob = town.make_building_object(bpy.context.scene.collection, "B", {k: v for k, v in values.items()
                                                                       if k in params.BY_NAME})
    ob.location = (x, 0.0, 0.0)
    return ob, inputs.building_modifier(ob)


def pad(x0, x1):
    from open_city import materials
    me = bpy.data.meshes.new("pad")
    me.from_pydata([(x0, -8, 0), (x1, -8, 0), (x1, 30, 0), (x0, 30, 0)], [], [(0, 1, 2, 3)])
    me.materials.append(materials.get("OC Sidewalk"))
    ob = bpy.data.objects.new("pad", me)
    bpy.context.scene.collection.objects.link(ob)


def modular_sheet(tmp):
    """Top row: the same red-brick kit at four sizes. Bottom row: roofs and towers."""
    base = dict(params.building_defaults())
    brick = styles.BRICK_SCHEMES[0]
    base.update({"Wall Kind": 1, "Ground Kind": 1, "Wall Color": styles.rgba(brick[1]),
                 "Ground Color": styles.rgba(brick[1]), "Trim Color": styles.rgba(brick[2]),
                 "Accent Color": styles.rgba("#2F5D46"), "Ground Use": 1, "Shop Name": "BAKERY",
                 "Awnings": 1, "Awning Color": styles.rgba("#F2C94C"), "Roof Type": 0, "Detail": 1.0,
                 "Balconies": 0.0, "Flower Boxes": 0.3, "Corner Style": 0, "Plinth Height": 0.15,
                 "Ground Height": 4.0, "Entrance Bay": -1, "Seed": 5, "Bay Width": 3.0, "Window Style": 0})
    sizes = [(2, 2, 2), (3, 3, 3), (4, 3, 4), (6, 4, 5)]
    variants = [
        {"Roof Type": 2, "Ground Use": 0, "Wall Kind": 0, "Wall Color": styles.rgba("#5F8CC2"),
         "Ground Color": styles.rgba("#5F8CC2"), "Trim Color": styles.rgba("#F6F2EA"), "Shutters": True,
         "Accent Color": styles.rgba("#7A2E2E"), "Plinth Height": 0.5, "Roof Color": styles.rgba("#B9583D")},
        {"Roof Type": 3, "Ground Use": 0, "Wall Kind": 3, "Wall Color": styles.rgba("#F3E2A9"),
         "Ground Color": styles.rgba("#F3E2A9"), "Trim Color": styles.rgba("#F6F2EA"), "Shutters": True,
         "Accent Color": styles.rgba("#2E7C7A"), "Plinth Height": 0.45, "Roof Color": styles.rgba("#555C6A"),
         "Floors": 2, "Bays Wide": 3},
        {"Roof Type": 4, "Wall Kind": 0, "Wall Color": styles.rgba("#D24B3E"),
         "Ground Color": styles.rgba("#F0C24B"), "Trim Color": styles.rgba("#F6F2EA"), "Balconies": 0.7,
         "Balcony Style": 1, "Shop Name": "RESTAURANT", "Awnings": 2, "Awning Color": styles.rgba("#7A2E2E"),
         "Accent Color": styles.rgba("#2E4A6B"), "Roof Color": styles.rgba("#454C59")},
        {"Roof Type": 0, "Tower": 2, "Wall Kind": 2, "Wall Color": styles.rgba("#DDD0B3"),
         "Ground Color": styles.rgba("#DDD0B3"), "Trim Color": styles.rgba("#F3EBDA"), "Ground Use": 0,
         "Window Style": 1, "Plinth Height": 0.7, "Corner Style": 2, "Bays Wide": 5, "Bays Deep": 4,
         "Roof Color": styles.rgba("#555C6A"), "Flower Boxes": 0.0},
    ]
    paths = []
    for row, items in enumerate((sizes, variants)):
        for col, item in enumerate(items):
            new_scene()
            v = dict(base)
            if row == 0:
                v.update({"Bays Wide": item[0], "Bays Deep": item[1], "Floors": item[2]})
            else:
                v.update({"Bays Wide": 4, "Bays Deep": 3, "Floors": 4})
                v.update(item)
            building(v, 0.0)
            pad(-20, 20)
            w = v["Bays Wide"] * v["Bay Width"]
            h = v["Plinth Height"] + v["Ground Height"] + (v["Floors"] - 1) * v["Floor Height"]
            h += 9.0 if v.get("Tower") == 2 else 0.0      # the clock tower stands above the roof
            size = max(w, h * 1.1, 12.0) + 6.0
            camera((-size * 0.95, -size * 1.45, h * 0.6 + size * 0.45), (0.0, v["Bays Deep"] * 1.5, h * 0.5),
                   ortho=size * 1.25)
            paths.append(render(os.path.join(tmp, f"mod_{row}_{col}.png"), (700, 700)))
    sheet(paths, 4, os.path.join(OUT, "modular.png"))


if __name__ == "__main__":
    tmp = os.path.join(OUT, "_tmp")
    os.makedirs(tmp, exist_ok=True)

    new_scene()
    root, plan = make_town("Main Street", 7)
    aerial(plan)
    render(os.path.join(OUT, "hero.png"))
    X0 = plan.extent[0]
    camera((X0 + 6, plan.main.centre - 1.5, 1.7), (X0 + 40, plan.main.centre + 4, 6.0), lens=24)
    render(os.path.join(OUT, "street.png"))
    cx = (plan.extent[0] + plan.extent[1]) / 2
    camera((cx - 22, plan.main.centre - 26, 14), (cx - 4, plan.main.centre + 4, 5.0), lens=30)
    render(os.path.join(OUT, "corner.png"))

    modular_sheet(tmp)

    tiles = []
    for name, seed in (("Main Street", 7), ("Old Quarter", 3), ("Garden Suburb", 3), ("Brick Town", 2),
                       ("Market Town", 3), ("Main Street", 21)):
        new_scene()
        root, plan = make_town(name, seed)
        aerial(plan)
        tiles.append(render(os.path.join(tmp, f"preset_{len(tiles)}.png"), (800, 450)))
    sheet(tiles, 3, os.path.join(OUT, "presets.png"))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
