#!/usr/bin/env python3
"""Paste the NFC corner of ST's X-NUCLEO-NFC01A1 (MB1163 rev C-01) onto our board, as ST laid it out (D-039).

One shot, on the owner's request: `python3 scripts/pcb/nfc_block.py --apply`. It reads scripts/pcb/mb1163_nfc.json
(made by scripts/nfc_reference.py, derived from STMicroelectronics MB1163 rev C-01, www.st.com/opla) and:
  - redraws the outline from placement.py (right of NFC_STEP_X the top edge is back at 117.5), retires the old
    NFC_COIL_KEEPOUT rule area and adds NFC_COIL (no tracks, vias or pour in or near the coil) and NFC_POUR_GAP (ST's
    coil-to-pour clearance: no pour or vias);
  - places AE801 (ANT14) and the tag cluster as ST has them, turned by placement.NFC_TURN (placement.from_mb1163): the
    coil in the top-right corner, the cluster beside it. Every pad lands on ST's pad of the same net;
  - copies ST's cluster tracks and vias, and ST's GND pour cut to the cluster (its thermal-relief settings are an
    ASSUMPTION: ST's Gerbers don't carry them);
  - nudges any via whose hole is closer than JLCPCB's 0.20 mm to other-net copper (rf_block.nudge_vias);
  - groups it all as "MB1163 NFC corner" (unlocked: locking is the owner's, D-045): move or rotate the group as one unit;
  - lays the silkscreen labels out (silk.py, D-041).
Re-running is a no-op once the group exists; --replace removes the group's copper and pastes it again (the group is
generated, not hand-edited). Run board.py first so the parts and nets exist.
"""

import argparse
import json
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import silk  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402

DATA = json.loads((pathlib.Path(__file__).resolve().parent / "mb1163_nfc.json").read_text(encoding="utf-8"))
GROUP = B.NFC_CORNER_GROUP
RULE_AREAS = {"NFC_COIL_KEEPOUT", "NFC_COIL", "NFC_POUR_GAP"}
POUR = {"clearance": DATA["st_rules_mm"]["GND-TOP"], "min_width": DATA["st_rules_mm"]["Width"],
        "thermal_gap": 0.3, "thermal_spoke": 0.4}

mm = pcbnew.FromMM


def to_ours(x, y):
    return B.to_board(*placement.from_mb1163(x, y))


def place(fp, part, net):
    """ST's position and rotation turned 180 degrees, or 180 more when our pin numbers run the other way round: every
    listed pad must land on ST's pad of the same net."""
    fp.SetPosition(to_ours(*part["at"]))
    wanted = [(to_ours(x, y), net(DATA["net_map"][st_net]).GetNetCode()) for _, x, y, st_net in part["pads"]]
    for extra in (placement.NFC_TURN, placement.NFC_TURN + 180.0):
        fp.SetOrientationDegrees((part["rot"] + extra) % 360.0)
        if all(any((pad.GetPosition() - target).EuclideanNorm() < mm(0.01) and pad.GetNetCode() == code
                   for pad in fp.Pads()) for target, code in wanted):
            return
    sys.exit(f"{fp.GetReference()}: no orientation puts its pads on MB1163 {part['st']}'s pads with the same nets")


def chain(points):
    shape = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in points:
        shape.Append(to_ours(x, y))
    shape.SetClosed(True)
    return shape


def add_pour(board, layer, polygons, gnd):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(board.GetLayerID(layer))
    for polygon in polygons:
        zone.Outline().AddOutline(chain(polygon))
    zone.SetNet(gnd)
    zone.SetZoneName(f"MB1163 {layer} GND")
    zone.SetLocalClearance(mm(POUR["clearance"]))
    zone.SetMinThickness(mm(POUR["min_width"]))
    zone.SetThermalReliefGap(mm(POUR["thermal_gap"]))
    zone.SetThermalReliefSpokeWidth(mm(POUR["thermal_spoke"]))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    board.Add(zone)
    return zone


def reset_geometry(board, replace=False):
    """Old outline, drawings and the NFC rule areas out; with `replace`, the pasted group's copper and zones too (its
    footprints stay). Everything is gathered before anything is removed (pcbnew's SWIG lists break after a removal),
    and apply() runs in the next child process."""
    drawings = [item for item in board.GetDrawings() if item.GetLayer() in (pcbnew.Edge_Cuts, pcbnew.Dwgs_User)]
    areas = [zone for zone in board.Zones() if zone.GetIsRuleArea() and zone.GetZoneName() in RULE_AREAS]
    groups = [g for g in board.Groups() if g.GetName() == GROUP] if replace else []
    members = [list(g.GetItems()) for g in groups]
    doomed = [i for items in members for i in items if i.GetClass() != "FOOTPRINT"]
    for group, items in zip(groups, members):
        for item in items:
            item.SetLocked(False)
            group.RemoveItem(item)
    for item in drawings + areas + doomed + groups:
        board.Remove(item)


def has_group(board):
    return any(g.GetName() == GROUP for g in board.Groups())


def apply(board):
    B.ensure_outline(board)
    B.ensure_rule_areas(board)
    B.ensure_drawings(board)
    net = RF.net_lookup(board)
    st_net = lambda name: net(DATA["net_map"][name])  # noqa: E731
    group = pcbnew.PCB_GROUP(board)
    group.SetName(GROUP)
    board.Add(group)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    placed = []
    for part in DATA["parts"] + [DATA["antenna"]]:
        fp = footprints.get(part["ours"])
        if fp is None:
            sys.exit(f"{part['ours']} is not on the board: run board.py first")
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
        track.SetLayer(board.GetLayerID(t["layer"]))
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
    gnd = st_net(DATA["pour_net"])
    for layer, polygons in DATA["pour"].items():
        if polygons:
            group.AddItem(add_pour(board, layer, polygons, gnd))

    for fp in placed:
        B.label_fields(fp)
    silk.report(*silk.layout(board, check=False), check=False)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    coil = placement.NFC_COIL_BOX
    print(f"pasted '{GROUP}': {len(placed)} footprints, {len(DATA['tracks'])} tracks, {len(vias)} vias "
          f"({nudged[0]} nudged by <= {nudged[1]:.3f} mm), GND pour on {', '.join(DATA['pour'])}")
    print(f"ANT14 copper at mechanical x {coil[0]}..{coil[2]}, z {coil[1]}..{coil[3]}: "
          f"{coil[1] - placement.BATTERY['z1']:.1f} mm above the battery, "
          f"{coil[0] - placement.TAB_OUTLINE[-1][0]:.1f} mm right of the MB1355 tab's foot; top edge back at "
          f"z {placement.TOP_Z} right of x {placement.NFC_STEP_X}")
    for ref in ("U803", "AE801"):
        fp = footprints[ref]
        print(f"{ref} at mechanical {RF.board_to_mech(fp.GetPosition())}, rotation {fp.GetOrientationDegrees():.0f}")
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
    parser.add_argument("--apply", action="store_true", help="paste the MB1163 NFC corner (one shot)")
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
