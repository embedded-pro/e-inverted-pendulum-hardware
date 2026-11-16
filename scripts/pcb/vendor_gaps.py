#!/usr/bin/env python3
"""Routing pass 2: the vendor copies' open ends, closed from the vendors' references (D-055).

    python3 scripts/pcb/vendor_gaps.py --apply

The three copies (MB1355 with U301, MB1163 with AE801, BOOST-DRV8711) change only with the vendor's reference in hand
(CLAUDE.md). Some of their tracks are no longer on the board: removed while parts were moved (D-047) or nudged (D-052).
This puts back what the references say, in this order:
  1. Restored as drawn: each chain of the vendor's tracks that is missing (the reference mapped onto the board as the
     pours are: rf_block.to_ours; nfc_block.to_ours + the NFC copy's offset; drv_block.to_ours + the drive's offset),
     when every end of it still lands on its net's copper (a pad of a part at the vendor's spot, a via, a track end) and
     every segment passes the board's checks (route_simple.World, tees, angles). TI's missing vias come back where they
     fit; ST's do not (the RF strip's stitching is D-049's lattice, the NFC copy's led to ST's Arduino header).
  2. Adapted: a chain with one end landing and the other at a pad that has moved goes back as drawn from the landing
     end, as far as it passes, and ends with a straight or one-bend hop to the moved pad (45-degree joins only).
  3. Re-joined: a connection of a vendor net among that copy's own parts that is still open, because a part moved off the
     vendor's spot (D-047, D-052), is routed by maze.Router at the vendor's width for that net, closest first; on F.Cu
     with no via for the crystals, the switch nodes and RF (QUIET_CLASSES), with at most two vias otherwise (ST's own
     +3V3 used vias). A crystal's two nets are re-joined together or not at all (the power map: short and symmetric).
  4. Ground: each of the copies' GND pads still off the L2 plane gets one stub and via, as route_simple does for ours.
ST's RF-strip stitching vias stay replaced by D-049's lattice and are never restored. Re-running is a no-op once nothing
is left. The zones are refilled. Nothing is locked (D-045).
"""

import argparse
import itertools
import pathlib
import subprocess
import sys
from collections import defaultdict

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import drv_block as D  # noqa: E402
import maze as M  # noqa: E402
import nfc_block as N  # noqa: E402
import pours as P  # noqa: E402
import rf_block as RF  # noqa: E402
import route_simple as RS  # noqa: E402

mm = pcbnew.FromMM
V = pcbnew.VECTOR2I
TOLERANCE = mm(0.06)
MAX_JOIN = 8.0
GND = "GND"
# Re-joined on F.Cu with no via: the crystals (the power map: at the pins, no vias), the switch nodes (small loop) and RF.
QUIET_CLASSES = {"CRYSTAL", "SWITCH", "RF"}


def references(board):
    """Per copy: (name, data, map to the board, layer of a reference track)."""
    zero = V(0, 0)
    nfc, drive = P.nfc_offset(board), P.drive_offset(board)
    return [
        ("MB1355", RF.DATA, lambda x, y: RF.to_ours(x, y) + zero, lambda t: t.get("layer", "F.Cu")),
        ("MB1163", N.DATA, lambda x, y: N.to_ours(x, y) + nfc, lambda t: t["layer"]),
        ("BOOST-DRV8711", D.DATA, lambda x, y: D.to_ours(x, y) + drive, lambda t: D.LAYERS[t["layer"]]),
    ]


def net_name(data, net):
    return RS.short(str(data["net_map"].get(net, net)))


def same_segment(track, s, e):
    a, b = track.GetStart(), track.GetEnd()
    return ((a - s).EuclideanNorm() < TOLERANCE and (b - e).EuclideanNorm() < TOLERANCE) or \
        ((a - e).EuclideanNorm() < TOLERANCE and (b - s).EuclideanNorm() < TOLERANCE)


