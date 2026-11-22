#!/usr/bin/env python3
"""The motor phases from TI's phase strips to J601 / J602, and the SS34 clamps beside their own strips (D-060).

    python3 scripts/pcb/route_phases.py --apply

TI's BOOST-DRV8711 runs each phase pour straight from its FETs to a terminal block in line with them (SLVC575B,
BOARD/BOOST-DRV8711.PcbDoc, top layer). Our copy is turned 180 degrees (D-040), so that direction is our bracket strip
and the copy stops at its edge (z 13.5): MOT_L_P and MOT_R_N are boxed in on every layer by their neighbours' pours. So,
as TI does, each phase leaves its strip downwards, and the two phases of each motor run as a pair on F.Cu:
  - across the top of the bracket strip, where the front carries no parts but may carry copper (BRACKET_STRIP denies
    nothing on F.Cu; the bracket base on the back denies B.Cu, D-026), clear of the M3 / M2 holes' keep-outs;
  - left motor: up into the empty area left of the bridges, left above MB1's keep-out, up the far left to C603 and J601;
  - right motor: up beside C507 through the right margin of TI's F.Cu GND (outside the bus hot loop C507 -> FETs ->
    shunts -> C507, power-pcb-layout s3.1; the fill refills round the tracks), then to C607 and J602.
The pair keeps 1.6 mm centre to centre (0.8 mm gap); its 45-degree corners are cut so the gap stays the same round each
bend (outer chamfer = inner + 0.586 x spacing). Width 0.8 mm, above the PWR_2A class's 0.781 mm (docs/power-map.md: 2 A peak, IPC-2221
0.78 mm on 1 oz outer at 10 C). The phase that crosses its connector's pin column (MOT_L_N to J601 pin 1, MOT_R_P to J602
pin 6) drops to B.Cu through two 0.3 / 0.6 mm vias (>= I / 1 A, power map) and runs outside the pins, as before.

The clamps (ours, D-022): since D-042's bridge swap, D502 and D503 sat inside the other phase's copper and D501 / D502 /
C502 blocked MOT_R_N's way out. Each clamp now stands on the outer side of its own strip, pad 1 (cathode, the phase) up
in the strip within 5 mm of its FET's phase pads (D-040: as near as TI's FET row allows), pad 2 (anode) down with a
0.3 / 0.6 mm GND via under the body to the L2 plane (S2 models the clamp straight across the phase node). C502 (bridge
A's 10 uF) moves beside C507, VBAT pad in TI's VBAT pour, GND pad in TI's GND. C603 turns 180 degrees so the left pair
meets it in order. The four phase test pads sit on their own tracks (D-051's row is in the way).

Our earlier phase copper (the 0.8 mm tracks and vias of passes 3 / 4) is taken up first; TI's 0.254 mm phase tracks to
the DRV8711 stay. Every new track and via is checked exactly against other nets' copper (the board's rules), holes,
keep-outs and other nets' pours (GND pours give way; the clamps' GND vias also pass TI's B.Cu VBAT pour, which gives
way). It refuses on any problem. One shot: a no-op once the paths are on the board. Nothing is locked (D-045).
"""

import argparse
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import place_block as PB  # noqa: E402
import placement  # noqa: E402
import respace as R  # noqa: E402
import route_simple as RS  # noqa: E402
import silk  # noqa: E402

B.pcbnew = pcbnew
mm = pcbnew.FromMM
WIDTH = 0.8
VIA = (0.6, 0.3)
CLAMP_VIA = (0.6, 0.3)
CLAMP_STUB = 0.6
EDGE = 0.3
PHASES = ("MOT_L_P", "MOT_L_N", "MOT_R_P", "MOT_R_N")
# Each clamp on the outer side of its own strip, pad 1 up (rotation 270): (ref, x, z).
CLAMP_Z = 16.05
CLAMPS = (("D504", 0.85), ("D503", 5.5), ("D502", 10.8), ("D501", 15.3))
# The strip each clamp sits in: its GND via is in that pour, which flows round it.
STRIPS = {"D504": "BOOST-DRV8711 F.Cu MOT_L_N 12", "D503": "BOOST-DRV8711 F.Cu MOT_L_P 13",
          "D502": "BOOST-DRV8711 F.Cu MOT_R_N 14", "D501": "BOOST-DRV8711 F.Cu MOT_R_P 15"}
