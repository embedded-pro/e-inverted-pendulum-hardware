#!/usr/bin/env python3
"""Check the exported KiCad netlist against the pin map, the rail plan and the BOM rules.

Checks:
  1. every MCU (U301) pin's net equals pin-data/pinmap.csv (GPIOs) or the rail plan (supplies);
  2. rail pins of each IC sit on the intended rail;
  3. no net has a single connection (except deliberate test points);
  4. every BOM part (in_bom, not DNP) has a footprint, an LCSC number and an MPN;
  5. every footprint referenced exists in the KiCad or project libraries.

Usage: check_netlist.py [hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_sch]
"""

import csv
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "schgen"))
from sexpr import find, find_all, parse  # noqa: E402

SYSTEM_FP = pathlib.Path("/usr/share/kicad/footprints")
PROJECT_FP = ROOT / "hardware" / "e-inverted-pendulum" / "e-inverted-pendulum.pretty"
MCU = "U301"
RAILS = {
    MCU: {"1": "+3V3", "13": "VDDA", "14": "VDDA", "30": "+3V3", "33": "+3V3", "44": "+3V3", "45": "+3V3",
          "55": "+3V3", "68": "+3V3", "69": "GND", "32": "GND", "42": "GND"},
    "U501": {"4": "VBAT", "5": "GND", "29": "GND", "38": "GND", "39": "GND"},
    "U201": {"3": "VBAT", "4": "GND"},
    "U202": {"1": "+5V", "2": "GND", "5": "+3V3"},
    "U701": {"13": "+3V3", "8": "+3V3", "18": "GND"},
}


def netlist(schematic):
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "net.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", str(out), str(schematic)],
                       check=True, capture_output=True)
        return parse(out.read_text(encoding="utf-8"))


def main():
    schematic = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "hardware" / "e-inverted-pendulum" / "e-inverted-pendulum.kicad_sch"
    tree = netlist(schematic)
    errors = []
    pin_net, net_nodes = {}, {}
    for net in find_all(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1]).split("/")[-1]
        nodes = [(str(find(n, "ref")[1]), str(find(n, "pin")[1])) for n in find_all(net, "node")]
        net_nodes[name] = nodes
        for node in nodes:
            pin_net[node] = name

    with open(ROOT / "pin-data" / "pinmap.csv", encoding="utf-8") as handle:
        pinmap = {row["pin"]: row["net"] for row in csv.DictReader(handle)}
    with open(ROOT / "pin-data" / "stm32wb55rgvx_vfqfpn68.csv", encoding="utf-8") as handle:
        number_of = {row["name"]: row["number"] for row in csv.DictReader(handle)}
    for pin, net in pinmap.items():
        actual = pin_net.get((MCU, number_of[pin]))
        if actual != net:
            errors.append(f"{MCU} {pin} (pin {number_of[pin]}) is on {actual}, pinmap says {net}")

    for ref, rails in RAILS.items():
        for pin, rail in rails.items():
            if pin_net.get((ref, pin)) != rail:
                errors.append(f"{ref} pin {pin} is on {pin_net.get((ref, pin))}, expected {rail}")

    for name, nodes in net_nodes.items():
        if len(nodes) == 1 and not name.startswith("unconnected-") and not nodes[0][0].startswith("TP"):
            errors.append(f"net {name} has a single connection {nodes[0]}")

    components = find_all(find(tree, "components"), "comp")
    fields_missing, footprints = [], set()
    for comp in components:
        ref = str(find(comp, "ref")[1])
        fields = {str(f[1][1]): str(f[2]) if len(f) > 2 else "" for f in find_all(find(comp, "fields") or [], "field")}
        props = {str(find(p, "name")[1]) for p in find_all(comp, "property")}
        footprint = str(find(comp, "footprint")[1]) if find(comp, "footprint") else ""
        excluded = "exclude_from_bom" in props or "dnp" in props
        if footprint:
            footprints.add(footprint)
        if excluded:
            continue
        missing = [k for k in ("LCSC", "MPN") if not fields.get(k)]
        if not footprint:
            missing.append("Footprint")
        if missing:
            fields_missing.append(f"{ref} missing {', '.join(missing)}")
    errors += fields_missing

    for footprint in sorted(footprints):
        library, name = footprint.split(":", 1)
        path = (PROJECT_FP if library == "e-inverted-pendulum" else SYSTEM_FP / f"{library}.pretty") / f"{name}.kicad_mod"
        if not path.exists():
            errors.append(f"footprint {footprint} not found")

    print(f"{len(components)} components, {len(net_nodes)} nets, {len(footprints)} distinct footprints")
    for error in errors:
        print("ERROR", error)
    print("PASS" if not errors else f"FAIL ({len(errors)} errors)")
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
