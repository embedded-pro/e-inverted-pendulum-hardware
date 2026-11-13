"""Board geometry and placement for kicad/gen/board.py, in mechanical coordinates (docs/mechanical.md).

x: across the plate, 0 on the vertical centreline. z: up the plate, 0 on the wheel axle at the centre of the 25 mm
bracket strip (D-026). mm, front (component side) view. Rotation in degrees, KiCad convention.
Everything here is a draft until the owner signs off gate A (docs/layout.md); approved anchors are then locked on the
board and never moved again (power-pcb-layout s1). Floorplan per the owner: D-025, D-026, D-029.
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
    {"ref": "MC1", "value": "battery cradle", "footprint": _M3, "x": -30.0, "z": 50.0},
    {"ref": "MC2", "value": "battery cradle", "footprint": _M3, "x": 30.0, "z": 50.0},
    {"ref": "MC3", "value": "battery cradle", "footprint": _M3, "x": -30.0, "z": 72.0},
    {"ref": "MC4", "value": "battery cradle", "footprint": _M3, "x": 30.0, "z": 72.0},
    {"ref": "MH1", "value": "bumper", "footprint": _M3, "x": -38.0, "z": 92.0},
    {"ref": "MH2", "value": "bumper (nylon)", "footprint": _M3, "x": 39.5, "z": 80.5},
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

MCU = (2.0, 97.5)
RF1_EDGE_Z = MCU[1] + 4.35
MLPF_IN_Z = RF1_EDGE_Z + 1.5

ANCHORS = {
    "AE401": (_FX, _FZ, 0, "SWRA117D IFA at the top edge, above RF1 (D-029, docs/rf.md)"),
    "U301": (MCU[0], MCU[1], 180, "STM32WB55 at the top centre, rotated so RF1 (pin 31) faces the antenna"),
    "FL401": (MCU[0] - 2.0 + 0.25, MLPF_IN_Z + 0.587, 0, "MLPF IN 1.5 mm from the RF1 pad (DS12804 Fig. 13)"),
    "Y301": (-4.5, 101.5, 0, "HSE 32 MHz at OSC_IN/OSC_OUT (pins 35/34)"),
    "J401": (-5.5, 106.8, 0, "U.FL conducted test port (DNP), beside the RF_50 line"),
    "U701": (-12.0, 94.0, 0, "MPU-6500 beside the MCU's SPI2 pins (left side after rotation)"),
    "U803": (11.0, 101.0, 180, "ST25DV04KC: AC0/AC1 toward the coil, I2C and GPO toward the MCU"),
    "U802": (11.0, 89.0, 180, "M24C64 EEPROM on I2C3"),
    "AE801": (COIL_CENTRE[0], COIL_CENTRE[1], 0, "NFC coil 25 x 21 mm, top-right, above the battery outline"),
    "U702": (-2.0, 86.0, 0, "W25Q16 flash below the MCU's SPI1 pins"),
    "SW101": (-37.7, 103.0, 0, "power switch at the top-left (it only switches the SW_ON gate line)"),
    "D801": (-20.0, 107.5, 0, "green LED at the top"),
    "D802": (-16.0, 107.5, 0, "red LED at the top"),
    "SW301": (10.0, 78.0, 0, "BOOT0 button"),
    "SW801": (20.0, 52.0, 0, "user button"),
    "BZ801": (20.0, 66.0, 0, "buzzer"),
    "J301": (38.0, 59.0, 0, "STDC14 debug at the middle of the right edge (D-029)"),
    "J801": (39.0, 72.0, 90, "Qwiic (I2C3), entry from the right edge"),
    "U201": (-20.0, 60.0, 0, "TPS62933F buck, mid-left, far from the antenna and the IMU"),
    "L201": (-15.5, 60.0, 0, "buck inductor at SW"),
    "J101": (-37.5, 33.5, 0, "XT30 battery socket on the left edge, below the battery band (THT)"),
    "F101": (-37.0, 41.0, 0, "battery fuse after the XT30"),
    "Q101": (-29.5, 43.0, 0, "AO4805 back-to-back power switch"),
    "D102": (-20.0, 44.0, 0, "SMBJ15A TVS after the power switch"),
    "J601": (-35.5, 26.0, 270, "left MG310 (PH 6-pin), entry from the left edge, just above the strip"),
    "J602": (35.5, 15.5, 90, "right MG310 (PH 6-pin), entry from the right edge, just above the strip"),
    "U601": (-30.0, 21.0, 90, "left encoder ESD at the connector"),
    "U602": (-25.5, 21.0, 90, "left encoder Schmitt buffer"),
    "U603": (30.0, 21.0, 90, "right encoder ESD at the connector"),
    "U604": (25.5, 21.0, 90, "right encoder Schmitt buffer"),
    "U501": (0.0, 20.0, 90, "DRV8711: gate-drive pins up, bridge A on the left, bridge B on the right"),
    "R509": (-10.0, 18.0, 0, "Rsense A"),
    "R512": (10.0, 18.0, 0, "Rsense B"),
    "Q501": (-17.0, 28.0, 90, "bridge A1 (MOT_L_P)"),
    "Q502": (-10.5, 28.0, 90, "bridge A2 (MOT_L_N)"),
    "Q503": (10.5, 28.0, 90, "bridge B1 (MOT_R_P)"),
    "Q504": (17.0, 28.0, 90, "bridge B2 (MOT_R_N)"),
    "C507": (0.0, 30.5, 0, "220 uF VM bulk between the bridges"),
    "D501": (-21.0, 37.5, 0, "SS34 clamp MOT_L_P"),
    "D502": (-13.5, 37.5, 0, "SS34 clamp MOT_L_N"),
    "D503": (13.5, 37.5, 0, "SS34 clamp MOT_R_P"),
    "D504": (21.0, 37.5, 0, "SS34 clamp MOT_R_N"),
}
