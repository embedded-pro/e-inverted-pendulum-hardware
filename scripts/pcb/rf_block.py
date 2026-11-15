#!/usr/bin/env python3
"""Paste the RF corner of ST's NUCLEO-WB55 board (MB1355 rev D-01) onto our board, as ST laid it out (D-037).

One shot, on the owner's request: `python3 scripts/pcb/rf_block.py --apply`. It reads scripts/pcb/mb1355_rf.json
(made by scripts/rf_reference.py, derived from STMicroelectronics MB1355 rev D-01, www.st.com/opla) and:
  - replaces the board outline with placement.py's (MB1355's antenna tab and step at the top-left corner), retires the
    old full-width antenna rule areas and redraws the reference drawings;
  - places U301 and every RF-corner part exactly where ST has them, ST's board-left edge and tab top on our top-left
    corner (a pure translation: same orientation, no mirror). Footprints are ST's land patterns, re-centred, so
    each pad lands on ST's pad; U301 (KiCad's QFN-68) is fitted by its pads;
  - copies ST's L1 copper of the RF-corner nets, the GND stitching and fence vias, the L1/L2/L3/L4 ground of the RF
    strip, the L2 cut-out under the RF line (it references L3) and ST's pad keep-outs;
  - puts the VDDRF decoupling on top (owner decision; ST has it on the bottom): C308 100 pF next to pin 33 after
    removing three of ST's GND vias, C307 100 nF at the nearest free spot (DEVIATIONS below; routed by the owner);
  - nudges the few ST vias whose hole is closer than JLCPCB's 0.20 mm to other-net copper, by the least amount;
  - groups and locks it all as "MB1355 RF corner": move or rotate the group as one unit.
Re-running is a no-op once the group exists. Run board.py first so the parts and nets exist.
"""

import argparse
import json
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import placement  # noqa: E402

DATA = json.loads((pathlib.Path(__file__).resolve().parent / "mb1355_rf.json").read_text(encoding="utf-8"))
GROUP = "MB1355 RF corner"
RETIRED_RULE_AREAS = {"ANTENNA_KEEPOUT", "ANTENNA_BASE"}

DEVIATIONS = {
    "removed_vias": [(135.7659, 86.8935), (135.8881, 88.0177), (135.9229, 88.6405)],
    "top_decoupling": [("C308", (135.5451, 89.0864)), ("C307", (135.5451, 89.0864))],
}
HOLE_TO_COPPER = 0.20
PART_CLEARANCE = 0.15
BOARD_ONLY = {"SC401", "SC402", "SC403", "SC404"}

mm = pcbnew.FromMM


def to_ours(x, y):
    return B.to_board(*placement.from_mb1355(x, y))


def net_lookup(board):
    names = {}
    for name in board.GetNetsByName().keys():
        name = str(name)
        names.setdefault(name.rsplit("/", 1)[-1], name)
        names[name] = name
    return lambda short: board.FindNet(names[short])


def fit_mcu(fp):
    """Orientation and position that put U301's pads on ST's U1 pads (same numbers)."""
    target = {num: to_ours(*xy) for num, xy in DATA["mcu"]["pads"].items()}
    best = None
    for rot in (0.0, 90.0, 180.0, 270.0):
        fp.SetOrientationDegrees(rot)
        pads = {p.GetNumber(): p.GetPosition() - fp.GetPosition() for p in fp.Pads() if p.GetNumber() in target}
        dx = sum(target[n].x - rel.x for n, rel in pads.items()) / len(pads)
        dy = sum(target[n].y - rel.y for n, rel in pads.items()) / len(pads)
        err = max(math.hypot(target[n].x - rel.x - dx, target[n].y - rel.y - dy) for n, rel in pads.items())
        if best is None or err < best[0]:
            best = (err, rot, pcbnew.VECTOR2I(int(round(dx)), int(round(dy))))
    err, rot, pos = best
    if pcbnew.ToMM(err) > 0.02:
        sys.exit(f"U301 pads don't match MB1355 U1 (worst {pcbnew.ToMM(err):.3f} mm)")
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pos)
    return pcbnew.ToMM(err)


