#!/usr/bin/env python3
"""Routing passes 3 and 4: the connections route_simple could not make, with bends around parts and vias where needed
(D-057, D-058).

    python3 scripts/pcb/route_maze.py --apply --max-length 8    # pass 3: the short ones (D-057)
    python3 scripts/pcb/route_maze.py --apply                   # pass 4: everything left (D-058)

Each net's islands are joined closest-first (route_simple.Islands, so no loop is closed), each connection by maze.Router
on F.Cu and B.Cu: 45-degree geometry, horizontal-preferred F.Cu and vertical-preferred B.Cu, at most two vias (0.3 / 0.6
mm, or 0.2 / 0.45 mm where that does not fit), every segment and via checked exactly before it is added.
  - Widths: the class width (docs/power-map.md), narrowed only to a narrower pad, never below 0.15 mm (route_simple.
    link_width); a supply that finds no path at 0.5 mm tries 0.3 mm (still above IPC-2221's 0.12 mm for 0.5 A).
  - No jogs: a route with a segment under 0.25 mm between parallel runs is refused (pcb-design-rules gate).
  - Left alone: PWR_BUS (its pours, power_pours.py, D-056), the crystal nets (at the pins, no vias: the power map), and
    GND, except a ground pad still off the plane, which is joined to the nearest grounded copper. The vendor copies'
    own connections are first closed from their references (vendor_gaps.py, D-055); what that leaves (ST's VDD pins,
    which ST joins through its own planes) is routed here like any other.
  - Order: pass 3 shortest first, with vias expensive (F.Cu around a part first); pass 4 by priority (the encoders, kept
    away from the motor phases; VBAT_SENSE; the DRV8711 control lines; the SPI buses; I2C3; SWD / VCP; the supplies;
    the rest), shortest first within each.
A connection that cannot be made is reported with its reason and left for the owner. Re-running is a no-op once nothing
routable is left. The zones are refilled. Nothing is locked (D-045).
"""

import argparse
import pathlib
import subprocess
import sys
import time
from collections import defaultdict

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import maze as M  # noqa: E402
import route_simple as RS  # noqa: E402

SKIP_CLASSES = {"PWR_BUS", "CRYSTAL"}
# Supplies that find no path at the class width (0.5 mm) try this: they carry at most 0.6 A (+5V), and IPC-2221 asks
# 0.12 mm for 0.5 A on 1 oz outer copper (docs/power-map.md).
NARROW = {"SUPPLY"}
NARROW_WIDTH = 0.3
GND = "GND"
GND_REACH = 8.0
SHORT_VIA_COST = 8.0
LONG_VIA_COST = 3.0
PRIORITY = (("ENC_",), ("VBAT_SENSE",), ("DRV_",), ("SPI1", "SPI2", "IMU_", "FLASH_"), ("QWIIC_", "I2C"),
            ("SWD", "SWCLK", "SWDIO", "VCP_", "NRST", "BOOT0"), ("+3V3", "+5V", "ENC_VCC", "VDDA", "NFC_VCC"))


def priority(name):
    return next((k for k, keys in enumerate(PRIORITY) if any(name.startswith(key) for key in keys)), len(PRIORITY))


def candidates(board, islands, found, plane, max_length):
    """(length, net name, a, b) between terminals of one net in different islands, closest first."""
    pairs = []
    for net, terms in found.items():
        if not terms:
            continue
        name = RS.short(terms[0].item.GetNetname())
        if terms[0].item.GetNetClassName() in SKIP_CLASSES:
            continue
        for i, a in enumerate(terms):
            for b in terms[i + 1:]:
                if islands.find(RS.uid(a.item)) == islands.find(RS.uid(b.item)):
                    continue
                if a.kind == "end" and b.kind == "end" and RS.uid(a.track) == RS.uid(b.track):
                    continue
                length = (b.at - a.at).EuclideanNorm() / 1e6
                if name == GND:
                    grounded = [islands.find(RS.uid(t.item)) == plane for t in (a, b)]
                    if grounded.count(True) != 1 or length > GND_REACH:
                        continue
                if max_length is not None and length > max_length:
                    continue
                pairs.append((length, name, a, b))
    if max_length is not None:
        pairs.sort(key=lambda p: (p[0], p[1], p[2].name(), p[3].name()))
    else:
        pairs.sort(key=lambda p: (priority(p[1]), p[0], p[1], p[2].name(), p[3].name()))
    return pairs


