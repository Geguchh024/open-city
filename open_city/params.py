# SPDX-License-Identifier: GPL-3.0-or-later
"""Generation settings: every input of a building, every setting of a town, and the town presets.

No bpy in here. The building node group, the sidebar, the property groups and the tests all read these
tables, so a new setting is one line here.

Each entry is (name, kind, default, options). `panel` groups settings in the UI; `items` names the
choices of an integer that works as a dropdown.
"""

# -- a building ---------------------------------------------------------------------------------------
SHAPE, FACADE, GROUND, ROOF, COLOURS = "Shape", "Facade", "Ground Floor", "Roof", "Colours"

WINDOW_STYLES = ("Sash", "Arched", "Wide")
BALCONY_STYLES = ("Iron", "Stone", "Juliet")
CORNER_STYLES = ("Plain", "Quoins", "Pilasters")
GROUND_USES = ("Residential", "Shop")
AWNING_STYLES = ("None", "Striped", "Plain")
CORNER_SIDES = ("None", "Left", "Right")
ROOF_TYPES = ("Parapet", "Flat", "Gable", "Hip", "Mansard")
TOWERS = ("None", "Corner Turret", "Clock Tower")
WALL_KINDS = ("Plaster", "Brick", "Stone", "Siding")
SURROUNDINGS = ("Open", "Forest", "Hills & Forest")

BUILDING_PARAMS = [
    ("Seed", "int", 0, dict(panel=SHAPE, min=0, max=100000, tip="Small variations: balconies, flowers, curtains")),
    ("Bays Wide", "int", 3, dict(panel=SHAPE, min=1, max=10, tip="Facade width in window bays")),
    ("Bays Deep", "int", 3, dict(panel=SHAPE, min=1, max=8, tip="Building depth in window bays")),
    ("Floors", "int", 3, dict(panel=SHAPE, min=1, max=10, tip="Number of storeys, ground floor included")),
    ("Bay Width", "float", 3.0, dict(panel=SHAPE, min=2.2, max=4.5, subtype="DISTANCE",
                                     tip="Width of one bay: the grid every facade module snaps to")),
    ("Floor Height", "float", 3.0, dict(panel=SHAPE, min=2.6, max=4.2, subtype="DISTANCE")),
    ("Ground Height", "float", 3.7, dict(panel=SHAPE, min=2.8, max=5.0, subtype="DISTANCE",
                                         tip="Height of the ground floor (shops are usually taller)")),
    ("Plinth Height", "float", 0.45, dict(panel=SHAPE, min=0.05, max=1.2, subtype="DISTANCE",
                                          tip="Stone base; front steps are added to reach it")),

    ("Window Style", "int", 0, dict(panel=FACADE, min=0, max=2, items=WINDOW_STYLES)),
    ("Shutters", "bool", False, dict(panel=FACADE)),
    ("Flower Boxes", "float", 0.3, dict(panel=FACADE, min=0.0, max=1.0)),
    ("Balconies", "float", 0.3, dict(panel=FACADE, min=0.0, max=1.0, tip="Share of window columns with balconies")),
    ("Balcony Style", "int", 0, dict(panel=FACADE, min=0, max=2, items=BALCONY_STYLES)),
    ("Corner Style", "int", 0, dict(panel=FACADE, min=0, max=2, items=CORNER_STYLES)),
    ("Detail", "float", 1.0, dict(panel=FACADE, min=0.0, max=1.0,
                                  tip="Dentils, keystones, string courses and brackets")),
    ("Attached Left", "bool", False, dict(panel=FACADE, tip="A neighbour shares the left wall: no windows there")),
    ("Attached Right", "bool", False, dict(panel=FACADE)),

    ("Ground Use", "int", 0, dict(panel=GROUND, min=0, max=1, items=GROUND_USES)),
    ("Shop Name", "string", "", dict(panel=GROUND)),
    ("Entrance Bay", "int", -1, dict(panel=GROUND, min=-1, max=9, tip="Bay of the front door; -1 is the middle")),
    ("Awnings", "int", 1, dict(panel=GROUND, min=0, max=2, items=AWNING_STYLES)),
    ("Corner Side", "int", 0, dict(panel=GROUND, min=0, max=2, items=CORNER_SIDES,
                                   tip="On a street corner: that side gets a full street facade")),

    ("Roof Type", "int", 0, dict(panel=ROOF, min=0, max=4, items=ROOF_TYPES)),
    ("Roof Pitch", "float", 35.0, dict(panel=ROOF, min=15.0, max=55.0)),
    ("Gable Front", "bool", False, dict(panel=ROOF, tip="Pitched roofs: the ridge runs back from the street")),
    ("Chimneys", "int", 1, dict(panel=ROOF, min=0, max=3)),
    ("Rooftop Units", "bool", True, dict(panel=ROOF, tip="Air conditioning, vents and hatches on flat roofs")),
    ("Tower", "int", 0, dict(panel=ROOF, min=0, max=2, items=TOWERS)),

    ("Wall Kind", "int", 1, dict(panel=COLOURS, min=0, max=3, items=WALL_KINDS)),
    ("Ground Kind", "int", 1, dict(panel=COLOURS, min=0, max=3, items=WALL_KINDS)),
    ("Wall Color", "color", (0.55, 0.12, 0.07, 1.0), dict(panel=COLOURS)),
    ("Ground Color", "color", (0.55, 0.12, 0.07, 1.0), dict(panel=COLOURS)),
    ("Trim Color", "color", (0.85, 0.78, 0.62, 1.0), dict(panel=COLOURS)),
    ("Accent Color", "color", (0.05, 0.16, 0.1, 1.0), dict(panel=COLOURS)),
    ("Roof Color", "color", (0.42, 0.11, 0.06, 1.0), dict(panel=COLOURS)),
    ("Awning Color", "color", (0.85, 0.6, 0.12, 1.0), dict(panel=COLOURS)),
]

