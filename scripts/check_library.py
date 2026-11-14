#!/usr/bin/env python3
"""Check every placed symbol against its footprint: pin numbers <-> pad numbers.

For each component in the exported netlist, the symbol's pin numbers must all exist as footprint
pads, and every numbered copper pad must have a symbol pin (unnumbered pads are mechanical).

Usage: check_library.py [hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_sch]
"""

import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "schgen"))
from sexpr import find, find_all, parse  # noqa: E402

SYSTEM_FP = pathlib.Path("/usr/share/kicad/footprints")
PROJECT_FP = ROOT / "hardware" / "e-inverted-pendulum" / "e-inverted-pendulum.pretty"


def pads(footprint):
    library, name = footprint.split(":", 1)
    path = (PROJECT_FP if library == "e-inverted-pendulum" else SYSTEM_FP / f"{library}.pretty") / f"{name}.kicad_mod"
    numbers = set()
    for match in re.finditer(r'\(pad "([^"]*)" (\w+)', path.read_text(encoding="utf-8")):
        if match.group(1) and match.group(2) != "np_thru_hole":
            numbers.add(match.group(1))
    return numbers


def main():
    schematic = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "hardware" / "e-inverted-pendulum" / "e-inverted-pendulum.kicad_sch"
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "net.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(out), str(schematic)],
                       check=True, capture_output=True)
        tree = parse(out.read_text(encoding="utf-8"))
    libpins = {}
    for libpart in find_all(find(tree, "libparts"), "libpart"):
        key = (str(find(libpart, "lib")[1]), str(find(libpart, "part")[1]))
        pins_node = find(libpart, "pins")
        libpins[key] = {str(find(p, "num")[1]) for p in find_all(pins_node, "pin")} if pins_node else set()
    errors, checked = [], 0
    for comp in find_all(find(tree, "components"), "comp"):
        ref = str(find(comp, "ref")[1])
        footprint_node = find(comp, "footprint")
        if not footprint_node:
            continue
        source = find(comp, "libsource")
        key = (str(find(source, "lib")[1]), str(find(source, "part")[1]))
        symbol_pins = libpins.get(key, set())
        footprint_pads = pads(str(footprint_node[1]))
        checked += 1
        if symbol_pins - footprint_pads:
            errors.append(f"{ref} ({key[1]} -> {footprint_node[1]}): pins without pads {sorted(symbol_pins - footprint_pads)}")
        if footprint_pads - symbol_pins:
            errors.append(f"{ref} ({key[1]} -> {footprint_node[1]}): pads without pins {sorted(footprint_pads - symbol_pins)}")
    print(f"{checked} symbol/footprint pairs checked")
    for error in errors:
        print("ERROR", error)
    print("PASS" if not errors else f"FAIL ({len(errors)} errors)")
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
