#!/usr/bin/env python3
"""Generate the project symbol library hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_sym.

Pin tables are transcribed from the vendor datasheets named in each entry. The file is written
in a format KiCad parses and then normalised with `kicad-cli sym upgrade`.
"""

import pathlib
import subprocess

from sexpr import Str, Sym, dump

LIB = (pathlib.Path(__file__).resolve().parents[2] / "hardware" / "e-inverted-pendulum"
       / "e-inverted-pendulum.kicad_sym")
FONT = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
PIN_LENGTH = 2.54
PITCH = 2.54

SYMBOLS = {
    "DRV8711": {
        "reference": "U",
        "footprint": "Package_SO:HTSSOP-38-1EP_4.4x9.7mm_P0.5mm_EP2.74x4.75mm_ThermalVias",
        "datasheet": "https://www.ti.com/lit/ds/symlink/drv8711.pdf",
        "description": "Stepper/dual brushed pre-driver with SPI, 8-52 V, external N-FETs (TI SLVSC40, pin table p.3-4)",
        "left": [
            ("8", "SLEEPn", "input"), ("9", "RESET", "input"), ("16", "SCS", "input"), ("14", "SCLK", "input"),
            ("15", "SDATI", "input"), ("17", "SDATO", "open_collector"), None,
            ("10", "STEP/AIN1", "input"), ("11", "DIR/AIN2", "input"), ("12", "BIN1", "input"), ("13", "BIN2", "input"),
            None, ("18", "FAULTn", "open_collector"), ("19", "STALLn/BEMFVn", "open_collector"),
            ("20", "BEMF", "output"), None, ("6", "V5", "power_out"), ("7", "VINT", "power_out"), None,
            ("5", "GND", "power_in"), ("29", "GND", "power_in"), ("38", "GND", "power_in"), ("39", "PAD", "power_in"),
        ],
        "right": [
            ("4", "VM", "power_in"), ("3", "VCP", "passive"), ("1", "CP1", "passive"), ("2", "CP2", "passive"), None,
            ("36", "A1HS", "output"), ("37", "AOUT1", "passive"), ("35", "A1LS", "output"),
            ("31", "A2HS", "output"), ("30", "AOUT2", "passive"), ("32", "A2LS", "output"),
            ("34", "AISENP", "passive"), ("33", "AISENN", "passive"), None,
            ("27", "B1HS", "output"), ("28", "BOUT1", "passive"), ("26", "B1LS", "output"),
            ("22", "B2HS", "output"), ("21", "BOUT2", "passive"), ("23", "B2LS", "output"),
            ("25", "BISENP", "passive"), ("24", "BISENN", "passive"),
        ],
    },
    "MPU-6500": {
        "reference": "U",
        "footprint": "Sensor_Motion:InvenSense_QFN-24_3x3mm_P0.4mm",
        "datasheet": "https://invensense.tdk.com/wp-content/uploads/2020/06/PS-MPU-6500A-01-v1.3.pdf",
        "description": "6-axis gyro + accelerometer, SPI/I2C, QFN-24 3x3 (PS-MPU-6500A-01 rev 1.1, Table 10 and Fig. 3 p.19)",
        "left": [
            ("13", "VDD", "power_in"), ("8", "VDDIO", "power_in"), ("10", "REGOUT", "passive"), None,
            ("22", "nCS", "input"), ("23", "SCL/SCLK", "input"), ("24", "SDA/SDI", "bidirectional"),
            ("9", "AD0/SDO", "bidirectional"), None, ("11", "FSYNC", "input"), ("12", "INT", "output"), None,
            ("18", "GND", "power_in"), ("20", "RESV_GND", "passive"),
        ],
        "right": [
            ("7", "AUX_CL", "bidirectional"), ("21", "AUX_DA", "bidirectional"), ("19", "RESV", "no_connect"), None,
            ("1", "NC", "no_connect"), ("2", "NC", "no_connect"), ("3", "NC", "no_connect"), ("4", "NC", "no_connect"),
            ("5", "NC", "no_connect"), ("6", "NC", "no_connect"), ("14", "NC", "no_connect"), ("15", "NC", "no_connect"),
            ("16", "NC", "no_connect"), ("17", "NC", "no_connect"),
        ],
    },
    "MLPF-WB55-01E3": {
        "reference": "FL",
        "footprint": "e-inverted-pendulum:ST_MLPF-WB55-01E3",
        "datasheet": "https://www.st.com/resource/en/datasheet/mlpf-wb55-01e3.pdf",
        "description": "ST integrated 50 ohm match + low-pass filter for STM32WB55 QFN (DS12804 Rev 2, Table 6)",
        "left": [("A3", "IN", "passive"), None, ("B3", "GND1", "passive"), ("B2", "GND2", "passive")],
        "right": [("A1", "OUT", "passive"), None, ("B1", "GND3", "passive"), ("A2", "GND4", "passive")],
    },
    "ST25DV04KC-IE8S3": {
        "reference": "U",
        "footprint": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "datasheet": "https://www.st.com/resource/en/datasheet/st25dv04kc.pdf",
        "description": "Dynamic NFC/RFID tag, NFC Forum Type 5 (ISO 15693), I2C, 4 Kbit, open-drain GPO, SO8N "
                       "(DS13519 Rev 6, Table 1 and Fig. 2)",
        "left": [("8", "VCC", "power_in"), ("1", "V_EH", "power_out"), None, ("2", "AC0", "passive"),
                 ("3", "AC1", "passive"), None, ("4", "VSS", "power_in")],
        "right": [("5", "SDA", "bidirectional"), ("6", "SCL", "input"), None, ("7", "GPO", "open_collector")],
    },
    "NFC_Coil": {
        "reference": "AE",
        "footprint": "e-inverted-pendulum:NFC_Coil_25x21mm",
        "datasheet": "",
        "description": "13.56 MHz printed loop antenna for the ST25DV (scripts/nfc_coil.py, docs/nfc.md)",
        "left": [("1", "A", "passive")],
        "right": [("2", "B", "passive")],
    },
}


