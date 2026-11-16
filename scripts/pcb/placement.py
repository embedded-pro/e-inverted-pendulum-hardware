"""Board geometry for scripts/pcb/board.py, in mechanical coordinates (docs/mechanical.md).

The top-left corner copies ST's NUCLEO-WB55 (MB1355 rev D-01) antenna tab (D-037): the outline, the tab depth and the
ground edge come from scripts/pcb/mb1355_rf.json (derived from STMicroelectronics MB1355, www.st.com/opla). The
top-right corner holds the NFC corner copied from ST's X-NUCLEO-NFC01A1 (MB1163 rev C-01, D-039,
scripts/pcb/mb1163_nfc.json): right of NFC_STEP_X the top edge is back at TOP_Z, and the ANT14 coil sits NFC_EDGE in
from the top and right edges with ST's coil-to-pour clearance kept free of pour and vias.

x: across the plate, 0 on the vertical centreline. z: up the plate, 0 on the wheel axle at the centre of the 25 mm
bracket strip (D-026). mm, front (component side) view.
board.py creates these items only when they are missing from the board. Component placement is the owner's, in KiCad
(D-032), so there are no anchors here.
"""

import json
import math
import pathlib

WIDTH = 85.0
BOTTOM_Z = -12.5
TOP_Z = 117.5
STRIP_TOP_Z = 12.5

MB1355 = json.loads((pathlib.Path(__file__).resolve().parent / "mb1355_rf.json").read_text(encoding="utf-8"))
MB1163 = json.loads((pathlib.Path(__file__).resolve().parent / "mb1163_nfc.json").read_text(encoding="utf-8"))


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

NFC_EDGE = 2.0  # ASSUMPTION: ANT14's copper to the top and right board edges (ST had >= 7.6 mm on a board end)
_COIL = MB1163["coil"]["bbox"]


NFC_TURN = 90.0  # degrees counter-clockwise from ST's board: D-039's 180, then the owner's 90 clockwise (2026-11-15)
NFC_DROP = 8.0  # mm the NFC group sits below the corner, so the tag clears the RF corner (owner, 2026-11-15)
DRIVE_TURN = 180.0  # degrees counter-clockwise from TI's board, about the stage's centre (owner, 2026-11-15)
# The drive block as the owner and D-050 left it: TI's stage and our extras beside it, moved with their copper by
# scripts/pcb/shift_block.py drive so that U501's footprint sits on DRIVE_TARGET (mechanical). The owner moved it 2.85 mm
# right in KiCad (D-047); D-050 moves it 8 mm further right, off the crowded left side.
DRIVE_REFS = ("U501", "Q501", "Q502", "Q503", "Q504", "R509", "R512", "NT501", "NT502", "NT503", "NT504",
              "C501", "C502", "C503", "C504", "C505", "C506", "C507", "C508", "C509", "C510", "C511", "C512", "C513",
              "C514", "D501", "D502", "D503", "D504", "R515", "R516", "R517", "R518")
DRIVE_TARGET = (6.9, 39.9966)


def _turn(a, b, degrees):
    c, s = round(math.cos(math.radians(degrees))), round(math.sin(math.radians(degrees)))
    return a * c - b * s, a * s + b * c


_COIL_CENTRE = ((_COIL[0] + _COIL[2]) / 2, (_COIL[1] + _COIL[3]) / 2)
_COIL_HALF = tuple(abs(v) for v in _turn((_COIL[2] - _COIL[0]) / 2, (_COIL[3] - _COIL[1]) / 2, NFC_TURN))


def from_mb1163(x, y):
    """MB1163 Gerber coordinates (mm, y up) to ours: turned NFC_TURN about the coil's centre, the coil's copper NFC_EDGE
    in from our top and right edges (the coil stays in the top-right corner whatever the turn)."""
    a, b = _turn(x - _COIL_CENTRE[0], y - _COIL_CENTRE[1], NFC_TURN)
    return (round(_HALF - NFC_EDGE - _COIL_HALF[0] + a, 4), round(TOP_Z - NFC_EDGE - NFC_DROP - _COIL_HALF[1] + b, 4))


NFC_COIL_BOX = (_HALF - NFC_EDGE - 2 * _COIL_HALF[0], TOP_Z - NFC_EDGE - NFC_DROP - 2 * _COIL_HALF[1], _HALF - NFC_EDGE,
                TOP_Z - NFC_EDGE - NFC_DROP)
NFC_POUR_GAP = MB1163["coil_to_pour_mm"]
NFC_STEP_X = round(NFC_COIL_BOX[0] - NFC_POUR_GAP, 4)

