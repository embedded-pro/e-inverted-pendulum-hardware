"""Board geometry for kicad/gen/board.py, in mechanical coordinates (docs/mechanical.md).

x: across the plate, 0 on the vertical centreline. z: up the plate, 0 on the wheel axle at the centre of the 25 mm
bracket strip (D-026). mm, front (component side) view.
board.py creates these items only when they are missing from the board. Component placement is the owner's, in KiCad
(D-032), so there are no anchors here.
"""

WIDTH = 85.0
BOTTOM_Z = -12.5
TOP_Z = 117.5
STRIP_TOP_Z = 12.5

BATTERY = {"x0": -37.5, "x1": 37.5, "z0": 40.0, "z1": 75.0}
STRAP_SLOTS = []

ANTENNA_FEED = (0.0, 111.35)
_FX, _FZ = ANTENNA_FEED
_GND_EDGE = _FZ - 0.25
_HALF = WIDTH / 2

COIL_CENTRE = (29.0, 95.5)
COIL_KEEPOUT = (16.0, 84.5, _HALF, 106.5)

RULE_AREAS = [
    {"name": "ANTENNA_KEEPOUT", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"tracks", "vias", "pour"},
     "polygon": [(-_HALF, _FZ + 0.25), (_HALF, _FZ + 0.25), (_HALF, TOP_Z), (-_HALF, TOP_Z)]},
    {"name": "ANTENNA_BASE", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"vias", "pour"},
     "polygon": [(-_HALF, _GND_EDGE), (_HALF, _GND_EDGE), (_HALF, _FZ + 0.25), (-_HALF, _FZ + 0.25)]},
    {"name": "NFC_COIL_KEEPOUT", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"tracks", "vias", "pour"},
     "polygon": [(COIL_KEEPOUT[0], COIL_KEEPOUT[1]), (COIL_KEEPOUT[2], COIL_KEEPOUT[1]),
                 (COIL_KEEPOUT[2], COIL_KEEPOUT[3]), (COIL_KEEPOUT[0], COIL_KEEPOUT[3])]},
    {"name": "BRACKET_STRIP", "layers": ["F.Cu", "B.Cu"], "deny": set(),
     "polygon": [(-_HALF, BOTTOM_Z), (_HALF, BOTTOM_Z), (_HALF, STRIP_TOP_Z), (-_HALF, STRIP_TOP_Z)]},
    {"name": "BRACKET_BASE_CONTACT", "layers": ["B.Cu"], "deny": {"tracks", "vias", "pour"},
     "polygon": [(-_HALF, BOTTOM_Z), (_HALF, BOTTOM_Z), (_HALF, STRIP_TOP_Z), (-_HALF, STRIP_TOP_Z)]},
    {"name": "BATTERY_BACK", "layers": ["B.Cu"], "deny": set(),
     "polygon": [(BATTERY["x0"] - 1, BATTERY["z0"] - 1), (BATTERY["x1"] + 1, BATTERY["z0"] - 1),
                 (BATTERY["x1"] + 1, BATTERY["z1"] + 1), (BATTERY["x0"] - 1, BATTERY["z1"] + 1)]},
]

_M3 = "MountingHole_M3_NPTH_KeepOut7mm"
_M2 = "MountingHole_M2_NPTH_KeepOut5.5mm"
MECHANICAL = [
    {"ref": "MB1", "value": "bracket M3", "footprint": _M3, "x": -32.0, "z": 8.5},
    {"ref": "MB2", "value": "bracket M3", "footprint": _M3, "x": 32.0, "z": 8.5},
    {"ref": "MB3", "value": "bracket M3", "footprint": _M3, "x": -32.0, "z": -8.5},
    {"ref": "MB4", "value": "bracket M3", "footprint": _M3, "x": 32.0, "z": -8.5},
    {"ref": "MB5", "value": "bracket M2", "footprint": _M2, "x": -38.5, "z": 7.0},
    {"ref": "MB6", "value": "bracket M2", "footprint": _M2, "x": 38.5, "z": 7.0},
    {"ref": "MB7", "value": "bracket M2", "footprint": _M2, "x": -38.5, "z": -7.0},
    {"ref": "MB8", "value": "bracket M2", "footprint": _M2, "x": 38.5, "z": -7.0},
]

DRAWINGS = [
    ("rect", (BATTERY["x0"], BATTERY["z0"]), (BATTERY["x1"], BATTERY["z1"]), "BATTERY 3S 75 x 35 (BACK, D-025)"),
    ("rect", (-_HALF, BOTTOM_Z), (_HALF, STRIP_TOP_Z), "BRACKET STRIP: no parts (D-026)"),
    ("rect", (-49.0, -12.5), (-4.0, 12.5), ""),
    ("rect", (4.0, -12.5), (49.0, 12.5), ""),
    ("rect", (-51.0, -12.5), (-49.0, 12.5), ""),
    ("rect", (49.0, -12.5), (51.0, 12.5), ""),
    ("line", (-51.0, 0.0), (51.0, 0.0), "WHEEL AXLE z = 0 (motors + bracket behind)"),
    ("rect", (COIL_KEEPOUT[0], COIL_KEEPOUT[1]), (COIL_KEEPOUT[2], COIL_KEEPOUT[3]), "NFC COIL"),
    ("rect", (-_HALF, _GND_EDGE), (_HALF, TOP_Z), "2.4 GHz ANTENNA KEEP-OUT"),
]
