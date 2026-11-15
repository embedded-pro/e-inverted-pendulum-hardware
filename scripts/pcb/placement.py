"""Board geometry for scripts/pcb/board.py, in mechanical coordinates (docs/mechanical.md).

The top-left corner copies ST's NUCLEO-WB55 (MB1355 rev D-01) antenna tab (D-037): the outline, the tab depth and the
ground edge come from scripts/pcb/mb1355_rf.json (derived from STMicroelectronics MB1355, www.st.com/opla).

x: across the plate, 0 on the vertical centreline. z: up the plate, 0 on the wheel axle at the centre of the 25 mm
bracket strip (D-026). mm, front (component side) view.
board.py creates these items only when they are missing from the board. Component placement is the owner's, in KiCad
(D-032), so there are no anchors here.
"""

import json
import pathlib

WIDTH = 85.0
BOTTOM_Z = -12.5
TOP_Z = 117.5
STRIP_TOP_Z = 12.5

MB1355 = json.loads((pathlib.Path(__file__).resolve().parent / "mb1355_rf.json").read_text(encoding="utf-8"))


def from_mb1355(x, y):
    """ST board coordinates (mm, y down) to ours, with ST's board-left edge and tab top on our top-left corner."""
    return (round(-WIDTH / 2 + (x - MB1355["board_left_x"]), 4), round(TOP_Z - (y - MB1355["tab_top_y"]), 4))


def _intersect(a, b):
    (x1, y1), (x2, y2) = a
    (x3, y3), (x4, y4) = b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _tab_outline():
    """MB1355's tab and step as corner points, from the top of its left edge to the step's foot.

    Each corner is the intersection of two consecutive straight edges, so ST's 0.04 mm fillets drop out."""
    segments = [tuple(map(tuple, seg)) for seg in MB1355["outline_segments"]]
    left = [seg for seg in segments if abs(seg[0][0] - seg[1][0]) < 1e-3 and seg[0][0] < MB1355["board_left_x"] + 0.1]
    rest = sorted((seg for seg in segments if seg not in left),
                  key=lambda seg: (min(seg[0][0], seg[1][0]), min(seg[0][1], seg[1][1])))
    path = left + rest
    corners = [_intersect(path[i], path[i + 1]) for i in range(len(path) - 1)]
    return [from_mb1355(*c) for c in corners]


TAB_OUTLINE = _tab_outline()
TOP_RIGHT_Z = TAB_OUTLINE[-1][1]
GROUND_EDGE_Z = round(TOP_Z - (MB1355["ground_edge_y"] - MB1355["tab_top_y"]), 4)

BATTERY = {"x0": -37.5, "x1": 37.5, "z0": 40.0, "z1": 75.0}
STRAP_SLOTS = []

_HALF = WIDTH / 2
_TAB_RIGHT = TAB_OUTLINE[-1][0]

COIL_CENTRE = (29.0, 95.5)
COIL_KEEPOUT = (16.0, 84.5, _HALF, 106.5)

RULE_AREAS = [
    {"name": "ANTENNA_TAB", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"vias", "pour"},
     "polygon": [(-_HALF - 1.0, GROUND_EDGE_Z), (_TAB_RIGHT + 0.5, GROUND_EDGE_Z), (_TAB_RIGHT + 0.5, TOP_Z + 1.0),
                 (-_HALF - 1.0, TOP_Z + 1.0)]},
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
    ("rect", (-_HALF, GROUND_EDGE_Z), (_TAB_RIGHT, TOP_Z), "MB1355 ANTENNA TAB (D-037)"),
]