RULE_AREAS = [
    {"name": "ANTENNA_TAB", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"vias", "pour"},
     "polygon": [(-_HALF - 1.0, GROUND_EDGE_Z), (_TAB_RIGHT + 0.5, GROUND_EDGE_Z), (_TAB_RIGHT + 0.5, TOP_Z + 1.0),
                 (-_HALF - 1.0, TOP_Z + 1.0)]},
    {"name": "NFC_COIL", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"tracks", "vias", "pour"},
     "polygon": [(NFC_COIL_BOX[0] - 0.5, NFC_COIL_BOX[1] - 0.5), (_HALF + 1.0, NFC_COIL_BOX[1] - 0.5),
                 (_HALF + 1.0, TOP_Z + 1.0), (NFC_COIL_BOX[0] - 0.5, TOP_Z + 1.0)]},
    {"name": "NFC_POUR_GAP", "layers": ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"], "deny": {"vias", "pour"},
     "polygon": [(NFC_STEP_X, NFC_COIL_BOX[1] - NFC_POUR_GAP), (_HALF + 1.0, NFC_COIL_BOX[1] - NFC_POUR_GAP),
                 (_HALF + 1.0, TOP_Z + 1.0), (NFC_STEP_X, TOP_Z + 1.0)]},
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
    ("rect", (NFC_COIL_BOX[0], NFC_COIL_BOX[1]), (NFC_COIL_BOX[2], NFC_COIL_BOX[3]), "MB1163 NFC COIL ANT14 (D-039)"),
    ("rect", (-_HALF, GROUND_EDGE_Z), (_TAB_RIGHT, TOP_Z), "MB1355 ANTENNA TAB (D-037)"),
]

# Motor connectors and encoder inputs at the side edges (owner, D-042), raised 20 mm (owner, D-044), arranged by the
# owner in KiCad (D-047, 49b38c1); scripts/pcb/place_block.py motor_io places them, --replace puts them back here.
# (ref, x, z, rotation): mechanical, at the centre of the footprint's pads, as the owner placed them. J601's plug faces
# the left edge, pins z 35.5-45.5, the upper four over the battery cradle's relief (BATTERY_RELIEF), pin 1 (M-) at the
# top. Each chain runs inward from its connector: the ESD array beside the pins, the four row parts (A pull-up DNP, A
# 100 Ohm, B 100 Ohm, B pull-up DNP) in a column, the 1 nF caps, then the SN74LVC3G17 with its bypass. The right side is
# the owner's own arrangement, not an exact mirror. The encoder supply sits below the left chain.
MOTOR_IO_LEFT = [
    ("J601", -35.7, 40.5, 270.0),
    ("U601", -32.635, 40.5, 0.0),
    ("C603", -35.25, 32.0, 180.0),
    ("R603", -32.0, 45.0, 0.0),
    ("R604", -32.0, 43.25, 0.0),
    ("R606", -32.0, 38.0, 0.0),
    ("R605", -32.0, 36.25, 0.0),
    ("C604", -28.75, 43.25, 0.0),
    ("C605", -28.75, 38.0, 0.0),
    ("U602", -27.5, 40.5, 0.0),
    ("C606", -26.0, 38.0, 180.0),
    ("TP601", -25.5, 43.5, 0.0),
    ("TP602", -25.5, 34.5, 0.0),
]
MOTOR_IO_RIGHT = [
    ("J602", 35.7, 40.5, 90.0),
    ("U603", 32.75, 40.5, 180.0),
    ("C607", 35.25, 32.0, 0.0),
    ("R609", 31.5, 45.0, 180.0),
    ("R610", 31.5, 43.0, 180.0),
    ("R608", 31.5, 37.75, 180.0),
    ("R607", 31.5, 36.0, 180.0),
    ("C609", 28.25, 43.0, 180.0),
    ("C608", 28.225, 37.75, 180.0),
    ("U604", 27.75, 40.5, 180.0),
    ("C610", 25.5, 43.0, 0.0),
]
# Encoder supply: +5V -> R601 (or R602, DNP, from +3V3) -> F601 PTC -> C601 / C602 -> ENC_VCC.
MOTOR_IO_SUPPLY = [
    ("R601", -31.75, 32.0, 0.0),
    ("R602", -31.75, 30.25, 0.0),
    ("F601", -28.25, 32.0, 0.0),
    ("C601", -28.25, 30.0, 180.0),
    ("C602", -28.25, 28.25, 180.0),
]
# Parked off the board by the owner, to be placed by the owner (D-047): not in the tables, place_block leaves them.
MOTOR_IO_PARKED = ("TP603", "TP604", "TP605", "TP606")
# Through-hole parts whose pins may sit over the battery: the cradle has a relief for them (owner, D-044, D-047).
BATTERY_RELIEF = {"J601", "J602", "J101"}


