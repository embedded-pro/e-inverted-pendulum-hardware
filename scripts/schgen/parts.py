"""Part helpers for the sheet descriptions: passives from bom/passives.json, active parts from bom/parts.csv.

Each helper places the symbol and labels its pins with the given nets; a later `rail`, `link` or `path` on the same
pin draws the wire instead (and fails if the nets disagree).
"""

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PASSIVES = json.loads((ROOT / "bom" / "passives.json").read_text(encoding="utf-8"))
with open(ROOT / "bom" / "parts.csv", encoding="utf-8") as handle:
    ACTIVE = {row["mpn"]: row for row in csv.DictReader(handle)}

FOOTPRINT = {
    "R0603": "Resistor_SMD:R_0603_1608Metric",
    "R0402": "Resistor_SMD:R_0402_1005Metric",
    "C0402": "Capacitor_SMD:C_0402_1005Metric",
    "C0603": "Capacitor_SMD:C_0603_1608Metric",
    "C0805": "Capacitor_SMD:C_0805_2012Metric",
}


def _passive(key):
    if key not in PASSIVES:
        raise KeyError(f"{key} missing from bom/passives.json; add it to scripts/passive_catalog.py")
    return PASSIVES[key]


def _purpose(purpose):
    return {"Purpose": purpose} if purpose else {}


def R(sh, ref, value, x, y, n1, n2, rot=0, package="0603", dnp=False, purpose=""):
    """Resistor; rot 0 is vertical with pin 1 on top, rot 90 horizontal with pin 1 on the left."""
    entry = _passive(f"R_{value}_{package}")
    p = sh.part("Device:R", ref, value, (x, y), rot, fp=FOOTPRINT[f"R{package}"], lcsc=entry["lcsc"],
                mpn=entry["mpn"], dnp=dnp, **_purpose(purpose))
    sh.net(p["1"], n1)
    sh.net(p["2"], n2)
    return p


def C(sh, ref, key, x, y, n1, n2="GND", rot=0, dnp=False, purpose=""):
    """Capacitor from its catalog key (value_package_voltage_dielectric); pin 1 on top at rot 0."""
    entry = _passive(f"C_{key}")
    value, package, voltage = key.split("_")[:3]
    p = sh.part("Device:C", ref, f"{value}F {voltage}", (x, y), rot, fp=FOOTPRINT[f"C{package}"],
                lcsc=entry["lcsc"], mpn=entry["mpn"], dnp=dnp, **_purpose(purpose))
    sh.net(p["1"], n1)
    sh.net(p["2"], n2)
    return p


def active(sh, ref, mpn, lib_id, fp, x, y, rot=0, value=None, dnp=False, purpose="", unit=1, mirror=None):
    """Part from bom/parts.csv (LCSC and MPN from the catalog); nets are added by the caller."""
    row = ACTIVE[mpn]
    return sh.part(lib_id, ref, value or mpn, (x, y), rot, unit=unit, fp=fp, lcsc=row["lcsc"], mpn=row["mpn"],
                   dnp=dnp, mirror=mirror, **_purpose(purpose))


def nobom(sh, ref, lib_id, value, fp, x, y, rot=0, purpose=""):
    """On the board but not in the BOM: printed antennas, net ties, test pads."""
    return sh.part(lib_id, ref, value, (x, y), rot, fp=fp, in_bom=False, **_purpose(purpose))


TP_PAD = {"rail": "TestPoint:TestPoint_Pad_D1.5mm", "signal": "TestPoint:TestPoint_Pad_D1.0mm"}
TP_RAILS = {"VBAT", "+5V", "+3V3", "VDDA", "ENC_VCC", "GND"}


def test_points(sh, x0, y, points, pitch=10.16):
    """A row of bring-up probe pads with their pins on `y` (D-035).

    Rails and GND get 1.5 mm pads, signals 1.0 mm. GND pads point down to their ground symbol, the others up to their
    label or power symbol. The Value is the net name: hidden here (the label shows it), printed on the PCB silkscreen.
    """
    parts = []
    for i, (ref, net) in enumerate(points):
        down = net == "GND"
        tp = sh.part("Connector:TestPoint", ref, net, (x0 + pitch * i, y), 0 if down else 180,
                     fp=TP_PAD["rail" if net in TP_RAILS else "signal"], in_bom=False, Purpose="bring-up probe point")
        tp.hide_value = True
        tp.fpos = (1.27, -3.81, "left") if down else (1.27, 3.81, "left")
        sh.net(tp["1"], net)
        parts.append(tp)
    return parts
