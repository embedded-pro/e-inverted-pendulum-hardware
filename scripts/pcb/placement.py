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

# Power-bus copper (D-056, docs/power-map.md), mechanical x, z. L3 (In2.Cu) carries VBAT in one wide corridor from the
# power entry past the buck input to the drive (4.2 A on 0.5 oz inner copper needs 11.3 mm, IPC-2221 at 10 degC), with a
# lobe under TP101; the rest of L3 is GND. L1 carries the short hops of the power entry (BAT_P, BAT_F, PP_S, each at least
# 2.2 mm, the 4.2 A outer width) and VBAT at Q101 and at the buck input, where the via arrays drop to L3.
L3_VBAT = [(-41.0, 64.0), (-30.0, 64.0), (-30.0, 70.0), (-26.0, 70.0), (-26.0, 64.0), (-3.0, 64.0), (-3.0, 50.0),
           (29.0, 50.0), (29.0, STRIP_TOP_Z), (-22.0, STRIP_TOP_Z), (-22.0, 47.0), (-41.0, 47.0)]
L1_POWER = {
    "L1_BAT_P": ("BAT_P", [(-39.6, 49.6), (-36.4, 49.6), (-36.4, 58.2), (-39.6, 58.2)]),
    "L1_BAT_F": ("BAT_F", [(-35.8, 49.6), (-31.5, 49.6), (-31.5, 55.85), (-35.8, 55.85)]),
    "L1_PP_S": ("PP_S", [(-28.75, 53.7), (-22.6, 53.7), (-22.6, 57.2), (-28.75, 57.2)]),
    "L1_VBAT_ENTRY": ("VBAT", [(-35.3, 56.3), (-31.5, 56.3), (-31.5, 60.2), (-33.9, 60.2), (-33.9, 64.0),
                               (-35.3, 64.0)]),
    "L1_VBAT_BUCK": ("VBAT", [(-22.2, 57.2), (-19.6, 57.2), (-19.6, 56.0), (-16.6, 56.0), (-16.6, 57.4), (-8.2, 57.4),
                              (-8.2, 60.4), (-22.2, 60.4)]),
}

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
# the owner's own arrangement, not an exact mirror. The encoder supply sits below the left chain. Both chains and the
# supply sit 2.05 mm in from the owner's spots, moved with their tracks by shift_block.py motor_left / motor_right, so
# J601 / J602's bodies keep JLCPCB's 2.5 mm from the edge (D-052).
MOTOR_IO_LEFT = [
    ("J601", -33.65, 40.5, 270.0),
    ("U601", -30.585, 40.5, 0.0),
    ("C603", -33.2, 32.0, 180.0),
    ("R603", -29.95, 45.0, 0.0),
    ("R604", -29.95, 43.25, 0.0),
    ("R606", -29.95, 38.0, 0.0),
    ("R605", -29.95, 36.25, 0.0),
    ("C604", -26.7, 43.25, 0.0),
    ("C605", -26.7, 38.0, 0.0),
    ("U602", -25.45, 40.5, 0.0),
    ("C606", -23.95, 38.0, 180.0),
    ("TP601", -23.45, 43.5, 0.0),
    ("TP602", -23.45, 34.5, 0.0),
]
MOTOR_IO_RIGHT = [
    ("J602", 33.65, 40.5, 90.0),
    ("U603", 30.7, 40.5, 180.0),
    ("C607", 33.2, 32.0, 0.0),
    ("R609", 29.45, 45.0, 180.0),
    ("R610", 29.45, 43.0, 180.0),
    ("R608", 29.45, 37.75, 180.0),
    ("R607", 29.45, 36.0, 180.0),
    ("C609", 26.2, 43.0, 180.0),
    ("C608", 26.175, 37.75, 180.0),
    ("U604", 25.7, 40.5, 180.0),
    ("C610", 23.45, 43.0, 0.0),
    ("TP603", 23.45, 44.5, 0.0),
    ("TP604", 23.45, 36.0, 0.0),
]
# Encoder supply: +5V -> R601 (or R602, DNP, from +3V3) -> F601 PTC -> C601 / C602 -> ENC_VCC.
MOTOR_IO_SUPPLY = [
    ("R601", -29.7, 32.0, 0.0),
    ("R602", -29.7, 30.25, 0.0),
    ("F601", -26.2, 32.0, 0.0),
    ("C601", -26.2, 30.0, 180.0),
    ("C602", -26.2, 28.25, 180.0),
]
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
def imu_memory():
    """The placed IMU, flash and EEPROM parts, as (ref, x, z, rotation)."""
    return list(IMU_MEMORY)

