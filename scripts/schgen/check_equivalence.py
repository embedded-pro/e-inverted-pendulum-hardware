#!/usr/bin/env python3
"""Prove that two schematics are the same circuit: same parts, fields and pin-to-net connectivity.

Use it after a drawing-only change (D-033): the reference is a KiCad netlist file or a git revision, whose
schematic is exported with kicad-cli. Compared: references, values, footprints, LCSC / MPN / Purpose fields, DNP and
BOM / board flags, symbol library IDs, and the partition of pins into nets, net names included (the PCB's nets and
net classes key on them).

Usage:
  python3 scripts/schgen/check_equivalence.py <reference.net | git-rev> [--allow-renames]
Exit 0 when equivalent, 1 otherwise.
"""

import argparse
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import io

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from sexpr import find, find_all, parse  # noqa: E402

PROJECT = "e-inverted-pendulum"
SCHEMATIC = ROOT / "hardware" / PROJECT / f"{PROJECT}.kicad_sch"
IGNORED_FIELDS = {"Footprint", "Datasheet", "Description"}
FLAGS = {"dnp", "exclude_from_bom", "exclude_from_board"}


def export_netlist(schematic, out):
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(schematic)],
                   check=True, capture_output=True)
    return out


def netlist_from_rev(rev, workdir):
    for folder in (f"hardware/{PROJECT}", "kicad"):
        result = subprocess.run(["git", "-C", str(ROOT), "archive", rev, folder], capture_output=True)
        if result.returncode == 0:
            with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
                archive.extractall(workdir, filter="data")
            return export_netlist(workdir / folder / f"{PROJECT}.kicad_sch", workdir / "reference.net")
    raise SystemExit(f"no schematic found at {rev}")


def read(path):
    tree = parse(pathlib.Path(path).read_text(encoding="utf-8"))
    parts = {}
    for comp in find_all(find(tree, "components"), "comp"):
        ref = str(find(comp, "ref")[1])
        fields = {}
        node = find(comp, "fields")
        for field in find_all(node, "field") if node else []:
            name = str(find(field, "name")[1])
            if name not in IGNORED_FIELDS:
                fields[name] = str(field[2]) if len(field) > 2 else ""
        flags = {str(find(p, "name")[1]) for p in find_all(comp, "property")} & FLAGS
        lib = find(comp, "libsource")
        footprint = find(comp, "footprint")
        parts[ref] = {"value": str(find(comp, "value")[1]), "footprint": str(footprint[1]) if footprint else "",
                      "fields": fields, "flags": sorted(flags),
                      "symbol": f"{find(lib, 'lib')[1]}:{find(lib, 'part')[1]}"}
    nets = {}
    for net in find_all(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1])
        nodes = frozenset((str(find(n, "ref")[1]), str(find(n, "pin")[1])) for n in find_all(net, "node"))
        nets[name] = nodes
    return parts, nets


def compare(reference, current, allow_renames=False):
    (ref_parts, ref_nets), (cur_parts, cur_nets) = reference, current
    problems, renames = [], []
    for ref in sorted(set(ref_parts) | set(cur_parts)):
        if ref not in cur_parts:
            problems.append(f"{ref}: missing")
            continue
        if ref not in ref_parts:
            problems.append(f"{ref}: added")
            continue
        for key in ("value", "footprint", "symbol", "flags", "fields"):
            if ref_parts[ref][key] != cur_parts[ref][key]:
                problems.append(f"{ref}: {key} {ref_parts[ref][key]!r} -> {cur_parts[ref][key]!r}")

    def connected(nets):
        return {name: nodes for name, nodes in nets.items() if not name.startswith("unconnected-")}

    ref_conn, cur_conn = connected(ref_nets), connected(cur_nets)
    by_nodes = {nodes: name for name, nodes in cur_conn.items()}
    matched = set()
    for name, nodes in sorted(ref_conn.items()):
        other = by_nodes.get(nodes)
        if other is None:
            node_net = {n: nm for nm, ns in cur_conn.items() for n in ns}
            split = sorted({node_net.get(n, "unconnected") for n in nodes})
            problems.append(f"net {name}: {len(nodes)} pins now on {split}")
            continue
        matched.add(other)
        if other != name:
            renames.append(f"net {name} -> {other}")
    for name in sorted(set(cur_conn) - matched):
        problems.append(f"net {name}: new connection {sorted(cur_conn[name])}")
    if not allow_renames:
        problems += renames
    return problems, renames


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("reference", help="reference netlist (.net) or git revision")
    parser.add_argument("--allow-renames", action="store_true", help="report net renames without failing")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        reference = pathlib.Path(args.reference)
        ref_net = reference if reference.suffix == ".net" and reference.exists() else netlist_from_rev(args.reference, tmp)
        cur_net = export_netlist(SCHEMATIC, tmp / "current.net")
        ref_data, cur_data = read(ref_net), read(cur_net)
    problems, renames = compare(ref_data, cur_data, args.allow_renames)
    for line in renames if args.allow_renames else []:
        print("RENAME", line)
    for line in problems:
        print("DIFF", line)
    parts, nets = len(cur_data[0]), len([n for n in cur_data[1] if not n.startswith("unconnected-")])
    print(f"{'EQUIVALENT' if not problems else 'DIFFERENT'}: {parts} parts, {nets} connected nets compared with "
          f"{args.reference}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