CLAMP_ROTATION = 270.0
PARTS = (("C502", 18.2, 17.35, 270.0),)
# The paths: (net, layer, [(x, z, chamfer)...]); a chamfer cuts that 90-degree corner at 45 degrees (mm along each leg).
INNER, OUTER_16, OUTER_155 = 1.0, 1.94, 1.91
PATHS = (
    ("MOT_L_N", "F.Cu", [(-1.9, 15.0, 0), (-1.9, 11.9, 1.0), (-13.0, 11.9, INNER), (-13.0, 16.1, OUTER_16),
                         (-32.42, 16.1, INNER), (-32.42, 34.0, 0)]),
    ("MOT_L_N", "B.Cu", [(-32.42, 34.0, 0), (-32.42, 33.2, 0), (-33.22, 32.4, 0), (-34.2, 32.4, 0), (-35.2, 33.4, 0),
                         (-35.2, 44.6, 0), (-34.3, 45.5, 0)]),
    ("MOT_L_P", "F.Cu", [(3.05, 15.0, 0), (3.05, 10.3, 1.0), (-14.6, 10.3, OUTER_16), (-14.6, 14.5, INNER),
                         (-33.97, 14.5, OUTER_155), (-33.97, 35.5, 0)]),
    ("MOT_R_P", "F.Cu", [(13.0, 15.0, 0), (13.0, 12.2, 1.0), (27.1, 12.2, INNER), (27.1, 26.5, OUTER_16),
                         (32.42, 26.5, INNER), (32.42, 34.0, 0)]),
    ("MOT_R_P", "B.Cu", [(32.42, 34.0, 0), (32.42, 33.2, 0), (33.22, 32.4, 0), (34.2, 32.4, 0), (35.2, 33.4, 0),
                         (35.2, 44.6, 0), (34.3, 45.5, 0)]),
    ("MOT_R_N", "F.Cu", [(8.3, 15.0, 0), (8.3, 11.0, 1.0), (28.7, 11.0, 1.9), (28.7, 24.9, INNER),
                         (33.97, 24.9, OUTER_155), (33.97, 35.5, 0)]),
)
VIAS = (("MOT_L_N", (-32.42, 33.2)), ("MOT_L_N", (-32.42, 34.0)), ("MOT_R_P", (32.42, 33.2)), ("MOT_R_P", (32.42, 34.0)))
# Ours that the old copper left behind: anything wider than TI's 0.254 mm phase tracks, and every via, on a phase net.
TI_WIDTH = 0.3
# Items taken off the board stay referenced until it is saved (SWIG would free them under the board).
KEEP = []


def at(x, z):
    """Board point, rounded to the nanometre so 45-degree legs stay exact (DRC track_angle)."""
    return pcbnew.VECTOR2I(int(round((B.ORIGIN[0] + x) * 1e6)), int(round((B.ORIGIN[1] - z) * 1e6)))


def chamfered(points):
    """Board points of a path with each marked 90-degree corner cut at 45 degrees."""
    out = [at(points[0][0], points[0][1])]
    for k in range(1, len(points) - 1):
        (x0, z0, _), (x1, z1, c), (x2, z2, _) = points[k - 1], points[k], points[k + 1]
        if not c:
            out.append(at(x1, z1))
            continue
        d0 = (x1 - x0, z1 - z0)
        d1 = (x2 - x1, z2 - z1)
        n0, n1 = math.hypot(*d0), math.hypot(*d1)
        out.append(at(round(x1 - d0[0] / n0 * c, 4), round(z1 - d0[1] / n0 * c, 4)))
        out.append(at(round(x1 + d1[0] / n1 * c, 4), round(z1 + d1[1] / n1 * c, 4)))
    out.append(at(points[-1][0], points[-1][1]))
    return out


def net_of(board, name):
    return next(n for n in board.GetNetsByName().values() if RS.short(n.GetNetname()) == name)


def old_copper(board):
    items = []
    for t in board.GetTracks():
        if RS.short(t.GetNetname()) not in PHASES:
            continue
        if t.GetClass() == "PCB_VIA" or t.GetWidth() > mm(TI_WIDTH):
            items.append(t)
    return items


def stubs(board, fps):
    """Tracks with an end on one of these parts' pads (their connection at the old spot), and the vias at their other
    ends that nothing else uses."""
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    found = []
    for fp in fps:
        for pad in fp.Pads():
            shape = pad.GetEffectiveShape(pcbnew.F_Cu)
            for t in tracks:
                if t.GetNetCode() != pad.GetNetCode():
                    continue
                ends = [e for e in (t.GetStart(), t.GetEnd()) if shape.Collide(pcbnew.SHAPE_CIRCLE(e, 1), 0)]
                if not ends:
                    continue
                found.append(t)
                other = t.GetEnd() if ends[0] == t.GetStart() else t.GetStart()
                for v in board.GetTracks():
                    if v.GetClass() == "PCB_VIA" and v.GetPosition() == other and v.GetNetCode() == t.GetNetCode() and \
                            sum(1 for u in tracks if other in (u.GetStart(), u.GetEnd())) == 1:
                        found.append(v)
    seen = set()
    return [i for i in found if not (RS.uid(i) in seen or seen.add(RS.uid(i)))]


