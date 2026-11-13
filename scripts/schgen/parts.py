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