def missing_chains(board, world):
    """The vendors' tracks not on the board, grouped into chains (segments of one net and layer sharing ends)."""
    chains = []
    for copy, data, to_board, layer_of in references(board):
        missing = []
        for t in data["tracks"]:
            s, e = to_board(*t["start"]), to_board(*t["end"])
            net, layer = net_name(data, t["net"]), board.GetLayerID(layer_of(t))
            if any(x.GetClass() == "PCB_TRACK" and x.GetLayer() == layer and RS.short(x.GetNetname()) == net
                   and same_segment(x, s, e) for x in world.tracks):
                continue
            missing.append({"net": net, "layer": layer, "start": s, "end": e, "width": mm(t["width"])})
        parent = list(range(len(missing)))

        def find(i):
            while parent[i] != i:
                i = parent[i]
            return i
        for i, j in itertools.combinations(range(len(missing)), 2):
            a, b = missing[i], missing[j]
            if a["net"] == b["net"] and a["layer"] == b["layer"] and \
                    any((p - q).EuclideanNorm() < TOLERANCE for p in (a["start"], a["end"]) for q in (b["start"], b["end"])):
                parent[find(i)] = find(j)
        groups = defaultdict(list)
        for i, segment in enumerate(missing):
            groups[find(i)].append(segment)
        chains += [(copy, segments) for segments in groups.values()]
    return chains


def landing(board, world, net, layer, point):
    """The copper a chain end lands on as the board is now: a pad (of a part at the vendor's spot), a via, a track end;
    None when nothing of its net is there."""
    for pad in world.pads:
        if RS.short(pad.GetNetname()) == net and pad.IsOnLayer(layer) and pad.HitTest(point):
            return RS.Terminal(pad, pad.GetPosition())
    for item in world.tracks:
        if RS.short(item.GetNetname()) != net:
            continue
        if item.GetClass() == "PCB_VIA" and (item.GetPosition() - point).EuclideanNorm() < TOLERANCE:
            return RS.Terminal(item, item.GetPosition())
        if item.GetClass() == "PCB_TRACK" and item.GetLayer() == layer:
            for end in (item.GetStart(), item.GetEnd()):
                if (end - point).EuclideanNorm() < TOLERANCE:
                    return RS.Terminal(item, end, track=item)
    return None


def moved_pads(board):
    """Per copy: [(pad, offset)] for its parts that are off the vendor's spot (offset = where the part is now minus
    the vendor's spot)."""
    found = []
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for copy, data, to_board, _ in references(board):
        for part in data["parts"]:
            fp = footprints.get(part["ours"])
            if fp is None:
                continue
            offset = fp.GetPosition() - to_board(*part["at"])
            if offset.EuclideanNorm() > TOLERANCE:
                found += [(pad, offset) for pad in fp.Pads()]
    return found


def walk(segments, start):
    """The chain's points in order from the end at start."""
    left = list(segments)
    points = [start]
    while left:
        here = points[-1]
        nxt = next((s for s in left if (s["start"] - here).EuclideanNorm() < TOLERANCE
                    or (s["end"] - here).EuclideanNorm() < TOLERANCE), None)
        if nxt is None:
            break
        left.remove(nxt)
        points.append(nxt["end"] if (nxt["start"] - here).EuclideanNorm() < TOLERANCE else nxt["start"])
    return points


def turn_ok(u, v):
    nu, nv = (u.x ** 2 + u.y ** 2) ** 0.5, (v.x ** 2 + v.y ** 2) ** 0.5
    return nu == 0 or nv == 0 or (u.x * v.x + u.y * v.y) / (nu * nv) >= M.COS45


def adapt_chains(board, world, islands, chains, moved):
    """Chains with one end landing and the other at a pad that moved: as drawn from the landing end, as far as it
    passes, then a straight or one-bend hop to the moved pad's centre (45-degree joins only)."""
    adapted, kept = [], []
    for copy, segments in chains:
        points = [p for s in segments for p in (s["start"], s["end"])]
        ends = [p for p in points if sum((p - q).EuclideanNorm() < TOLERANCE for q in points) == 1]
        net, layer, width = segments[0]["net"], segments[0]["layer"], min(s["width"] for s in segments)
        if len(ends) != 2 or net == GND:
            kept.append((copy, segments))
            continue
        lands = [landing(board, world, net, layer, p) for p in ends]
        if sum(t is not None for t in lands) != 1:
            kept.append((copy, segments))
            continue
        home = next(t for t in lands if t is not None)
        loose = ends[0] if lands[0] is None else ends[1]
        target = next((pad for pad, offset in moved if RS.short(pad.GetNetname()) == net and pad.IsOnLayer(layer)
                       and pad.HitTest(loose + offset)), None)
        if target is None or islands.find(RS.uid(home.item)) == islands.find(RS.uid(target)):
            kept.append((copy, segments))
            continue
        far = RS.Terminal(target, target.GetPosition())
        path = walk(segments, home.at if home.kind != "pad" else next(p for p in ends if p != loose))
        probe = RS.probe_for(board, home.item.GetNet())
        done = None
        for keep in range(len(path), 1, -1):
            body = path[:keep]
            for hop in RS.paths(body[-1], far.at):
                route = body + hop[1:]
                if len(route) > 2 and not all(turn_ok(route[k] - route[k - 1], route[k + 1] - route[k])
                                              for k in range(1, len(route) - 1)):
                    continue
                legs = [(a, b) for a, b in zip(route, route[1:]) if a != b]
                if RS.tee_problem(world, legs, layer, home.item.GetNetCode()):
                    continue
                if any(world.track_problem(a, b, layer, width, probe, (home, far), pours=False) for a, b in legs):
                    continue
                done = legs
                break
            if done:
                break
        if not done:
            kept.append((copy, segments))
            continue
        added = RS.lay(board, world, home.item.GetNet(), layer, done, width)
        for item in added + [target]:
            islands.union(RS.uid(item), RS.uid(home.item))
        adapted.append((copy, net, len(done), [home.name(), far.name()]))
    return adapted, kept