def zone_outlines(board, layer, net):
    """Other nets' pours on this layer that must not be cut (GND gives way)."""
    found = []
    for zone in board.Zones():
        if zone.GetIsRuleArea() or not zone.IsOnLayer(layer) or zone.GetNetCode() == net.GetNetCode():
            continue
        if RS.short(zone.GetNetname()) == "GND":
            continue
        found.append((zone.GetZoneName(), pcbnew.SHAPE_POLY_SET(zone.Outline())))
    return found


def segment_problems(board, world, net, layer, a, b, width):
    shape = pcbnew.SHAPE_SEGMENT(a, b, width)
    probe = RS.probe_for(board, net)
    problems = []
    if world.outside.Collide(shape, mm(EDGE)):
        problems.append("edge")
    if any(area.Collide(shape, 0) for area in world.keep_tracks[layer]):
        problems.append("rule area")
    for pad in world.pads:
        if pad.HasHole() and pad.GetNetCode() != net.GetNetCode():
            gap = RS.NPTH_TO_COPPER if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else RS.PAD_HOLE_TO_COPPER
            if pad.GetEffectiveHoleShape().Collide(shape, mm(gap)):
                problems.append(f"hole {pad.GetParentFootprint().GetReference()}")
        if pad.IsOnLayer(layer) and pad.GetNetCode() != net.GetNetCode() and \
                pad.GetEffectiveShape(layer).Collide(shape, mm(max(0.2, R.rule_clearance(pad, probe)))):
            problems.append(f"pad {pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}")
    for item in world.tracks:
        if item.GetNetCode() == net.GetNetCode():
            continue
        if item.GetClass() == "PCB_VIA" and item.GetEffectiveHoleShape().Collide(shape, mm(RS.HOLE_TO_COPPER)):
            problems.append(f"via hole {RS.short(item.GetNetname())}")
        if item.IsOnLayer(layer) and \
                item.GetEffectiveShape(layer).Collide(shape, mm(max(0.2, R.rule_clearance(item, probe)))):
            problems.append(f"{'via' if item.GetClass() == 'PCB_VIA' else 'track'} {RS.short(item.GetNetname())}")
    for name, poly in zone_outlines(board, layer, net):
        if poly.Collide(shape, mm(0.2)):
            problems.append(f"pour {name}")
    return problems


