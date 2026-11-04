"""Read component values from the KiCad schematic (the single source of truth).

values()[ref] -> {"value": float, "raw": str, "dnp": bool, "purpose": str}
PROPOSED holds candidate changes ({ref: value}); get() applies them on top of the schematic.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kicad" / "gen"))
from sexpr import find, find_all, parse  # noqa: E402

PROPOSED = {}
SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "": 1.0}


def parse_value(text):
    token = text.strip().split()[0] if text.strip() else ""
    match = re.match(r"^(\d+(?:\.\d+)?)([pnuµmkKM]?)(\d*)", token)
    if not match:
        return None
    number, prefix, tail = match.groups()
    if tail:
        number = f"{number}.{tail}"
    return float(number) * SI[prefix]


def values(directory=ROOT / "kicad"):
    out = {}
    for path in sorted(directory.glob("*.kicad_sch")):
        tree = parse(path.read_text(encoding="utf-8"))
        for symbol in find_all(tree, "symbol"):
            if find(symbol, "lib_id") is None:
                continue
            props = {str(p[1]): str(p[2]) for p in find_all(symbol, "property")}
            ref = props.get("Reference", "")
            if not ref or ref.startswith("#"):
                continue
            dnp = find(symbol, "dnp")
            out[ref] = {"value": parse_value(props.get("Value", "")), "raw": props.get("Value", ""),
                        "dnp": bool(dnp) and str(dnp[1]) == "yes", "purpose": props.get("Purpose", "")}
    return out


_cache = None


def get(ref):
    global _cache
    if ref in PROPOSED:
        return PROPOSED[ref]
    if _cache is None:
        _cache = values()
    entry = _cache[ref]
    if entry["dnp"]:
        raise ValueError(f"{ref} is DNP")
    return entry["value"]