def restore_chains(board, world, islands, chains):
    """Chains whose every end lands: added as drawn when every segment passes."""
    restored, kept = [], []
    for copy, segments in chains:
        points = [p for s in segments for p in (s["start"], s["end"])]
        ends = [p for p in points if sum((p - q).EuclideanNorm() < TOLERANCE for q in points) == 1]
        net, layer = segments[0]["net"], segments[0]["layer"]
        terminals = [landing(board, world, net, layer, p) for p in ends]
        if len(ends) < 2 or any(t is None for t in terminals):
            kept.append((copy, segments))
            continue
        if len({islands.find(RS.uid(t.item)) for t in terminals}) < 2:
            continue
        probe = RS.probe_for(board, terminals[0].item.GetNet())
        legs = []
        for s in segments:
            start, end = s["start"], s["end"]
            for t in terminals:
                if (start - t.at).EuclideanNorm() < TOLERANCE and t.kind != "pad":
                    start = t.at
                if (end - t.at).EuclideanNorm() < TOLERANCE and t.kind != "pad":
                    end = t.at
            legs.append((start, end, s["width"]))
        problem = RS.tee_problem(world, [(a, b) for a, b, _ in legs], layer, terminals[0].item.GetNetCode())
        for a, b, width in legs:
            problem = problem or world.track_problem(a, b, layer, width, probe, tuple(terminals), pours=False)
        if problem:
            kept.append((copy, segments))
            continue
        added = []
        for a, b, width in legs:
            added += RS.lay(board, world, terminals[0].item.GetNet(), layer, [(a, b)], width)
        for item in added + [t.item for t in terminals[1:]]:
            islands.union(RS.uid(item), RS.uid(terminals[0].item))
        restored.append((copy, net, len(legs), [t.name() for t in terminals]))
    return restored, kept


def restore_vias(board, world, router):
    """TI's vias that are missing, where they fit. ST's are not: the RF strip's stitching is D-049's lattice, and the NFC
    copy's missing vias led to ST's Arduino header (RF disable, ground), which this board does not have."""
    added = []
    for copy, data, to_board, _ in references(board):
        if copy != "BOOST-DRV8711":
            continue
        for v in data["vias"]:
            at, net = to_board(*v["at"]), net_name(data, v["net"])
            if any(x.GetClass() == "PCB_VIA" and RS.short(x.GetNetname()) == net
                   and (x.GetPosition() - at).EuclideanNorm() < mm(0.2) for x in world.tracks):
                continue
            netinfo = next((n for n in board.GetNetsByName().values() if RS.short(n.GetNetname()) == net), None)
            if netinfo is None:
                continue
            probe = RS.probe_for(board, netinfo)
            if router.via_problem(at, mm(v["size"]), mm(v["drill"]), probe, own_net_ok=True):
                continue
            via = pcbnew.PCB_VIA(board)
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetPosition(at)
            via.SetWidth(mm(v["size"]))
            via.SetDrill(mm(v["drill"]))
            via.SetNet(netinfo)
            world.add(via)
            added.append((copy, net))
    return added


def vendor_widths(board):
    widths = defaultdict(int)
    for copy, data, _, _ in references(board):
        for t in data["tracks"]:
            net = net_name(data, t["net"])
            widths[net] = max(widths[net], mm(t["width"]))
    return widths