# -- a town -------------------------------------------------------------------------------------------
T_LAYOUT, T_BUILDINGS, T_STREETS, T_DETAILS = "Layout", "Buildings", "Streets", "Details"

TOWN_PARAMS = [
    ("Seed", "int", 7, dict(panel=T_LAYOUT, min=0, max=100000, tip="Same seed and settings, same town")),
    ("Blocks X", "int", 2, dict(panel=T_LAYOUT, min=1, max=6, tip="City blocks across")),
    ("Blocks Y", "int", 2, dict(panel=T_LAYOUT, min=1, max=6, tip="City blocks deep")),
    ("Block Width", "float", 36.0, dict(panel=T_LAYOUT, min=20.0, max=90.0, subtype="DISTANCE")),
    ("Block Depth", "float", 30.0, dict(panel=T_LAYOUT, min=18.0, max=70.0, subtype="DISTANCE")),
    ("Block Variation", "float", 0.25, dict(panel=T_LAYOUT, min=0.0, max=1.0,
                                            tip="How much block sizes differ from each other")),
    ("Parks", "float", 0.25, dict(panel=T_LAYOUT, min=0.0, max=0.6, tip="Share of blocks that become parks")),

    ("Density", "float", 0.7, dict(panel=T_BUILDINGS, min=0.1, max=1.0,
                                    tip="How much of each street front is built up")),
    ("Min Floors", "int", 2, dict(panel=T_BUILDINGS, min=1, max=6)),
    ("Max Floors", "int", 4, dict(panel=T_BUILDINGS, min=1, max=8)),
    ("Landmarks", "float", 0.5, dict(panel=T_BUILDINGS, min=0.0, max=1.0,
                                     tip="Chance of a taller landmark: a clock tower or a corner turret")),
    ("Shops", "float", 0.7, dict(panel=T_BUILDINGS, min=0.0, max=1.0,
                                 tip="Share of ground floors on busy streets that are shops and cafes")),
    ("Variation", "float", 0.7, dict(panel=T_BUILDINGS, min=0.0, max=1.0,
                                     tip="How different neighbouring buildings are")),
    ("Brick", "float", 0.4, dict(panel=T_BUILDINGS, min=0.0, max=1.0, tip="Share of red-brick buildings")),
    ("Bay Width", "float", 3.0, dict(panel=T_BUILDINGS, min=2.4, max=4.0, subtype="DISTANCE")),
    ("Floor Height", "float", 3.0, dict(panel=T_BUILDINGS, min=2.6, max=3.8, subtype="DISTANCE")),

    ("Street Width", "float", 7.0, dict(panel=T_STREETS, min=4.5, max=14.0, subtype="DISTANCE",
                                        tip="Road between the kerbs")),
    ("Sidewalk Width", "float", 3.0, dict(panel=T_STREETS, min=1.5, max=6.0, subtype="DISTANCE")),
    ("Parking", "float", 0.5, dict(panel=T_STREETS, min=0.0, max=1.0, tip="Cars parked along the kerbs")),
    ("Traffic", "float", 0.25, dict(panel=T_STREETS, min=0.0, max=1.0,
                                    tip="Cars driving round the blocks (animated: press play)")),
    ("Traffic Speed", "float", 8.0, dict(panel=T_STREETS, min=0.0, max=20.0,
                                         tip="How fast the traffic drives, in metres per second")),

    ("Street Lights", "float", 0.7, dict(panel=T_DETAILS, min=0.0, max=1.0)),
    ("Trees", "float", 0.7, dict(panel=T_DETAILS, min=0.0, max=1.0)),
    ("Furniture", "float", 0.7, dict(panel=T_DETAILS, min=0.0, max=1.0,
                                     tip="Benches, bins, hydrants, signs, cafe tables and planters")),
    ("Surroundings", "int", 2, dict(panel=T_DETAILS, min=0, max=2, items=SURROUNDINGS,
                                    tip="What closes off the edge of town: open fields, a forest, or a valley "
                                        "of wooded hills")),
    ("Diorama Base", "bool", False, dict(panel=T_DETAILS, tip="Stand the town on a thick base, like a model")),
]

