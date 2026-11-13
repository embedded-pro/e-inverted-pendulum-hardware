"""Part helpers: resolve passives from bom/passives.json and active parts from bom/parts.csv."""

import csv
import json
import pathlib

from schematic import Part

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


def R(sheet, value, a, b, dnp=False, ref=None, purpose="", package="0603"):
    entry = _passive(f"R_{value}_{package}")
    return sheet.add(Part(ref or sheet.next_ref("R"), "Device:R", value, {"1": a, "2": b},
                          footprint=FOOTPRINT[f"R{package}"], lcsc=entry["lcsc"], mpn=entry["mpn"], dnp=dnp,
                          fields={"Purpose": purpose} if purpose else None))


def C(sheet, key, a, b, dnp=False, ref=None, purpose=""):
    entry = _passive(f"C_{key}")
    package = key.split("_")[1]
    value = key.split("_")[0] + "F"
    return sheet.add(Part(ref or sheet.next_ref("C"), "Device:C", f"{value} {key.split('_')[2]}", {"1": a, "2": b},
                          footprint=FOOTPRINT[f"C{package}"], lcsc=entry["lcsc"], mpn=entry["mpn"], dnp=dnp,
                          fields={"Purpose": purpose} if purpose else None))


def active(sheet, mpn, lib_id, nets, footprint, prefix, value=None, ref=None, dnp=False, purpose=""):
    row = ACTIVE[mpn]
    return sheet.add(Part(ref or sheet.next_ref(prefix), lib_id, value or mpn, nets, footprint=footprint,
                          lcsc=row["lcsc"], mpn=row["mpn"], dnp=dnp,
                          fields={"Purpose": purpose} if purpose else None))


def flag(sheet, net):
    return sheet.add(Part(f"#FLG{sheet.index}{len([p for p in sheet.parts if p.ref.startswith('#FLG')]) + 1:02d}",
                          "power:PWR_FLAG", "PWR_FLAG", {"1": net}))


def nobom(sheet, prefix, lib_id, value, nets, footprint, purpose=""):
    return sheet.add(Part(sheet.next_ref(prefix), lib_id, value, nets, footprint=footprint, in_bom=False,
                          fields={"Purpose": purpose} if purpose else None))
