"""Board geometry and placement for kicad/gen/board.py, in mechanical coordinates (docs/mechanical.md).

x: across the plate, 0 on the vertical centreline. z: up the plate, 0 on the wheel axle. mm, top-side view.
Everything here is an ASSUMPTION until the owner signs off gate A (docs/layout.md); approved anchors are then
locked on the board and never moved again (power-pcb-layout s1).
"""

WIDTH = 85.0
BOTTOM_Z = -15.0
TOP_Z = 115.0

BATTERY = {"x0": -37.5, "x1": 37.5, "z0": 42.5, "z1": 77.5}
STRAP_SLOTS = [
    {"x": 0.0, "z": 39.0, "length": 22.0, "width": 3.0},
    {"x": 0.0, "z": 81.0, "length": 22.0, "width": 3.0},
]

ANTENNA_FEED = (-29.65, 108.85)
_FX, _FZ = ANTENNA_FEED
_GND_EDGE = _FZ - 0.25
_ANT_RIGHT = _FX + 3.2 + 1.0

RULE_AREAS = [
    {"name": "ANTENNA_KEEPOUT", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"],
     "deny": {"tracks", "vias", "pour"},
     "polygon": [(-WIDTH / 2, _FZ + 0.25), (_ANT_RIGHT, _FZ + 0.25), (_ANT_RIGHT, TOP_Z), (-WIDTH / 2, TOP_Z)]},
    {"name": "ANTENNA_BASE", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"],
     "deny": {"vias", "pour"},
     "polygon": [(-WIDTH / 2, _GND_EDGE), (_ANT_RIGHT, _GND_EDGE), (_ANT_RIGHT, _FZ + 0.25), (-WIDTH / 2, _FZ + 0.25)]},
    {"name": "BATTERY_ZONE", "layers": ["F.Cu"],
     "deny": {"footprints"},
     "polygon": [(BATTERY["x0"] - 1, BATTERY["z0"] - 1), (BATTERY["x1"] + 1, BATTERY["z0"] - 1),
                 (BATTERY["x1"] + 1, BATTERY["z1"] + 1), (BATTERY["x0"] - 1, BATTERY["z1"] + 1)]},
]

MECHANICAL = [
    {"ref": "MS1", "value": "motor mount L", "footprint": "MountingSlot_M3_10mm_NPTH_KeepOut7mm", "x": -32.0, "z": 20.0},
    {"ref": "MS2", "value": "motor mount L", "footprint": "MountingSlot_M3_10mm_NPTH_KeepOut7mm", "x": -32.0, "z": 30.0},
    {"ref": "MS3", "value": "motor mount R", "footprint": "MountingSlot_M3_10mm_NPTH_KeepOut7mm", "x": 32.0, "z": 20.0},
    {"ref": "MS4", "value": "motor mount R", "footprint": "MountingSlot_M3_10mm_NPTH_KeepOut7mm", "x": 32.0, "z": 30.0},
    {"ref": "MH1", "value": "bumper", "footprint": "MountingHole_M3_NPTH_KeepOut7mm", "x": 10.0, "z": 109.5},
    {"ref": "MH2", "value": "bumper", "footprint": "MountingHole_M3_NPTH_KeepOut7mm", "x": 37.0, "z": 109.5},
]

DRAWINGS = [
    ("rect", (BATTERY["x0"], BATTERY["z0"]), (BATTERY["x1"], BATTERY["z1"]), "BATTERY 3S 75 x 35 (top side, D-015)"),
    ("rect", (-WIDTH / 2, -12.5), (-1.0, 12.5), "MOTOR L (bottom side, continues to x -68)"),
    ("rect", (1.0, -12.5), (WIDTH / 2, 12.5), "MOTOR R (bottom side, continues to x +68)"),
    ("line", (-WIDTH / 2, 0.0), (WIDTH / 2, 0.0), "WHEEL AXLE z = 0"),
    ("rect", (-WIDTH / 2, _GND_EDGE), (_ANT_RIGHT, TOP_Z), "ANTENNA KEEP-OUT"),
]

ANCHORS = {}
