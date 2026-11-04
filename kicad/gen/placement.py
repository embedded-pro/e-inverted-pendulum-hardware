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

ANTENNA_FEED = (-29.0, 108.85)
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

MCU = (-27.0, 95.0)
RF1_EDGE_Z = MCU[1] + 4.35
MLPF_IN_Z = RF1_EDGE_Z + 1.5

ANCHORS = {
    # ref: (x, z, rotation in degrees, why)
    "AE401": (_FX, _FZ, 0, "SWRA117D IFA, top-left corner, 1.65 mm from the side edge (docs/rf.md)"),
    "U301": (MCU[0], MCU[1], 180, "STM32WB55: rotated so RF1 (pin 31) faces the antenna; HSE at the top-left corner"),
    "FL401": (MCU[0] - 2.0 + 0.25, MLPF_IN_Z + 0.587, 0, "MLPF IN 1.5 mm from the RF1 pad, OUT toward the feed (DS12804 Fig. 13)"),
    "Y301": (-34.3, 98.3, 0, "HSE 32 MHz at OSC_IN/OSC_OUT (pins 35/34, top-left corner after rotation)"),
    "J401": (-23.0, 104.5, 0, "U.FL conducted test port (DNP), beside the RF_50 line"),
    "U702": (-10.0, 87.0, 0, "W25Q16 flash on SPI1, next to the MCU's SPI1 pins"),
    "J301": (22.0, 104.0, 0, "STDC14 debug header, away from the antenna"),
    "SW301": (-14.0, 110.0, 0, "BOOT0 button at the top edge"),
    "D801": (-3.0, 111.5, 0, "green LED at the top edge"),
    "D802": (2.0, 111.5, 0, "red LED at the top edge"),
    "SW801": (22.0, 90.0, 0, "user button"),
    "BZ801": (34.0, 88.0, 0, "buzzer, right edge of the upper band"),
    "J801": (39.0, 98.5, 90, "Qwiic (I2C3), entry from the right edge"),
    "U701": (0.0, 31.0, 0, "MPU-6500 on the centreline, 31 mm above the axle, >= 15 mm from switch nodes"),
    "U501": (0.0, 6.0, 90, "DRV8711: gate-drive side (pins 20-38) up, bridge A pins on the left, bridge B on the right"),
    "Q501": (-15.5, 14.0, 90, "bridge A1 (MOT_L_P)"),
    "Q502": (-9.0, 14.0, 90, "bridge A2 (MOT_L_N)"),
    "Q503": (9.0, 14.0, 90, "bridge B1 (MOT_R_P)"),
    "Q504": (15.5, 14.0, 90, "bridge B2 (MOT_R_N)"),
    "R509": (-12.0, 7.0, 0, "Rsense A between its two LS sources"),
    "R512": (12.0, 7.0, 0, "Rsense B between its two LS sources"),
    "C507": (0.0, 16.0, 0, "220 uF VM bulk, centred between the bridges"),
    "D501": (-21.5, 13.0, 90, "SS34 clamp MOT_L_P"),
    "D502": (-25.5, 6.0, 90, "SS34 clamp MOT_L_N"),
    "D503": (21.5, 13.0, 90, "SS34 clamp MOT_R_P"),
    "D504": (25.5, 6.0, 90, "SS34 clamp MOT_R_N"),
    "J101": (-8.0, -11.0, 0, "XT30 battery socket at the bottom edge"),
    "SW101": (3.0, -11.0, 0, "power switch at the bottom edge"),
    "F101": (-12.5, -4.0, 0, "battery fuse right after the XT30"),
    "Q101": (-3.0, -3.5, 0, "AO4805 back-to-back power switch"),
    "D102": (6.5, -4.0, 0, "SMBJ15A TVS after the power switch"),
    "J601": (-24.0, -5.3, 0, "left motor (XH), cable from below"),
    "J603": (21.5, -5.3, 0, "right motor (XH), cable from below"),
    "J602": (-39.5, -8.15, 0, "left encoder (PH 5-pin), cable from below"),
    "J604": (31.5, -8.15, 0, "right encoder (PH 5-pin), cable from below"),
    "U601": (-35.5, -3.5, 90, "left encoder ESD at the connector (pass-through)"),
    "U603": (35.5, -3.5, 90, "right encoder ESD at the connector (pass-through)"),
    "U602": (-35.5, 5.0, 0, "left encoder Schmitt buffer after the RC filters"),
    "U604": (35.5, 5.0, 0, "right encoder Schmitt buffer after the RC filters"),
    "U201": (14.0, 26.0, 0, "TPS62933F buck, right of the IMU, >= 15 mm from it"),
    "L201": (18.5, 26.0, 0, "buck inductor at SW"),
}