# The power stage right of the power entry (owner, D-049): the TPS62933F buck and the TLV75533P LDO beside it, placed by
# scripts/pcb/place_block.py power. (ref, x, z, rotation): mechanical, at the centre of the footprint's pads.
# TI's layout guidance (TPS62933 datasheet ZHCSO99D s12.1, Fig. 12-2): every part on top; C203 (100 nF) the closest part
# to VIN / GND (pins 3 / 4), the 10 uF input caps beside it toward the power entry, so the input loop is the smallest;
# C204 (BST) between BST and SW (pins 6 / 5), L201's SW pad facing pin 5; the output caps under L201, +5V pads up toward
# its +5V pad; the EN divider, the SS cap and the FB divider in a row above the IC, the FB pair over FB (pin 8), away from
# SW and L201. The LDO sits beside the output caps, rotated so IN / EN face C209 and OUT faces C210. Test pads right
# of L201 (moved there by D-050 to leave the LED rings room for labels).
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
    ("TP201", 1.4, 59.6, 0.0),
    ("TP203", 1.4, 56.85, 0.0),
    ("TP202", 1.4, 54.1, 0.0),
]


def power():
    """The buck and the LDO with their support parts and test pads, as (ref, x, z, rotation)."""
    return list(POWER)

# The power entry at the left edge, the owner's arrangement (D-047, 49b38c1), placed by scripts/pcb/place_block.py
# power_entry. (ref, x, z, rotation): mechanical, at the centre of the footprint's pads. J101 (XT30) moved 0.9 mm inward
# so its body keeps JLCPCB's 2.5 mm from the edge, and R104 / C103 / R105 (0.5 mm), Q101 (0.35 mm) and D101 (0.05 mm)
# moved right with it to keep their 0.5 mm (D-052).
POWER_ENTRY = [
    ("J101", -37.1, 58.9, 90.0),
    ("F101", -36.4, 50.7, 0.0),
    ("Q101", -30.225, 56.005, 180.0),
    ("D101", -25.25, 53.4, 270.0),
    ("D102", -18.1, 55.2, 270.0),
    ("R101", -25.7, 57.575, 270.0),
    ("R102", -23.9, 57.6, 270.0),
    ("R103", -21.4, 53.6, 90.0),
    ("R104", -32.4, 59.7, 0.0),
    ("R105", -32.4, 63.3, 180.0),
    ("C101", -21.4, 56.9, 90.0),
    ("C102", -23.1, 53.6, 90.0),
    ("C103", -32.4, 61.5, 180.0),
]


def power_entry():
    """The battery connector, the fuse, the reverse / soft-start FETs and their parts, as (ref, x, z, rotation)."""
    return list(POWER_ENTRY)


# The 12 RGB LEDs in the centre as two square rings (owner, D-050), placed by scripts/pcb/place_block.py leds.
# (ref, x, z, rotation): mechanical, at the centre of the footprint's pads. Each ring has 6 WS2812B-2020 on a 7.0 mm square:
# the four corners and the middle of the top and bottom sides, 3.5 mm pitch; the rings are centred at (-9, 70.5) and
# (+9, 70.5), mirrored about the centre line, between the power block and the IMU. The chain runs D802 (bottom middle of the
# left ring) round the left ring to D807 (bottom right), across the centre to D808 (bottom left of the right ring) and
# round it to D813, so every DOUT -> DIN link is short. Bottom-row LEDs at 0 degrees and top-row LEDs at 180 so every VDD
# pad faces the inside of its ring, where its 100 nF cap (C806-C817 in chain order) sits with its +5V pad toward it. The
# chain's driver (U804 with C801, R803, R802 at its output, C805 bulk, TP801) is left of the left ring; the green status
# LED D801 with R801 sits on the centre line between the rings.
LEDS = [
    ("D802", -9.0, 67.0, 0.0),
    ("C806", -8.565, 69.05, 180.0),
    ("D803", -12.5, 67.0, 0.0),
    ("C807", -12.065, 69.05, 180.0),
    ("D804", -12.5, 74.0, 180.0),
    ("C808", -12.935, 71.95, 0.0),
    ("D805", -9.0, 74.0, 180.0),
    ("C809", -9.435, 71.95, 0.0),
    ("D806", -5.5, 74.0, 180.0),
    ("C810", -5.935, 71.95, 0.0),
    ("D807", -5.5, 67.0, 0.0),
    ("C811", -5.065, 69.05, 180.0),
    ("D808", 5.5, 67.0, 0.0),
    ("C812", 5.935, 69.05, 180.0),
    ("D809", 5.5, 74.0, 180.0),
    ("C813", 5.065, 71.95, 0.0),
    ("D810", 9.0, 74.0, 180.0),
    ("C814", 8.565, 71.95, 0.0),
    ("D811", 12.5, 74.0, 180.0),
    ("C815", 12.065, 71.95, 0.0),
    ("D812", 12.5, 67.0, 0.0),
    ("C816", 12.935, 69.05, 180.0),
    ("D813", 9.0, 67.0, 0.0),
    ("C817", 9.435, 69.05, 180.0),
    ("D801", 0.0, 71.0, 270.0),
    ("R801", 0.0, 67.6, 90.0),
    ("U804", -17.6, 69.5, 0.0),
    ("R802", -16.2, 66.4, 0.0),
    ("C801", -16.943, 72.05, 180.0),
    ("R803", -21.0, 69.5, 270.0),
    ("TP801", -21.0, 73.0, 0.0),
    ("C805", -17.6, 74.0, 0.0),
]