def chain(points):
    shape = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in points:
        shape.Append(to_ours(x, y))
    shape.SetClosed(True)
    return shape


def add_zone(board, layer, polygons, net=None, rule=None, priority=0, settings=None):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    for poly in polygons:
        zone.Outline().AddOutline(chain(poly))
    if rule:
        zone.SetIsRuleArea(True)
        zone.SetZoneName(rule["name"])
        layers = pcbnew.LSET()
        for name in rule["layers"]:
            layers.AddLayer(board.GetLayerID(name))
        zone.SetLayerSet(layers)
        zone.SetDoNotAllowZoneFills("pour" in rule["deny"])
        zone.SetDoNotAllowTracks("tracks" in rule["deny"])
        zone.SetDoNotAllowVias("vias" in rule["deny"])
        zone.SetDoNotAllowPads(False)
        zone.SetDoNotAllowFootprints(False)
    else:
        zone.SetNet(net)
        zone.SetAssignedPriority(priority)
        zone.SetLocalClearance(mm(max(settings["clearance"], 0.2)))
        zone.SetMinThickness(mm(settings["min_width"]))
        zone.SetThermalReliefGap(mm(settings["thermal_gap"]))
        zone.SetThermalReliefSpokeWidth(mm(settings["thermal_spoke"]))
        zone.SetPadConnection(settings["pad_connection"])
    board.Add(zone)
    return zone


def reset_geometry(board):
    """Old outline, drawings and retired rule areas out. Removing items leaves pcbnew's SWIG wrappers unusable for the
    rest of the process, so this runs in its own child process and apply() in the next one."""
    drawings = [item for item in board.GetDrawings() if item.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Dwgs_User)]
    retired = [zone for zone in board.Zones() if zone.GetIsRuleArea() and zone.GetZoneName() in RETIRED_RULE_AREAS]
    for item in drawings + retired:
        board.Remove(item)


def board_to_mech(v):
    return (round(pcbnew.ToMM(v.x) - B.ORIGIN[0], 3), round(B.ORIGIN[1] - pcbnew.ToMM(v.y), 3))


def orient(fp, part, net):
    """ST's rotation, or 180 degrees more when ST numbers the pins the other way: every pad must land on the ST pad
    of the same net."""
    st_nets = DATA["st_parts"].get(part["st"], {}).get("pads", {})
    wanted = []
    for number, x, y in part.get("pads", []):
        short = DATA["net_map"].get(st_nets.get(number, ""))
        wanted.append((to_ours(x, y), net(short).GetNetCode() if short else None))
    for extra in (0.0, 180.0):
        fp.SetOrientationDegrees(part["rot"] + extra)
        ok = True
        for target, netcode in wanted:
            hits = [p for p in fp.Pads() if (p.GetPosition() - target).EuclideanNorm() < mm(0.01)]
            if not hits or (netcode is not None and all(p.GetNetCode() != netcode for p in hits)):
                ok = False
                break
        if ok:
            return
    sys.exit(f"{fp.GetReference()}: no orientation puts its pads on MB1355 {part['st']}'s pads with the same nets")


def copper_near(board, centre, radius, layers=(pcbnew.F_Cu, pcbnew.B_Cu)):
    items = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if (pad.GetPosition() - centre).EuclideanNorm() < radius + pad.GetBoundingRadius():
                items.append(pad)
    for track in board.GetTracks():
        width = track.GetWidth(pcbnew.F_Cu) if track.GetClass() == "PCB_VIA" else track.GetWidth()
        if (track.GetPosition() - centre).EuclideanNorm() < radius + track.GetLength() + width:
            items.append(track)
    return items