def via_problems(board, world, net, position, size, pours_ok=()):
    diameter, drill = (mm(v) for v in size)
    ring = pcbnew.SHAPE_CIRCLE(position, diameter // 2)
    hole = pcbnew.SHAPE_CIRCLE(position, drill // 2)
    probe = RS.probe_for(board, net)
    problems = []
    if world.outside.Collide(ring, mm(EDGE)):
        problems.append("edge")
    if any(area.Collide(ring, 0) for area in world.keep_vias):
        problems.append("rule area")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        if any(area.Collide(ring, 0) for area in world.keep_tracks[layer]):
            problems.append("rule area")
    for item in list(world.pads) + list(world.tracks):
        drilled = item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole())
        if drilled and item.GetEffectiveHoleShape().Collide(hole, mm(RS.HOLE_TO_HOLE)):
            problems.append(f"hole near {RS.short(item.GetNetname())}")
        if item.GetNetCode() == net.GetNetCode():
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if item.IsOnLayer(layer) and (item.GetEffectiveShape(layer).Collide(ring, mm(max(0.2, R.rule_clearance(item, probe))))
                                          or item.GetEffectiveShape(layer).Collide(hole, mm(RS.HOLE_TO_COPPER))):
                problems.append(f"copper {RS.short(item.GetNetname())}")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        for name, poly in zone_outlines(board, layer, net):
            if name not in pours_ok and poly.Collide(ring, mm(0.2)):
                problems.append(f"pour {name}")
    return sorted(set(problems))


def add_track(board, world, net, layer, a, b, width):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(a)
    track.SetEnd(b)
    track.SetWidth(width)
    track.SetLayer(layer)
    track.SetNet(net)
    world.add(track)


def add_via(board, world, net, position, size):
    via = pcbnew.PCB_VIA(board)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetPosition(position)
    via.SetWidth(mm(size[0]))
    via.SetDrill(mm(size[1]))
    via.SetNet(net)
    world.add(via)


def place(fp, x, z, rotation):
    fp.SetOrientationDegrees(rotation)
    fp.SetPosition(B.to_board(x, z))
    pads = pcbnew.BOX2I()
    for pad in fp.Pads():
        pads.Merge(pad.GetBoundingBox())
    fp.Move(B.to_board(x, z) - pads.GetCenter())


def is_done(board):
    return all(any(t.GetClass() == "PCB_TRACK" and RS.short(t.GetNetname()) == net and t.GetLayer() == board.GetLayerID(
        layer) and t.GetStart() == chamfered(points)[0] for t in board.GetTracks()) for net, layer, points in PATHS)


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    if is_done(board):
        print("the phases are routed: nothing to do")
        sys.exit(3)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    moved = [footprints[ref] for ref, _ in CLAMPS] + [footprints[ref] for ref, *_ in PARTS]
    for item in old_copper(board) + stubs(board, moved):
        board.Remove(item)
        KEEP.append(item)
    for ref, x in CLAMPS:
        place(footprints[ref], x, CLAMP_Z, CLAMP_ROTATION)
    for ref, x, z, rotation in PARTS:
        place(footprints[ref], x, z, rotation)
    tables = {ref: (x, z, rot) for ref, x, z, rot in placement.motor_io() + placement.rest()}
    for ref in ("C603", "TP503", "TP504", "TP505", "TP506"):
        place(footprints[ref], *tables[ref])
    outline = PB.outline_of(board)
    failed = []
    for ref in [r for r, _ in CLAMPS] + [r for r, *_ in PARTS] + ["C603", "TP503", "TP504", "TP505", "TP506"]:
        fp = footprints[ref]
        others = [f for f in board.GetFootprints() if f.GetReference() != ref]
        failed += [f"{ref}: {why}" for why in PB.problems(board, fp, outline, others)]
    world = RS.World(board)
    for ref, x in CLAMPS:
        fp = footprints[ref]
        pads = {p.GetNumber(): p for p in fp.Pads()}
        gnd = pads["2"].GetNet()
        position = B.to_board(x, CLAMP_Z)
        problems = via_problems(board, world, gnd, position, CLAMP_VIA,
                                pours_ok=("BOOST-DRV8711 B.Cu VBAT 11", STRIPS[ref]))
        if problems:
            failed.append(f"{ref} GND via: {problems}")
            continue
        add_via(board, world, gnd, position, CLAMP_VIA)
        add_track(board, world, gnd, pcbnew.F_Cu, pads["2"].GetPosition(), position, mm(CLAMP_STUB))
    for net_name, position in VIAS:
        net = net_of(board, net_name)
        problems = via_problems(board, world, net, B.to_board(*position), VIA)
        if problems:
            failed.append(f"{net_name} via at {position}: {problems}")
        add_via(board, world, net, B.to_board(*position), VIA)
    for net_name, layer_name, points in PATHS:
        net = net_of(board, net_name)
        layer = board.GetLayerID(layer_name)
        corners = chamfered(points)
        for a, b in zip(corners, corners[1:]):
            problems = segment_problems(board, world, net, layer, a, b, mm(WIDTH))
            if problems:
                failed.append(f"{net_name} {layer_name} {RF_mech(a)} -> {RF_mech(b)}: {sorted(set(problems))}")
            add_track(board, world, net, layer, a, b, mm(WIDTH))
    if failed:
        sys.exit("phases not routed:\n  " + "\n  ".join(failed))
    kept, moved, failed_labels = silk.layout(board, check=False)
    if failed_labels:
        print(f"{', '.join(lb.ref for lb in failed_labels)}: no clean spot as they are; every name laid out afresh")
        kept, moved, failed_labels = silk.layout(board, check=False, relayout=True)
    silk.report(kept, moved, failed_labels, check=False)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"phases routed: {sum(len(chamfered(p)) - 1 for _, _, p in PATHS)} tracks, {len(VIAS) + len(CLAMPS)} vias; "
          f"clamps {', '.join(r for r, _ in CLAMPS)} and C502 moved; C603 turned; TP503-TP506 on their tracks")
    pcbnew.SaveBoard(str(B.BOARD), board)


def RF_mech(v):
    return (round(pcbnew.ToMM(v.x) - B.ORIGIN[0], 2), round(B.ORIGIN[1] - pcbnew.ToMM(v.y), 2))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="route the four phases and move the clamps (one shot)")
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