def joins(board, islands, found):
    """Open connections among one copy's own parts (both pads of one copy, or a copy's pad and loose copper of its net),
    closest first; a crystal's pairs grouped."""
    pairs = []
    for net, terms in found.items():
        if not terms:
            continue
        name = RS.short(terms[0].item.GetNetname())
        if name == GND or terms[0].item.GetNetClassName() == "PWR_BUS":
            continue
        for a, b in itertools.combinations(terms, 2):
            if islands.find(RS.uid(a.item)) == islands.find(RS.uid(b.item)):
                continue
            if not RS.vendor_internal(a, b):
                continue
            length = (b.at - a.at).EuclideanNorm() / 1e6
            if length <= MAX_JOIN:
                pairs.append((length, name, a, b))
    pairs.sort(key=lambda p: (p[0], p[1], p[2].name(), p[3].name()))
    return pairs


def rejoin(board, world, islands, router):
    widths = vendor_widths(board)
    pairs = joins(board, islands, RS.terminals(board))
    done, failed = [], []
    crystal = [p for p in pairs if p[2].item.GetNetClassName() == "CRYSTAL"]
    others = [p for p in pairs if p[2].item.GetNetClassName() != "CRYSTAL"]
    groups = defaultdict(list)
    for p in crystal:
        groups[RS.crystal_of(p[2], p[3])].append(p)
    for name in sorted(groups):
        nets, laid, made = set(), [], []
        for length, net, a, b in groups[name]:
            nets.add(net)
            if net in {m[1] for m in made} or islands.find(RS.uid(a.item)) == islands.find(RS.uid(b.item)):
                continue
            width = widths.get(net) or RS.link_width(a.item.GetNetClassName(), a, b)
            result, why = router.route(a, b, width, allow_vias=False, layers=(0,), margins=(2.0, 4.0))
            if result is None:
                failed.append((net, a.name(), b.name(), length, why))
                continue
            laid += result[0] + result[1]
            made.append((length, net, a.name(), b.name(), width))
        if {m[1] for m in made} != nets:
            for item in laid:
                world.remove(item)
            failed += [(m[1], m[2], m[3], m[0], "its crystal pair did not route") for m in made]
            continue
        done += made
    for length, net, a, b in others:
        if islands.find(RS.uid(a.item)) == islands.find(RS.uid(b.item)):
            continue
        width = widths.get(net) or RS.link_width(a.item.GetNetClassName(), a, b)
        width = min(width, RS.link_width(a.item.GetNetClassName(), a, b)) if a.kind == "pad" or b.kind == "pad" else width
        quiet = a.item.GetNetClassName() in QUIET_CLASSES
        result, why = router.route(a, b, max(width, mm(RS.MIN_WIDTH)), allow_vias=not quiet,
                                   layers=(0,) if quiet else (0, 1), margins=(2.0, 4.0))
        if result is None:
            failed.append((net, a.name(), b.name(), length, why))
            continue
        done.append((length, net, a.name(), b.name(), width))
    return done, failed


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    world = RS.World(board)
    islands = RS.Islands(board)
    router = M.Router(board, world, islands)
    restored, kept = restore_chains(board, world, islands, missing_chains(board, world))
    adapted, _ = adapt_chains(board, world, islands, kept, moved_pads(board))
    restored += adapted
    vias = restore_vias(board, world, router)
    islands = RS.Islands(board) if vias else islands
    router.islands = islands
    done, failed = rejoin(board, world, islands, router)
    grounds, no_spot = RS.ground_islands(board, world, islands, copies=True)
    if not (restored or vias or done or grounds):
        print("the vendor copies have nothing left to close: nothing to do")
        sys.exit(3)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for copy, net, count, ends in restored:
        print(f"restored {copy:14} {net:12} {count} segment(s) from the reference, {ends[0]} -> {ends[1]}")
    for copy, net in vias:
        print(f"restored {copy:14} {net:12} via")
    for length, net, a, b, width in done:
        print(f"re-joined {net:12} {a:>22} -> {b:<22} {width / 1e6:.3f} mm ({length:.2f} mm apart)")
    for names, at, length, diameter, drill, width in grounds:
        print(f"ground   {names:28} via {drill:.2f} / {diameter:.2f} at {at}, stub {length:.2f} mm")
    for net, a, b, length, why in failed:
        print(f"open     {net:12} {a:>22} -> {b:<22} {length:.2f} mm: {why}")
    for names in no_spot:
        print(f"open     GND {names}: no via spot")
    print(f"{len(restored)} chains restored, {len(vias)} vias, {len(done)} re-joined, {len(grounds)} ground vias; "
          f"{len(failed) + len(no_spot)} left open")
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="close the vendor copies' open ends (one shot)")
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage()
        return
    if not args.apply:
        parser.error("nothing to do without --apply")
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage"])
    B.PROJECT.write_bytes(project)
    if result.returncode == 3:
        return
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
