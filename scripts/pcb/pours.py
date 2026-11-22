#!/usr/bin/env python3
"""The pours: the solid L2 ground plane, ST's RF-strip copper and TI's drive copper, with their rule areas (D-053).

    python3 scripts/pcb/pours.py --apply

The owner removed the pours (D-046) and the board's rule areas (D-047) until the pours came back. This puts back:
  - the board's rule areas (board.ensure_rule_areas, placement.RULE_AREAS): ANTENNA_TAB, NFC_COIL, NFC_POUR_GAP and
    BATTERY_BACK, which keep pours, vias and through-hole pins where D-025, D-037 and D-039 want them;
  - MB1355's L2 cut-out under the RF line (mb1355_rf.json), so the line references L3 as on ST's board (D-037, D-038);
  - ST's RF-strip pours from mb1355_rf.json, with ST's settings: the F.Cu ground beside the line (the line is coplanar,
    0.6 / 0.2 mm, docs/rf.md), the F.Cu RF_50 patch at FL401, the In2.Cu ground the line references and the B.Cu ground
    (ST's In1.Cu ground is the plane below);
  - ST's MB1163 B.Cu GND pour cut to the NFC cluster (mb1163_nfc.json, nfc_block.add_pour, D-039), which ties the
    cluster's ground and its stitching vias (ST's F.Cu patch, 1.5 mm2, would reach one pad only on this board: left out,
    NFC_POUR_LAYERS);
  - TI's BOOST-DRV8711 pours from boost_drv8711.json, with TI's settings (drv_block.add_pour's): the F.Cu VBAT, phase,
    sense and GND pours and the B.Cu VBAT and GND pours that carry the bridges' current (D-040), moved by the offset
    the stage has moved since drv_block pasted it (the owner's 2.85 mm, D-047, and shift_block's 8 mm, D-050);
  - L2_GND: one GND pour on In1.Cu over the whole outline, solid as CLAUDE.md asks (L2 is never cut but by the RF
    cut-out and the NFC keep-outs, which the rule areas carve out), so every GND via reaches ground.
Each pour is added once, by name; then every zone is filled, with islands removed. Re-running is a no-op once every
pour is there. Nothing is locked (D-045).
"""

import argparse
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import drv_block as D  # noqa: E402
import nfc_block as N  # noqa: E402
import rf_block as RF  # noqa: E402

mm = pcbnew.FromMM
PLANE = "L2_GND"
NFC_POUR_LAYERS = ("B.Cu",)
# The plane's settings: the board's design clearance (pcb-design-rules design value 0.15 mm) raised to the RF class's
# 0.2 mm so the plane keeps the RF class's gap everywhere; 0.25 mm minimum width (ST's, mb1355_rf.json); through-hole
# pins on thermal spokes (hand-soldered parts: J101, J601 / J602, SW101), vias solid.
PLANE_CLEARANCE = 0.2
PLANE_MIN_WIDTH = 0.25
THERMAL_GAP = 0.3
THERMAL_SPOKE = 0.5


def st_zone_name(zone):
    return f"MB1355 {zone['layer']} {RF.DATA['net_map'][zone['net']]}"


def plane(board, gnd):
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    zone = pcbnew.ZONE(board)
    zone.SetLayer(pcbnew.In1_Cu)
    zone.SetNet(gnd)
    zone.SetZoneName(PLANE)
    zone.SetAssignedPriority(0)
    for i in range(outline.OutlineCount()):
        zone.Outline().AddOutline(outline.Outline(i))
    zone.SetLocalClearance(mm(PLANE_CLEARANCE))
    zone.SetMinThickness(mm(PLANE_MIN_WIDTH))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    zone.SetThermalReliefGap(mm(THERMAL_GAP))
    zone.SetThermalReliefSpokeWidth(mm(THERMAL_SPOKE))
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(zone)
    return zone


def drive_offset(board):
    """How far the drive stage has moved since drv_block pasted it: U501 against TI's spot (translations only)."""
    u501 = next(fp for fp in board.GetFootprints() if fp.GetReference() == "U501")
    part = next(p for p in D.DATA["parts"] if p["ours"] == "U501")
    return u501.GetPosition() - D.to_ours(*part["at"])


def nfc_offset(board):
    """How far the NFC copy has moved since nfc_block pasted it: U803 against ST's spot (translations only)."""
    u803 = next(fp for fp in board.GetFootprints() if fp.GetReference() == "U803")
    part = next(p for p in N.DATA["parts"] if p["ours"] == "U803")
    return u803.GetPosition() - N.to_ours(*part["at"])


def nfc_pours(board, names):
    gnd = RF.net_lookup(board)(N.DATA["pour_net"])
    added = []
    for layer, polygons in N.DATA["pour"].items():
        name = f"MB1163 {layer} GND"
        if name in names or layer not in NFC_POUR_LAYERS:
            continue
        zone = N.add_pour(board, layer, polygons, gnd)
        zone.Move(nfc_offset(board))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        added.append(name)
    return added


def drive_pour_name(board, z):
    return f"BOOST-DRV8711 {D.LAYERS[z['layer']]} {D.DATA['net_map'][z['net']]} {z['priority']}"


def drive_pours(board, names):
    nets = RF.net_lookup(board)
    offset = drive_offset(board)
    added = []
    for z in D.DATA["zones"]:
        name = drive_pour_name(board, z)
        if name in names:
            continue
        zone = D.add_pour(board, z, nets(D.DATA["net_map"][z["net"]]))
        zone.Move(offset)
        zone.SetZoneName(name)
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        added.append(name)
    return added


def wanted(board):
    names = [st_zone_name(z) for z in RF.DATA["zones"] if z["layer"] != "In1.Cu"]
    names += [drive_pour_name(board, z) for z in D.DATA["zones"]] + [PLANE]
    names += [f"MB1163 {layer} GND" for layer in NFC_POUR_LAYERS]
    names += [area["name"] for area in B.placement.RULE_AREAS]
    names += [rule["name"] for rule in RF.DATA["rule_areas"] if rule["layers"] == ["In1.Cu"]]
    return names


def apply(board):
    names = {zone.GetZoneName() for zone in board.Zones()}
    if all(name in names for name in wanted(board)):
        print("every pour and its rule areas are on the board: nothing to do")
        sys.exit(3)
    added = []
    rule_names = {zone.GetZoneName() for zone in board.Zones() if zone.GetIsRuleArea()}
    B.ensure_rule_areas(board)
    added += sorted({zone.GetZoneName() for zone in board.Zones() if zone.GetIsRuleArea()} - rule_names)
    for rule in RF.DATA["rule_areas"]:
        if rule["name"] not in names and rule["layers"] == ["In1.Cu"]:
            RF.add_zone(board, board.GetLayerID(rule["layers"][0]), [rule["polygon"]], rule=rule)
            added.append(rule["name"])
    nets = RF.net_lookup(board)
    for z in RF.DATA["zones"]:
        if z["layer"] == "In1.Cu" or st_zone_name(z) in names:
            continue
        zone = RF.add_zone(board, board.GetLayerID(z["layer"]), z["polygons"], net=nets(RF.DATA["net_map"][z["net"]]),
                           priority=z["priority"], settings=z)
        zone.SetZoneName(st_zone_name(z))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        added.append(st_zone_name(z))
    added += nfc_pours(board, names)
    added += drive_pours(board, names)
    if PLANE not in names:
        plane(board, board.FindNet("GND"))
        added.append(PLANE)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for name in added:
        print(f"added {name}")


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    apply(board)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="add the pours and their rule areas, fill (one shot)")
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
