#!/usr/bin/env python3
"""Export the netlist and compare it with the generator's intended connectivity (scripts/schgen/expected.json).

Ported from embedded-pro/e-psu-hardware. Every connection the sheet descriptions make is recorded by sch.py; this
checks that KiCad sees exactly those nets, under the same names, with no extra pins.

Usage: python3 scripts/schgen/check.py
"""

import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from check_equivalence import SCHEMATIC, read  # noqa: E402


def compare(expected, nets):
    node_net = {node: name for name, nodes in nets.items() for node in nodes}
    problems = []
    for name, nodes in sorted(expected.items()):
        got = {node_net.get(node) for node in nodes}
        if None in got:
            problems.append(f"{name}: pins missing from the netlist {sorted(n for n in nodes if n not in node_net)}")
            got.discard(None)
        if len(got) > 1:
            problems.append(f"{name}: split across {sorted(got)}")
        for kicad_name in got:
            if kicad_name != name:
                problems.append(f"{name}: KiCad names it {kicad_name}")
            extra = {n for n in nets[kicad_name] - nodes if not n[0].startswith("#")}
            if extra:
                problems.append(f"{name}: unexpected pins {sorted(extra)}")
    return problems


def main():
    expected = {k: {tuple(n) for n in v} for k, v in json.loads((HERE / "expected.json").read_text()).items()}
    with tempfile.TemporaryDirectory() as tmp:
        out = pathlib.Path(tmp) / "check.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out),
                        str(SCHEMATIC)], check=True, capture_output=True)
        _, nets = read(out)
    problems = compare(expected, nets)
    print("\n".join(problems) if problems else f"netlist matches intent ({len(expected)} nets)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