BY_NAME = {p[0]: p for p in BUILDING_PARAMS}
TOWN_BY_NAME = {p[0]: p for p in TOWN_PARAMS}


def _defaults(table):
    return {name: default for name, _kind, default, _o in table}


def building_defaults():
    return _defaults(BUILDING_PARAMS)


def town_defaults():
    return _defaults(TOWN_PARAMS)


def clamp_value(name, value, table=None):
    """Clamp a value to the range of the setting (building settings unless `table` is given)."""
    by = table or BY_NAME
    _n, kind, _d, opts = by[name]
    if kind == "bool":
        return bool(value)
    if kind in ("int", "float"):
        lo, hi = opts.get("min"), opts.get("max")
        if lo is not None:
            value = max(lo, value)
        if hi is not None:
            value = min(hi, value)
        return int(round(value)) if kind == "int" else float(value)
    return value


# -- town presets: only the differences from the defaults ---------------------------------------------------
PRESETS = {
    "Main Street": dict(
        desc="Two by two blocks round a park: shops, cafes and brick apartments.",
        values={}),
    "Old Quarter": dict(
        desc="Tight blocks of tall painted houses, narrow streets, lots of shops.",
        values={"Blocks X": 3, "Blocks Y": 2, "Block Width": 32.0, "Block Depth": 28.0, "Street Width": 6.0,
                "Sidewalk Width": 2.6, "Density": 0.95, "Min Floors": 3, "Max Floors": 5, "Parks": 0.15,
                "Brick": 0.25, "Shops": 0.85, "Parking": 0.3}),
    "Garden Suburb": dict(
        desc="Quiet streets of detached houses with gardens, hedges and trees.",
        values={"Blocks X": 2, "Blocks Y": 2, "Block Width": 46.0, "Block Depth": 36.0, "Density": 0.45,
                "Min Floors": 1, "Max Floors": 2, "Shops": 0.15, "Landmarks": 0.0, "Trees": 1.0,
                "Parks": 0.2, "Brick": 0.2, "Traffic": 0.1}),
    "Brick Town": dict(
        desc="Red-brick rows with stoops and dentil cornices, one long main street.",
        values={"Blocks X": 3, "Blocks Y": 1, "Block Width": 40.0, "Block Depth": 30.0, "Brick": 0.85,
                "Min Floors": 2, "Max Floors": 4, "Density": 0.9, "Parks": 0.0}),
    "Market Town": dict(
        desc="Three by two blocks with a central square and a clock tower.",
        values={"Blocks X": 3, "Blocks Y": 2, "Block Width": 38.0, "Block Depth": 32.0, "Landmarks": 1.0,
                "Parks": 0.2, "Max Floors": 5}),
}


def preset_values(name):
    """A full set of town settings for a preset: the defaults plus its changes."""
    v = town_defaults()
    v.update(PRESETS[name]["values"])
    return v