def collides(shape, items, netcode, clearance, layers=(pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
    for item in items:
        if item.GetNetCode() == netcode:
            continue
        for layer in layers:
            if item.IsOnLayer(layer) and shape.Collide(item.GetEffectiveShape(layer), mm(clearance)):
                return item
    return None


def nudge_vias(board, vias):
    """Move a via straight away from the other-net copper its hole is too close to, 0.005 mm at a time."""
    moved, worst = 0, 0.0
    for via in vias:
        start = via.GetPosition()
        items = [i for i in copper_near(board, start, mm(1.5)) if i.m_Uuid.AsString() != via.m_Uuid.AsString()]
        for _ in range(40):
            hit = collides(via.GetEffectiveHoleShape(), items, via.GetNetCode(), HOLE_TO_COPPER)
            if hit is None:
                break
            if hit.GetClass() in ("PCB_TRACK", "PCB_ARC"):
                seg = pcbnew.SEG(hit.GetStart(), hit.GetEnd())
                away = via.GetPosition() - seg.NearestPoint(via.GetPosition())
            else:
                away = via.GetPosition() - hit.GetPosition()
            length = max(away.EuclideanNorm(), 1)
            via.SetPosition(via.GetPosition() + pcbnew.VECTOR2I(int(away.x * mm(0.005) / length),
                                                                 int(away.y * mm(0.005) / length)))
        else:
            sys.exit(f"via at {board_to_mech(start)} can't reach {HOLE_TO_COPPER} mm hole-to-copper")
        shift = pcbnew.ToMM((via.GetPosition() - start).EuclideanNorm())
        if shift > 0:
            moved, worst = moved + 1, max(worst, shift)
    return moved, worst


def place_near(board, fp, pin):
    """First spot, nearest to `pin` first, where every pad clears other-net copper by PART_CLEARANCE and the
    courtyard clears every other footprint's."""
    others = [f for f in board.GetFootprints() if f.GetReference() != fp.GetReference()]
    for ring in range(1, 160):
        r = mm(0.05) * ring
        steps = max(8, int(2 * math.pi * ring / 2))
        for k in range(steps):
            angle = 2 * math.pi * k / steps
            for rot in (90.0, 270.0, 0.0, 180.0):
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(pin + pcbnew.VECTOR2I(int(r * math.cos(angle)), int(r * math.sin(angle))))
                if spot_ok(board, fp, others):
                    return
    sys.exit(f"no free spot for {fp.GetReference()} near VDDRF")


def spot_ok(board, fp, others):
    court = fp.GetCourtyard(pcbnew.F_CrtYd)
    for other in others:
        if other.IsFlipped() or (other.GetPosition() - fp.GetPosition()).EuclideanNorm() > mm(15):
            continue
        if court.Collide(other.GetCourtyard(pcbnew.F_CrtYd), 0):
            return False
    for pad in fp.Pads():
        items = [i for i in copper_near(board, pad.GetPosition(), mm(1.5))
                 if i.GetClass() != "PAD" or i.GetParentFootprint().GetReference() != fp.GetReference()]
        if collides(pad.GetEffectiveShape(pcbnew.F_Cu), items, pad.GetNetCode(), PART_CLEARANCE, (pcbnew.F_Cu,)):
            return False
        vias = [t for t in items if t.GetClass() == "PCB_VIA"]
        if collides(pad.GetEffectiveShape(pcbnew.F_Cu), vias, pad.GetNetCode(), HOLE_TO_COPPER, (pcbnew.F_Cu,)):
            return False
    return True


def has_group(board):
    return any(g.GetName() == GROUP for g in board.Groups())


def apply(board):
    B.ensure_outline(board)
    B.ensure_rule_areas(board)
    B.ensure_drawings(board)
    net = net_lookup(board)
    st_net = lambda name: net(DATA["net_map"][name])  # noqa: E731
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    mcu = footprints[DATA["mcu"]["ours"]]
    worst = fit_mcu(mcu)
    group.AddItem(mcu)

    placed = []
    for part in DATA["parts"]:
        ref = part["ours"]
        fp = footprints.get(ref)
        if fp is None and ref in BOARD_ONLY:
            fp = B.load_footprint(board, part["footprint"])
            fp.SetReference(ref)
            fp.SetValue("S0951-46R")
            fp.SetBoardOnly(True)
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
            fp.SetDNP(True)
            for pad in fp.Pads():
                pad.SetNet(net("GND"))
            board.Add(fp)
        if fp is None:
            sys.exit(f"{ref} is not on the board: run board.py first")
        if fp.GetFPIDAsString() != part["footprint"]:
            sys.exit(f"{ref} has {fp.GetFPIDAsString()}, expected {part['footprint']}: update the schematic")
        fp.SetPosition(to_ours(*part["at"]))
        orient(fp, part, net)
        placed.append(fp)
    for fp in placed:
        group.AddItem(fp)

    for t in DATA["tracks"]:
        item = pcbnew.PCB_ARC(board) if "mid" in t else pcbnew.PCB_TRACK(board)
        item.SetStart(to_ours(*t["start"]))
        item.SetEnd(to_ours(*t["end"]))
        if "mid" in t:
            item.SetMid(to_ours(*t["mid"]))
        item.SetWidth(mm(t["width"]))
        item.SetLayer(pcbnew.F_Cu)
        item.SetNet(st_net(t["net"]))
        board.Add(item)
        group.AddItem(item)

    removed = [tuple(v) for v in DEVIATIONS["removed_vias"]]
    vias = 0
    for v in DATA["vias"]:
        if any(math.hypot(v["at"][0] - x, v["at"][1] - y) < 0.01 for x, y in removed):
            continue
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(to_ours(*v["at"]))
        via.SetWidth(mm(v["size"]))
        via.SetDrill(mm(v["drill"]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetNet(st_net(v["net"]))
        board.Add(via)
        group.AddItem(via)
        vias += 1

    group_vias = [item for item in group.GetItems() if item.GetClass() == "PCB_VIA"]
    nudged = nudge_vias(board, group_vias)
    for ref, pin in DEVIATIONS["top_decoupling"]:
        fp = footprints[ref]
        place_near(board, fp, to_ours(*pin))
        group.AddItem(fp)
        placed.append(fp)

    for z in DATA["zones"]:
        zone = add_zone(board, board.GetLayerID(z["layer"]), z["polygons"], net=st_net(z["net"]),
                        priority=z["priority"], settings=z)
        zone.SetZoneName(f"MB1355 {z['layer']} {DATA['net_map'][z['net']]}")
        group.AddItem(zone)
    for rule in DATA["rule_areas"]:
        zone = add_zone(board, board.GetLayerID(rule["layers"][0]), [rule["polygon"]], rule=rule)
        group.AddItem(zone)

    for item in group.GetItems():
        item.SetLocked(True)
    group.SetLocked(True)
    for fp in placed + [mcu]:
        B.label_fields(fp)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    antenna = footprints["AE401"].GetPosition()
    print(f"pasted '{GROUP}': {len(placed) + 1} footprints (U301 pad fit {worst:.4f} mm), {len(DATA['tracks'])} tracks, "
          f"{vias} vias ({len(removed)} of ST's removed for C308, {nudged[0]} nudged by <= {nudged[1]:.3f} mm), "
          f"{len(DATA['zones'])} zones, {len(DATA['rule_areas'])} rule areas")
    for ref, _ in DEVIATIONS["top_decoupling"]:
        fp = footprints[ref]
        print(f"{ref} on top at mechanical {board_to_mech(fp.GetPosition())}, rotation {fp.GetOrientationDegrees():.0f}")
    print(f"antenna feed at mechanical {placement.from_mb1355(*[p for p in DATA['parts'] if p['ours'] == 'AE401'][0]['at'])}"
          f" (board {pcbnew.ToMM(antenna.x):.3f}, {pcbnew.ToMM(antenna.y):.3f} mm); top-right edge and ground at "
          f"z {placement.TOP_RIGHT_Z}")
    return True


def stage(step):
    board = pcbnew.LoadBoard(str(B.BOARD))
    if has_group(board):
        print(f"'{GROUP}' is already on the board: nothing to do")
        sys.exit(3)
    reset_geometry(board) if step == "reset" else apply(board)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="paste the MB1355 RF corner (one shot)")
    parser.add_argument("--pcbnew-stage", choices=["reset", "apply"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.pcbnew_stage)
        return
    if not args.apply:
        parser.error("nothing to do without --apply")
    project = B.PROJECT.read_bytes()
    for step in ("reset", "apply"):
        result = subprocess.run([sys.executable, __file__, "--pcbnew-stage", step])
        B.PROJECT.write_bytes(project)
        if result.returncode == 3:
            return
        if result.returncode:
            sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
