# SPDX-License-Identifier: GPL-3.0-or-later
"""Building types, architectural styles and colour schemes. No bpy.

A building's look comes from a *role* chosen by the town layout (a shop on the main street, a corner
building, a house on a quiet street, a landmark) and a *scheme*: a colour combination that is known to
work (red brick with cream trim, red plaster over a yellow shopfront, sky blue with white). Neighbours
draw different schemes and different geometry, so a row is varied but never clashes.
"""

# -- colour ----------------------------------------------------------------------------------------------


def hexlin(h):
    """'#RRGGBB' (sRGB, as a designer would pick it) to linear RGB for Blender."""
    h = h.lstrip("#")
    out = []
    for k in range(3):
        c = int(h[2 * k:2 * k + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def rgba(h):
    return (*hexlin(h), 1.0)


CREAM, WHITE, STONE_TRIM, SAND = "#F1E4C6", "#F6F2EA", "#DCCFB4", "#E6D6B0"

# (name, wall, trim, wall kind, shopfront colours that suit it)
BRICK_SCHEMES = [
    ("red brick", "#B5513A", CREAM, 1, ("#F2C94C", "#2F5D46", "#F1E4C6")),
    ("orange brick", "#C46A43", CREAM, 1, ("#2F5D46", "#2E4A6B", "#F1E4C6")),
    ("dark brick", "#9A4431", SAND, 1, ("#F1E4C6", "#3E6E8E", "#2F5D46")),
    ("tan brick", "#C98B5E", WHITE, 1, ("#2F5D46", "#7A2E2E", "#F2C94C")),
]
PAINT_SCHEMES = [
    ("pillar-box red", "#D24B3E", WHITE, 0, ("#F2C94C", "#F6F2EA", "#2E4A6B")),
    ("cornflower", "#5F8CC2", WHITE, 0, ("#F6F2EA", "#F2C94C", "#7A2E2E")),
    ("sunflower", "#EBC35A", WHITE, 0, ("#2F5D46", "#2E4A6B", "#C9573B")),
    ("mustard", "#DCA544", CREAM, 0, ("#2E4A6B", "#2F5D46", "#F6F2EA")),
    ("cream", "#EEDFBF", "#C8B286", 0, ("#2F5D46", "#7A2E2E", "#2E4A6B")),
    ("rose", "#E3A09B", WHITE, 0, ("#F6F2EA", "#2E4A6B", "#3E8E5C")),
    ("salmon", "#E58B70", WHITE, 0, ("#F6F2EA", "#2E4A6B", "#F2C94C")),
    ("sage", "#9FBA8E", WHITE, 0, ("#F6F2EA", "#7A2E2E", "#F2C94C")),
    ("mint", "#A7D2C0", WHITE, 0, ("#F6F2EA", "#2E4A6B", "#C9573B")),
    ("terracotta", "#CB7149", CREAM, 0, ("#F6F2EA", "#2F5D46", "#2E4A6B")),
    ("sky", "#86B7DA", WHITE, 0, ("#F6F2EA", "#F2C94C", "#C9573B")),
    ("apricot", "#F0B27A", WHITE, 0, ("#2E4A6B", "#F6F2EA", "#3E8E5C")),
]
STONE_SCHEMES = [
    ("limestone", "#DDD0B3", "#F3EBDA", 2, ("#2F5D46", "#2E4A6B")),
    ("sandstone", "#D8B98C", "#F1E4C6", 2, ("#2F5D46", "#7A2E2E")),
]
SIDING_SCHEMES = [
    ("powder blue", "#A8CBE0", WHITE, 3, ()),
    ("butter", "#F3E2A9", WHITE, 3, ()),
    ("pistachio", "#BCD9A6", WHITE, 3, ()),
    ("chalk", "#F2EEE4", "#9CB7C9", 3, ()),
    ("blush", "#F0C4BC", WHITE, 3, ()),
]
ACCENTS = ("#2F5D46", "#2E4A6B", "#7A2E2E", "#2B2B2E", "#2E7C7A", "#6B4429", "#3D6FA8", "#B8462F")
ROOFS_PITCHED = ("#B9583D", "#A04A33", "#C46A45", "#555C6A", "#454C59", "#7A5440")
AWNINGS = ("#F2C94C", "#D9473B", "#3E8E5C", "#3D6FA8", "#E07A3A", "#2F8C8A", "#7A2E2E", "#F2E9D8")

# shop names and whether they put tables out on the sidewalk
SHOPS = [
    ("BAKERY", False), ("CAFE", True), ("RESTAURANT", True), ("GROCERY", False), ("BOOKS", False),
    ("FLOWERS", False), ("PHARMACY", False), ("DELI", True), ("PIZZA", True), ("BISTRO", True),
    ("HARDWARE", False), ("BARBER", False), ("TAILOR", False), ("ICE CREAM", True), ("PASTRY", True),
    ("MARKET", False), ("DINER", True), ("TOYS", False), ("WINE BAR", True), ("FISH", False),
]


def _pick_scheme(rng, brick, kinds=("brick", "paint")):
    if "brick" in kinds and rng.random() < brick:
        return rng.choice(BRICK_SCHEMES)
    return rng.choice(PAINT_SCHEMES)


class Namer:
    """Hands out shop names so a town rarely repeats one."""

    def __init__(self, rng):
        self.pool = list(SHOPS)
        rng.shuffle(self.pool)
        self.rng = rng

    def take(self):
        if not self.pool:
            self.pool = list(SHOPS)
            self.rng.shuffle(self.pool)
        return self.pool.pop()


def _floors(rng, lo, hi, bias=0.5):
    """A floor count in [lo, hi], leaning towards `bias` (0 low, 1 high)."""
    if hi <= lo:
        return lo
    t = (rng.random() + rng.random() + bias * 2) / 4
    return max(lo, min(hi, lo + int(round(t * (hi - lo)))))


def style(rng, role, town, bays_wide, bays_deep, namer, used=()):
    """Every building input for one building.

    role: "shop" (a mixed-use row building on a busy street), "corner" (the same on a corner),
    "row" (a residential row house), "house" (a detached house), "landmark" (a civic building or a
    corner building with a turret). `used` holds the schemes of the neighbours, which are avoided.
    """
    var = town["Variation"]
    lo, hi = town["Min Floors"], max(town["Min Floors"], town["Max Floors"])
    p = {"Seed": rng.randint(0, 99999), "Bays Wide": bays_wide, "Bays Deep": bays_deep,
         "Bay Width": town["Bay Width"], "Floor Height": town["Floor Height"]}

    for _ in range(6):
        if role == "house":
            scheme = rng.choice(SIDING_SCHEMES + PAINT_SCHEMES[:8]) if rng.random() > town["Brick"] * 0.6 \
                else rng.choice(BRICK_SCHEMES)
        elif role == "landmark" and rng.random() < 0.6:
            scheme = rng.choice(STONE_SCHEMES)
        else:
            scheme = _pick_scheme(rng, town["Brick"])
        if scheme[0] not in used or rng.random() < 0.1:
            break
    name, wall, trim, kind, fronts = scheme
    p["Scheme"] = name
    p["Wall Kind"] = kind
    p["Wall Color"] = rgba(wall)
    p["Trim Color"] = rgba(trim)
    p["Accent Color"] = rgba(rng.choice(ACCENTS))
    p["Roof Color"] = rgba(rng.choice(ROOFS_PITCHED))
    p["Awning Color"] = rgba(rng.choice(AWNINGS))
    p["Ground Kind"] = kind
    p["Ground Color"] = p["Wall Color"]
    p["Detail"] = 1.0 if rng.random() < 0.55 + 0.4 * (1 - var) else 0.0
    p["Corner Style"] = rng.choice((0, 1, 2)) if kind != 3 else 0
    if kind == 1:
        p["Window Style"] = 0 if rng.random() < 0.7 else 1
    elif kind == 2:
        p["Window Style"] = 1 if rng.random() < 0.7 else 0
    else:
        p["Window Style"] = rng.choice((0, 0, 1, 2, 2))
    p["Shutters"] = kind in (0, 3) and p["Window Style"] != 2 and rng.random() < 0.55
    p["Flower Boxes"] = round(rng.uniform(0.0, 0.6) if rng.random() < 0.6 else 0.0, 2)
    p["Balconies"] = 0.0
    p["Balcony Style"] = rng.choice((0, 0, 1, 2))
    p["Chimneys"] = rng.choice((0, 1, 1, 2))
    p["Rooftop Units"] = True
    p["Tower"] = 0
    p["Awnings"] = 0
    p["Ground Use"] = 0
    p["Shop Name"] = ""
    p["Entrance Bay"] = -1
    p["Corner Side"] = 0
    p["Attached Left"] = False
    p["Attached Right"] = False
    p["Gable Front"] = False
    p["Roof Pitch"] = round(rng.uniform(32, 42), 1)
    p["Ground Height"] = 3.3
    p["Plinth Height"] = round(rng.uniform(0.4, 0.6), 2)
    p["Shop Kind"] = ""

    if role in ("shop", "corner"):
        p["Floors"] = _floors(rng, max(lo, 2), hi, 0.6 if role == "corner" else 0.45)
        if role == "corner":
            p["Floors"] = min(hi + 1, p["Floors"] + (1 if rng.random() < 0.5 else 0))
        p["Roof Type"] = rng.choice((0, 0, 0, 1, 4)) if kind != 0 or rng.random() < 0.6 else rng.choice((2, 4))
        p["Balconies"] = round(rng.uniform(0.25, 0.7), 2) if kind == 0 or rng.random() < 0.3 else 0.0
        _make_shop(rng, p, town, fronts, namer)
    elif role == "row":
        p["Floors"] = _floors(rng, lo, hi, 0.4)
        p["Roof Type"] = rng.choice((0, 1, 1)) if kind == 1 else rng.choice((0, 2, 2, 4))
        p["Balconies"] = round(rng.uniform(0.0, 0.5), 2) if kind == 0 else 0.0
        if p["Roof Type"] == 2 and p["Floors"] <= 2 and rng.random() < 0.4:
            p["Gable Front"] = True
    elif role == "house":
        p["Floors"] = 1 if lo <= 1 and rng.random() < 0.25 else 2
        p["Roof Type"] = rng.choice((2, 2, 3))
        p["Gable Front"] = p["Roof Type"] == 2 and rng.random() < 0.5
        p["Rooftop Units"] = False
        p["Chimneys"] = 1
        p["Detail"] = 0.0 if kind == 3 else p["Detail"]
        p["Corner Style"] = 0 if kind == 3 else p["Corner Style"]
        p["Flower Boxes"] = round(rng.uniform(0.3, 0.9), 2)
        p["Ground Height"] = 3.0
    elif role == "landmark":
        p["Floors"] = min(10, max(hi, 3) + 1)
        p["Detail"] = 1.0
        p["Corner Style"] = 2
        if p["Wall Kind"] == 2 or rng.random() < 0.5:
            p["Tower"] = 2
            p["Roof Type"] = 0
            p["Window Style"] = 1
            p["Plinth Height"] = 0.7
            p["Ground Height"] = 4.0
            p["Chimneys"] = 0
            p["Flower Boxes"] = 0.0
            p["Balconies"] = 0.0
            p["Shutters"] = False
        else:
            p["Tower"] = 1
            p["Roof Type"] = 4
            p["Balconies"] = round(rng.uniform(0.3, 0.6), 2)
            _make_shop(rng, p, town, fronts, namer)
    if p["Ground Use"] == 0 and role != "landmark" and p["Window Style"] == 2:
        p["Plinth Height"] = 0.3
    return p


def _make_shop(rng, p, town, fronts, namer):
    if rng.random() > town["Shops"]:
        return
    name, outdoor = namer.take()
    p["Ground Use"] = 1
    p["Shop Name"] = name
    p["Shop Kind"] = "cafe" if outdoor else "shop"
    p["Plinth Height"] = 0.15
    p["Ground Height"] = round(rng.uniform(3.8, 4.3), 2)
    p["Awnings"] = rng.choice((1, 1, 1, 2, 0))
    if fronts and rng.random() < 0.7:
        p["Accent Color"] = rgba(rng.choice(fronts))
    if p["Wall Kind"] == 0 and rng.random() < 0.45:
        # a contrasting painted shopfront storey (reference: the red restaurant on yellow)
        p["Ground Color"] = rgba(rng.choice(("#F0C24B", "#F6F2EA", "#2F5D46", "#EBDDBE")))
        if p["Ground Color"] == rgba("#2F5D46"):
            p["Accent Color"] = rgba("#F1E4C6")
    bays = p["Bays Wide"]
    if bays >= 3:
        p["Entrance Bay"] = rng.choice((0, (bays - 1) // 2, bays - 1))
    else:
        p["Entrance Bay"] = rng.choice((0, bays - 1))


def entrance_bay(p):
    """The bay of the front door, as the building module resolves it."""
    e = p.get("Entrance Bay", -1)
    if e < 0 or e >= p["Bays Wide"]:
        return (p["Bays Wide"] - 1) // 2
    return e
