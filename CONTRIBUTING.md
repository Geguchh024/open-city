# Contributing

## Project layout

```
open_city/                 the add-on (this folder is what gets zipped)
  __init__.py              registration
  blender_manifest.toml    extension manifest
  params.py                every building input, every town setting, the presets (no bpy)
  styles.py                building roles, colour schemes, shop names (no bpy)
  layout.py                streets, blocks, zoning, lot packing -> a Plan (no bpy)
  placement.py             prop placement rules (no bpy)
  ground.py                roads, kerbs, lawns, paths, markings as mesh data (no bpy)
  gn.py                    node builder DSL: graphs read like expressions
  materials.py             stylized, attribute-driven materials
  kit/                     the modular kit, one node group per module
    parts.py               chamfered boxes, the V expression helper, the Kit part builder
    openings.py            windows, doors, storefronts and their add-ons
    roofs.py               roofs, dormers, chimneys, rooftop equipment
    street.py nature.py vehicles.py   props
  building.py              OC Building and its shell, facade, roof and tower sub-groups
  groups.py                build, find and rebuild every node group
  town.py                  turn a Plan into objects; bake
  inputs.py props.py ops.py ui.py stage.py   modifier I/O, properties, operators, sidebar, lighting
tests/run_tests.py         headless test suite
tools/render_previews.py   renders docs/images
```

## The module frame

Facade modules fill one slot: x along the wall (0 at the middle of the bay), the wall surface at y = 0
with the outside towards -y, z up from the bottom of the slot (from the street for ground-floor
modules). They read `Bay`, `Floor`, `Ground`, `Plinth`, `Win W`, `Win H`, `Sill` and `Detail`, so they
are rebuilt to fit instead of scaled. Props stand on z = 0 facing -y; cars point along +x.

## Adding things

- **A window or door:** write a builder in `kit/openings.py` with the `Kit` helper and add it to
  `BASE` (or `ADDONS` for something stacked on a slot). Teach `_facade` in `building.py` when to use it.
- **A roof:** add a group to `kit/roofs.py` and a branch in `_roof`, plus a name in
  `params.ROOF_TYPES`.
- **A prop:** add a builder to `kit/street.py`, `nature.py` or `vehicles.py`, its key to
  `placement.PROP_KEYS`, and a rule in `placement.py`.
- **A style:** add a colour scheme to `styles.py`; roles decide what a building is for.
- **A setting:** one line in `params.py`; the node group, sidebar and properties pick it up.

Bump `VERSION` in `groups.py` whenever a node group changes, so older files offer *Update Generator*.

## Tests

```
blender -b --factory-startup --python tests/run_tests.py
```

Requires Blender 5.2. The plain-Python tests check the layout (no overlaps, exact frontage, party walls,
reproducible seeds, small-town proportions) and the prop rules (nothing in buildings or doorways, cars
on the road). The Blender tests build every kit module, check that resizing adds modules without
stretching them, build whole towns, regenerate, lock, re-roll, bake and reopen a file without the
add-on.
