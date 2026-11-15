#!/usr/bin/env python3
"""Paste the motor-driver power stage of TI's BOOST-DRV8711 onto our board, as TI laid it out (D-040).

One shot, on the owner's request: `python3 scripts/pcb/drv_block.py --apply`. It reads scripts/pcb/boost_drv8711.json
(made by scripts/drv_reference.py, derived from Texas Instruments BOOST-DRV8711 design files, SLVC575B) and:
  - places U501, Q501-Q504, R509 / R512, the net ties NT501-NT504 (on B.Cu, as TI has them) and C508-C514 where TI has
    U1, Q1-Q4, R1 / R2, NT1-NT4 and C2-C8: TI's stage turned by placement.DRIVE_TURN about its centre (180: the FETs
    nearest the bracket strip, the DRV8711 above them, bridge A on the right), its box centred on x 0 with its bottom
    edge 1 mm above the bracket strip. Every pad lands on TI's pad of the same net;
  - puts C507 (our SMD 220 uF, D-040) at the centre of TI's through-hole C1, its + pad toward TI's VM pad;
  - copies TI's tracks, vias and pours cut to the stage's box, and nudges any via whose hole is closer than JLCPCB's
    0.20 mm to other-net copper (rf_block.nudge_vias);
  - places our extras (owner, D-040) at the nearest free top-side spot to their pin: the SS34 clamps at the phase
    nodes, the per-bridge 10 uF / 100 nF at the high-side drains, the 1 nF sense caps (not fitted) at the ISEN pins
    and the logic pulls at their DRV8711 pins;
  - groups and locks it all as "BOOST-DRV8711 drive", then lays the silkscreen labels out (silk.py, D-041).
Re-running is a no-op once the group exists; --replace removes the group's copper and pastes it again. Run board.py
first so the parts and nets exist.
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
import silk  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402

DATA = json.loads((pathlib.Path(__file__).resolve().parent / "boost_drv8711.json").read_text(encoding="utf-8"))
GROUP = B.DRIVE_GROUP
LAYERS = {"Top Layer": "F.Cu", "Bottom Layer": "B.Cu"}
BOTTOM_Z = placement.STRIP_TOP_Z + 1.0
BULK = "C507"
EXTRAS = [  # (ref, how its target is found: ("pads", ref, net) = centroid of those pads, ("pin", ref, number))
    ("D501", ("pads", "Q501", "MOT_L_P")), ("D502", ("pads", "Q502", "MOT_L_N")),
    ("D503", ("pads", "Q503", "MOT_R_P")), ("D504", ("pads", "Q504", "MOT_R_N")),
    ("C503", ("pads", "Q501", "VBAT")), ("C502", ("pads", "Q502", "VBAT")),
    ("C506", ("pads", "Q503", "VBAT")), ("C505", ("pads", "Q504", "VBAT")),
    ("C501", ("pins", "U501", ("34", "33"))), ("C504", ("pins", "U501", ("25", "24"))),
    ("R515", ("pins", "U501", ("18",))), ("R516", ("pins", "U501", ("19",))),
    ("R517", ("pins", "U501", ("17",))), ("R518", ("pins", "U501", ("8",))),
]
SEARCH_MM = 20.0
EXTRA_CLEARANCE = 0.2  # above TI's 0.178 mm group rule and equal to the MOTOR / PWR_BUS class clearance

mm = pcbnew.FromMM
_BOX = DATA["box"]


def to_mech(x, y):
    """TI's frame (y down) to ours: turned placement.DRIVE_TURN about the box centre, the box centred on x 0 with its
    lower edge at BOTTOM_Z."""
    a, b = x - (_BOX[0] + _BOX[2]) / 2, -(y - (_BOX[1] + _BOX[3]) / 2)
    a, b = placement._turn(a, b, placement.DRIVE_TURN)
    half = abs(placement._turn((_BOX[2] - _BOX[0]) / 2, (_BOX[3] - _BOX[1]) / 2, placement.DRIVE_TURN)[1])
    return (round(a, 4), round(BOTTOM_Z + half + b, 4))


def to_ours(x, y):
    return B.to_board(*to_mech(x, y))


def place(fp, part, net):
    """TI's position, on TI's side, in the one orientation that puts every pad on TI's pad of the same net."""
    if part["side"] == "B" and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    wanted = [(to_ours(x, y), net(DATA["net_map"][st_net]).GetNetCode()) for _, x, y, st_net in part["pads"]]
    for angle in (part["rot"], part["rot"] + 180.0, part["rot"] + 90.0, part["rot"] + 270.0):
        fp.SetOrientationDegrees(angle % 360.0)
        fp.SetPosition(to_ours(*part["at"]))
        shift = pcbnew.VECTOR2I(0, 0)
        pads = list(fp.Pads())
        centre = pcbnew.VECTOR2I(sum(p.GetPosition().x for p in pads) // len(pads),
                                 sum(p.GetPosition().y for p in pads) // len(pads))
        shift = to_ours(*part["at"]) - centre
        fp.SetPosition(fp.GetPosition() + shift)
        if all(any((pad.GetPosition() - target).EuclideanNorm() < mm(0.02) and pad.GetNetCode() == code
                   for pad in fp.Pads()) for target, code in wanted):
            return
    sys.exit(f"{fp.GetReference()}: no orientation puts its pads on TI's {part['st']} pads with the same nets")


def place_bulk(fp, part, net):
    """Our SMD bulk at the centre of TI's through-hole C1, + (pad 1, VBAT) toward TI's VM pad."""
    vm = next((x, y) for _, x, y, st_net in part["pads"] if st_net == "VM")
    target = to_ours(*vm)
    best = None
    for angle in (0.0, 90.0, 180.0, 270.0):
        fp.SetOrientationDegrees(angle)
        fp.SetPosition(to_ours(*part["at"]))
        plus = next(p for p in fp.Pads() if p.GetNumber() == "1")
        distance = (plus.GetPosition() - target).EuclideanNorm()
        if best is None or distance < best[0]:
            best = (distance, angle)
    fp.SetOrientationDegrees(best[1])
    fp.SetPosition(to_ours(*part["at"]))
    if fp.FindPadByNumber("1").GetNetCode() != net("VBAT").GetNetCode():
        sys.exit(f"{BULK} pad 1 isn't VBAT")


def add_pour(board, z, net):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(board.GetLayerID(LAYERS[z["layer"]]))
    for polygon in z["polygons"]:
        chain = pcbnew.SHAPE_LINE_CHAIN()
        for x, y in polygon:
            chain.Append(to_ours(x, y))
        chain.SetClosed(True)
        zone.Outline().AddOutline(chain)
    zone.SetNet(net)
    zone.SetZoneName(f"BOOST-DRV8711 {LAYERS[z['layer']]} {net.GetNetname().rsplit('/', 1)[-1]}")
    zone.SetAssignedPriority(z["priority"])
    zone.SetLocalClearance(mm(max(z["clearance"], DATA["st_rules_mm"]["clearance"])))
    zone.SetMinThickness(mm(max(z["min_width"], 0.1524)))
    zone.SetThermalReliefGap(mm(z["thermal_gap"]))
    zone.SetThermalReliefSpokeWidth(mm(z["thermal_spoke"]))
    zone.SetPadConnection(z["pad_connection"])
    board.Add(zone)
    return zone


def on_board(board, fp):
    """Inside the outline and above the bracket strip (no parts there, D-026)."""
    box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    edge = board.GetBoardEdgesBoundingBox()
    strip = B.to_board(0, placement.STRIP_TOP_Z).y
    return edge.Contains(box.GetOrigin()) and edge.Contains(box.GetEnd()) and box.GetBottom() < strip


def place_near(board, fp, target):
    others = [f for f in board.GetFootprints() if f.GetReference() != fp.GetReference()]
    for ring in range(0, int(SEARCH_MM / 0.1) + 1):
        r = mm(0.1) * ring
        steps = max(1, int(2 * math.pi * ring))
        for k in range(steps):
            angle = 2 * math.pi * k / steps
            for rot in (0.0, 90.0, 180.0, 270.0):
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(target + pcbnew.VECTOR2I(int(r * math.cos(angle)), int(r * math.sin(angle))))
                if on_board(board, fp) and RF.spot_ok(board, fp, others):
                    return pcbnew.ToMM(r)
    sys.exit(f"no free spot for {fp.GetReference()} within {SEARCH_MM} mm")


def nudge_from_ties(board, vias, ties):
    """TI's vias next to the net ties keep 0.19 mm to the tie's copper bridge; JLCPCB wants 0.20 mm hole-to-copper.
    Move such a via straight away from the bridge, 0.005 mm at a time (the ties' copper isn't in rf_block's check)."""
    moved, worst = 0, 0.0
    shapes = [item for fp in ties for item in fp.GraphicalItems() if item.IsOnCopperLayer()]
    for via in vias:
        start = via.GetPosition()
        for _ in range(40):
            hit = next((s for s in shapes if via.GetEffectiveHoleShape().Collide(
                s.GetEffectiveShape(s.GetLayer()), mm(RF.HOLE_TO_COPPER))), None)
            if hit is None:
                break
            seg = pcbnew.SEG(hit.GetStart(), hit.GetEnd())
            away = via.GetPosition() - seg.NearestPoint(via.GetPosition())
            length = max(away.EuclideanNorm(), 1)
            via.SetPosition(via.GetPosition() + pcbnew.VECTOR2I(int(away.x * mm(0.005) / length),
                                                                 int(away.y * mm(0.005) / length)))
        shift = pcbnew.ToMM((via.GetPosition() - start).EuclideanNorm())
        if shift > 0:
            moved, worst = moved + 1, max(worst, shift)
    return moved, worst


def target_of(footprints, how):
    kind, ref, key = how
    fp = footprints[ref]
    if kind == "pads":
        pads = [p for p in fp.Pads() if p.GetNetname().rsplit("/", 1)[-1] == key]
    else:
        pads = [p for p in fp.Pads() if p.GetNumber() in key]
    return pcbnew.VECTOR2I(sum(p.GetPosition().x for p in pads) // len(pads),
                           sum(p.GetPosition().y for p in pads) // len(pads))


def reset_geometry(board, replace=False):
    """With `replace`, the pasted group's copper and zones out (its footprints stay); gathered first (pcbnew's SWIG
    lists break after a removal), apply() runs in the next child process."""
    groups = [g for g in board.Groups() if g.GetName() == GROUP] if replace else []
    members = [list(g.GetItems()) for g in groups]
    doomed = [i for items in members for i in items if i.GetClass() != "FOOTPRINT"]
    for group, items in zip(groups, members):
        for item in items:
            item.SetLocked(False)
            group.RemoveItem(item)
    for item in doomed + groups:
        board.Remove(item)


def has_group(board):
    return any(g.GetName() == GROUP for g in board.Groups())


def apply(board):
    net = RF.net_lookup(board)
    st_net = lambda name: net(DATA["net_map"][name])  # noqa: E731
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    park = B.to_board(placement.WIDTH, -40.0)
    for ref, _ in EXTRAS:
        footprints[ref].SetPosition(park)
    placed = []
    for part in DATA["parts"]:
        fp = footprints.get(part["ours"])
        if fp is None:
            sys.exit(f"{part['ours']} is not on the board: run board.py first")
        if part["ours"] == BULK:
            place_bulk(fp, part, net)
        else:
            if fp.GetFPIDAsString() != part["footprint"]:
                sys.exit(f"{part['ours']} has {fp.GetFPIDAsString()}, expected {part['footprint']}: update the schematic")
            place(fp, part, net)
        placed.append(fp)
    for fp in placed:
        group.AddItem(fp)

    for t in DATA["tracks"]:
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(to_ours(*t["start"]))
        track.SetEnd(to_ours(*t["end"]))
        track.SetWidth(mm(t["width"]))
        track.SetLayer(board.GetLayerID(LAYERS[t["layer"]]))
        track.SetNet(st_net(t["net"]))
        board.Add(track)
        group.AddItem(track)
    vias = []
    for v in DATA["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(to_ours(*v["at"]))
        via.SetWidth(mm(v["size"]))
        via.SetDrill(mm(v["drill"]))
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetNet(st_net(v["net"]))
        board.Add(via)
        group.AddItem(via)
        vias.append(via)
    nudged = RF.nudge_vias(board, vias)
    ties = [footprints[p["ours"]] for p in DATA["parts"] if p["ours"].startswith("NT")]
    tied = nudge_from_ties(board, vias, ties)
    nudged = (nudged[0] + tied[0], max(nudged[1], tied[1]))
    for z in DATA["zones"]:
        group.AddItem(add_pour(board, z, st_net(z["net"])))

    report = []
    RF.PART_CLEARANCE = EXTRA_CLEARANCE
    for ref, how in EXTRAS:
        fp = footprints[ref]
        report.append((ref, place_near(board, fp, target_of(footprints, how))))
        group.AddItem(fp)
        placed.append(fp)

    for item in group.GetItems():
        item.SetLocked(True)
    group.SetLocked(True)
    for fp in placed:
        B.label_fields(fp)
    silk.report(*silk.layout(board, check=False), check=False)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    x0, z1 = to_mech(_BOX[0], _BOX[1])
    x1, z0 = to_mech(_BOX[2], _BOX[3])
    print(f"pasted '{GROUP}': {len(DATA['parts'])} TI parts, {len(DATA['tracks'])} tracks, {len(vias)} vias "
          f"({nudged[0]} nudged by <= {nudged[1]:.3f} mm), {len(DATA['zones'])} pours; TI's box at mechanical "
          f"x {x0}..{x1}, z {z0}..{z1}")
    for ref in ("U501", "Q501", "Q504", BULK):
        fp = footprints[ref]
        print(f"{ref} at mechanical {RF.board_to_mech(fp.GetPosition())}, rotation {fp.GetOrientationDegrees():.0f}"
              f"{', B.Cu' if fp.IsFlipped() else ''}")
    for ref, distance in report:
        fp = footprints[ref]
        print(f"{ref} at mechanical {RF.board_to_mech(fp.GetPosition())}, {distance:.2f} mm from its target")
    return True


def stage(step, replace):
    board = pcbnew.LoadBoard(str(B.BOARD))
    if has_group(board) and not (replace and step == "reset"):
        print(f"'{GROUP}' is already on the board: nothing to do")
        sys.exit(3)
    if step == "reset":
        reset_geometry(board, replace)
    else:
        apply(board)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="paste the BOOST-DRV8711 power stage (one shot)")
    parser.add_argument("--replace", action="store_true",
                        help="remove the pasted group's copper and paste it again (after a change to the copy)")
    parser.add_argument("--pcbnew-stage", choices=["reset", "apply"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.pcbnew_stage, args.replace)
        return
    if not args.apply:
        parser.error("nothing to do without --apply")
    project = B.PROJECT.read_bytes()
    for step in ("reset", "apply"):
        result = subprocess.run([sys.executable, __file__, "--pcbnew-stage", step] + (["--replace"] if args.replace else []))
        B.PROJECT.write_bytes(project)
        if result.returncode == 3:
            return
        if result.returncode:
            sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