def _pin(number, name, kind, x, y, angle):
    return [Sym("pin"), Sym(kind), Sym("line"), [Sym("at"), x, y, angle], [Sym("length"), PIN_LENGTH],
            [Sym("name"), Str(name), FONT], [Sym("number"), Str(number), FONT]]


def _property(key, value, x, y, hide=False):
    node = [Sym("property"), Str(key), Str(value), [Sym("at"), x, y, 0], FONT]
    if hide:
        node[-1] = FONT + [[Sym("hide"), True]]
    return node


def symbol(name, spec):
    rows = max(len(spec["left"]), len(spec["right"]))
    longest = max(len(p[1]) for p in spec["left"] + spec["right"] if p)
    half_width = round((longest * 1.27 * 2 + 5.08) / PITCH) * PITCH / 2 + PITCH
    top = (rows - 1) * PITCH / 2
    top = round(top / PITCH) * PITCH
    pins = []
    for side, x, angle in (("left", -half_width - PIN_LENGTH, 0), ("right", half_width + PIN_LENGTH, 180)):
        for i, pin in enumerate(spec[side]):
            if pin:
                pins.append(_pin(pin[0], pin[1], pin[2], x, top - i * PITCH, angle))
    height = top + PITCH
    bottom = top - rows * PITCH
    body = [Sym("rectangle"), [Sym("start"), -half_width, height], [Sym("end"), half_width, bottom],
            [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
            [Sym("fill"), [Sym("type"), Sym("background")]]]
    return [Sym("symbol"), Str(name), [Sym("pin_names"), [Sym("offset"), 1.016]],
            [Sym("exclude_from_sim"), False], [Sym("in_bom"), True], [Sym("on_board"), True],
            _property("Reference", spec["reference"], -half_width, height + 1.27),
            _property("Value", name, -half_width, bottom - 1.27),
            _property("Footprint", spec["footprint"], 0, 0, hide=True),
            _property("Datasheet", spec["datasheet"], 0, 0, hide=True),
            _property("Description", spec["description"], 0, 0, hide=True),
            [Sym("symbol"), Str(f"{name}_0_1"), body],
            [Sym("symbol"), Str(f"{name}_1_1")] + pins,
            [Sym("embedded_fonts"), False]]


def main():
    LIB.parent.mkdir(parents=True, exist_ok=True)
    tree = [Sym("kicad_symbol_lib"), [Sym("version"), 20251024], [Sym("generator"), Str("kicad_symbol_editor")],
            [Sym("generator_version"), Str("10.0")]] + [symbol(n, s) for n, s in SYMBOLS.items()]
    LIB.write_text(dump(tree) + "\n", encoding="utf-8")
    subprocess.run(["kicad-cli", "sym", "upgrade", "--force", str(LIB)], check=True, capture_output=True)
    print(f"wrote {len(SYMBOLS)} symbols to {LIB}")


if __name__ == "__main__":
    main()