def motor_io():
    """Every placed motor I/O part as (ref, x, z, rotation): the left chain, the right chain, the supply."""
    return MOTOR_IO_LEFT + MOTOR_IO_RIGHT + MOTOR_IO_SUPPLY

# The IMU on the centre line (owner, D-043), the flash and the EEPROM in one column left of the MCU, the EEPROM above
# (owner, D-047, 49b38c1); scripts/pcb/place_block.py imu_memory places them, --replace puts them back here.
# (ref, x, z, rotation): mechanical, at the centre of the footprint's pads. U701 (MPU-6500) at rotation 0, pin 1
# top-left: chip +X along +x, +Y up, +Z out of the component side (PS-MPU-6500A-01 s9.1); its decoupling at the pins it
# serves (Table 11: VDDIO pin 8, REGOUT pin 10, VDD pin 13), the nCS pull-up by pin 22. U702 (W25Q16JV) turned 180
# degrees, U802 (M24C64) above it.
IMU_POSITION = (0.0, 78.0)
IMU_MEMORY = [
    ("U701", IMU_POSITION[0], IMU_POSITION[1], 0.0),
    ("C702", -1.4, 75.0, 0.0),
    ("C703", 1.6, 75.3, 0.0),
    ("C701", 2.9, 77.2, 90.0),
    ("R701", -0.2, 81.675, 90.0),
    ("U702", -26.2, 82.895, 180.0),
    ("U802", -26.275, 88.9949999, 0.0),
]
# Parked off the board by the owner, to be placed by the owner (D-047): the SPI2 / INT and FLASH_NCS test pads, the
# flash's bypass and pull-ups, R301 (SPI1 SCK source termination), the EEPROM's bypass and the I2C3 pull-ups.
IMU_MEMORY_PARKED = ("TP701", "TP702", "TP703", "TP704", "TP705", "TP706", "C704", "R702", "R703", "R704", "R301",
                     "C802", "R808", "R809")


def imu_memory():
    """The placed IMU, flash and EEPROM parts, as (ref, x, z, rotation)."""
    return list(IMU_MEMORY)

# The power stage right of the power entry (owner, D-049): the TPS62933F buck and the TLV75533P LDO beside it, placed by
# scripts/pcb/place_block.py power. (ref, x, z, rotation): mechanical, at the centre of the footprint's pads.
# TI's layout guidance (TPS62933 datasheet ZHCSO99D s12.1, Fig. 12-2): every part on top; C203 (100 nF) the closest part
# to VIN / GND (pins 3 / 4), the 10 uF input caps beside it toward the power entry, so the input loop is the smallest;
# C204 (BST) between BST and SW (pins 6 / 5), L201's SW pad facing pin 5; the output caps under L201, +5V pads up toward
# its +5V pad; the EN divider, the SS cap and the FB divider in a row above the IC, the FB pair over FB (pin 8), away from
# SW and L201. The LDO sits beside the output caps, rotated so IN / EN face C209 and OUT faces C210. Test pads above.
POWER = [
    ("U201", -7.71, 58.0, 0.0),
    ("C203", -10.1, 57.5, 270.0),
    ("C202", -12.15, 57.5, 270.0),
    ("C201", -14.45, 57.5, 270.0),
    ("C204", -5.605, 57.5, 270.0),
    ("L201", -2.52, 57.25, 0.0),
    ("C208", -1.0, 52.95, 270.0),
    ("C206", -3.275, 52.95, 270.0),
    ("C207", -5.575, 52.95, 270.0),
    ("C209", -7.625, 52.95, 270.0),
    ("U202", -10.745, 52.95, 180.0),
    ("C210", -13.865, 52.95, 90.0),
    ("R201", -13.2, 62.8, 270.0),
    ("R202", -11.4, 62.8, 90.0),
    ("C205", -9.6, 62.8, 90.0),
    ("R204", -7.8, 62.8, 90.0),
    ("R203", -6.0, 62.8, 270.0),
    ("TP201", -3.4, 62.8, 0.0),
    ("TP203", -0.6, 62.8, 0.0),
    ("TP202", 2.2, 62.8, 0.0),
]


def power():
    """The buck and the LDO with their support parts and test pads, as (ref, x, z, rotation)."""
    return list(POWER)