def stage(max_length, limit):
    board = pcbnew.LoadBoard(str(B.BOARD))
    world = RS.World(board)
    islands = RS.Islands(board)
    plane = islands.find(RS.uid(world.plane))
    router = M.Router(board, world, islands)
    pairs = candidates(board, islands, RS.terminals(board), plane, max_length)
    via_cost = SHORT_VIA_COST if max_length is not None else LONG_VIA_COST
    routed, failed = [], []
    tried = 0
    for length, name, a, b in pairs:
        if islands.find(RS.uid(a.item)) == islands.find(RS.uid(b.item)):
            continue
        if limit is not None and tried >= limit:
            break
        tried += 1
        width = RS.link_width(a.item.GetNetClassName(), a, b)
        started = time.time()
        result, why = router.route(a, b, width, allow_vias=True, via_cost=via_cost)
        if result is None and a.item.GetNetClassName() in NARROW and width > M.mm(NARROW_WIDTH):
            width = M.mm(NARROW_WIDTH)
            result, why = router.route(a, b, width, allow_vias=True, via_cost=via_cost)
        spent = time.time() - started
        if result is None:
            failed.append((name, a.name(), b.name(), length, why, (RS.uid(a.item), RS.uid(b.item))))
            print(f"... {name} {a.name()} -> {b.name()}: {why} ({spent:.1f} s)", flush=True)
            continue
        tracks, vias = result
        if name == GND:
            for item in tracks + vias:
                islands.union(RS.uid(item), plane)
        routed_length = sum(t.GetLength() for t in tracks) / 1e6
        layers = sorted({board.GetLayerName(t.GetLayer()) for t in tracks})
        routed.append((name, a.name(), b.name(), length, routed_length, len(vias), "+".join(layers), width / 1e6, spent))
        print(f"... {name} {a.name()} -> {b.name()}: routed, {len(vias)} via(s) ({spent:.1f} s)", flush=True)
    failed = [f for f in failed if islands.find(f[-1][0]) != islands.find(f[-1][1])]
    if not routed:
        print("nothing routable left: nothing to do")
        for name, a, b, length, why, _ in failed:
            print(f"open  {name:14} {a:>22} -> {b:<22} {length:6.2f} mm  {why}")
        sys.exit(3)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for name, a, b, length, routed_length, vias, layers, width, spent in routed:
        detour = routed_length / length if length else 0
        flag = "  DETOUR" if detour > 1.6 and length > 2 else ""
        print(f"route {name:14} {a:>22} -> {b:<22} {width:.2f} mm  {length:6.2f} -> {routed_length:6.2f} mm  "
              f"{vias} via(s)  {layers}  {spent:5.1f} s{flag}")
    for name, a, b, length, why, _ in failed:
        print(f"open  {name:14} {a:>22} -> {b:<22} {length:6.2f} mm  {why}")
    print(f"{len(routed)} connections routed ({sum(r[5] for r in routed)} vias), {len(failed)} attempts open "
          f"(some joined later by another pair)")
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="route what is left (one shot)")
    parser.add_argument("--max-length", type=float, help="only connections up to this length (mm), shortest first")
    parser.add_argument("--limit", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.max_length, args.limit)
        return
    if not args.apply:
        parser.error("nothing to do without --apply")
    project = B.PROJECT.read_bytes()
    command = [sys.executable, __file__, "--pcbnew-stage"]
    if args.max_length is not None:
        command += ["--max-length", str(args.max_length)]
    if args.limit is not None:
        command += ["--limit", str(args.limit)]
    result = subprocess.run(command)
    B.PROJECT.write_bytes(project)
    if result.returncode == 3:
        return
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