def leds():
    """The RGB LED rings, their caps, the chain's driver and the status LED, as (ref, x, z, rotation)."""
    return list(LEDS)

# The remaining parts (owner, D-051), placed by scripts/pcb/place_block.py rest: the edge parts first, then the support
# parts at their pins, then the test pads in rows per block in the room left. (ref, x, z, rotation): mechanical, at the
# centre of the footprint's pads. Each spot clears every courtyard, other-net copper and silk outline (place_block), keeps
# JLCPCB's assembly spacing (0.5 mm to every part, bodies 2.5 mm from the edge, D-052) and leaves each test pad's name a
# clean spot (silk.py). The edge parts sit 2 mm in from where D-051 put them (D-052). Parked for the owner: MC1-MC4 and
# MH1 / MH2 (the cradle and the bumpers aren't designed yet).
REST_EDGE = [
    ("SW101", -36.5, 83.7, 90.0),
    ("J801", -37.18, 70.0, 270.0),
    ("U801", -32.63, 68.5, 0.0),
]
# Support parts at the nearest spot to the pin they serve that keeps every label; C803 on ST's MB1163 land (D-039).
# R808 / R809 (I2C3 pull-ups) by the Qwiic port's ESD, where the bus enters; R301 (SPI1 SCK 33 Ohm) 6 mm down the SCK
# route from its fan-out via; R302 (BOOT0 pull-down) 3.8 mm from its via; R702 clear of U702's pin-1 mark; C704 0.5 mm
# from U702 (D-052).
REST_SUPPORT = [
    ("C803", -9.85, 90.45, 90.0),
    ("C704", -30.21, 79.85, 0.0),
    ("R702", -21.0, 79.45, 0.0),
    ("R703", -20.812, 83.53, 90.0),
    ("R704", -31.62, 82.011, 90.0),
    ("C802", -22.0, 91.0, 90.0),
    ("R808", -31.6, 74.8, 90.0),
    ("R809", -31.6, 71.7, 90.0),
    ("R301", -19.3, 87.5, 90.0),
    ("R302", -9.6, 97.5, 0.0),
]
TP_PITCH = 2.4
TP_PITCH_LARGE = 2.7
_LARGE_TPS = {"TP101", "TP105", "TP303", "TP516", "TP517", "TP605", "TP606", "TP804"}


def tp_row(refs, x, z, along="x"):
    """Test pads in a straight row (along x, left to right) or column (along z, top down): TP_PITCH centre to centre,
    TP_PITCH_LARGE next to a 1.5 mm pad."""
    out = []
    for i, ref in enumerate(refs):
        out.append((ref, round(x, 4), round(z, 4), 0.0))
        if i + 1 < len(refs):
            step = TP_PITCH_LARGE if {ref, refs[i + 1]} & _LARGE_TPS else TP_PITCH
            x, z = (x + step, z) if along == "x" else (x, z - step)
    return out


# Test pads in rows per block (owner), each beside the copper it probes: the power entry in a column right of the
# Qwiic port's pull-ups, BAT_F / PP_G nearest Q101; the Qwiic port's beside it; the drive's logic in a row right of the
# power block, above the DRV8711's logic vias; its power test pads in one row per bridge, below each motor's phase route
# (left: MOT_L, SENSE_B; right: MOT_R, SENSE_A); the MCU's above J301 (NRST, VFBSMPS nearest their pins), but VDDA's
# (TP303) beside the VDDA caps, 2.1 mm from C311's pad (D-052); the IMU's SPI2 / INT with FLASH_NCS in one row left of the
# IMU; ENC_VCC with a GND below the encoder supply. The right encoder's (TP603 / TP604) are in MOTOR_IO_RIGHT, as the
# left's. The Qwiic column runs SDA, GND, SCL so QWIIC_SDA's name has room (D-052).
REST_TEST_PADS = (
    tp_row(("TP102", "TP103", "TP101", "TP105", "TP104"), -28.0, 73.5, "z")
    + tp_row(("TP802", "TP804", "TP803"), -24.0, 72.6, "z")
    + tp_row(("TP511", "TP515", "TP512", "TP514", "TP513", "TP508", "TP507", "TP509", "TP510"), 9.0, 53.5)
    + tp_row(("TP503", "TP504", "TP502", "TP516"), -17.0, 29.0)
    + tp_row(("TP517", "TP501", "TP506", "TP505"), 27.0, 28.0)
    + tp_row(("TP301", "TP304", "TP302"), -37.5, 104.0)
    + tp_row(("TP706", "TP704", "TP701", "TP702", "TP703", "TP705"), -16.9, 80.9)
    + [("TP303", -6.0, 98.5, 0.0)]
    + tp_row(("TP605", "TP606"), -28.0, 26.0)
)


def rest():
    """The edge parts, the support parts and the test pads, as (ref, x, z, rotation)."""
    return REST_EDGE + REST_SUPPORT + REST_TEST_PADS
