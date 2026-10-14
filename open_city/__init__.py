# SPDX-License-Identifier: GPL-3.0-or-later
"""Open City: a modular small-town generator for Blender.

Towns are planned in plain Python (streets, blocks, lots, building types, props) and built from a
modular Geometry Nodes kit: every building is its own live, editable object assembled from windows,
doors, storefronts, balconies, cornices and roofs that fit any size without stretching.
"""


def register():
    # imported here so the bpy-free modules (params, layout, styles, placement) load without Blender
    from . import ops, props, ui
    props.register()
    ops.register()
    ui.register()


def unregister():
    from . import ops, props, ui
    ui.unregister()
    ops.unregister()
    props.unregister()
