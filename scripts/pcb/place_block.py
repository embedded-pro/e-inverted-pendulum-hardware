#!/usr/bin/env python3
"""Place a block of parts at the owner's chosen spots, once (D-042, D-043, D-047, D-049, D-050, D-051).

    python3 scripts/pcb/place_block.py --apply motor_io      J601 / J602 at the side edges, their encoder chains and the
                                                            encoder supply (D-042, D-044)
    python3 scripts/pcb/place_block.py --apply imu_memory    the IMU on the centre line, the flash and the EEPROM left of
                                                            the MCU, with their support parts (D-043)
    python3 scripts/pcb/place_block.py --apply power         the TPS62933F buck and the TLV75533P LDO right of the power
                                                            entry, to TI's layout guidance (D-049)
    python3 scripts/pcb/place_block.py --apply power_entry   J101 (XT30), the fuse, Q101 and their parts at the left edge,
                                                            the owner's arrangement (D-047), J101 2.5 mm from the edge (D-052)
    python3 scripts/pcb/place_block.py --apply leds          the 12 RGB LEDs as two square rings in the centre, their
                                                            caps, the chain's driver and the status LED (D-050)
    python3 scripts/pcb/place_block.py --apply rest          the rest: the power switch and the Qwiic port at the left
                                                            edge, the support parts at their pins and the test pads in
                                                            rows per block (D-051)

Each block is a list from placement.py of (ref, x, z, rotation): mechanical, at the centre of the footprint's pads. The
tables hold the owner's positions from KiCad (D-047), so --replace on the owner's board changes nothing; parts not in a
table (the mechanical holes MC1-MC4 and MH1 / MH2) stay where they are. The parts move to their spots,
and the script refuses if any part:
  - leaves the board, or its courtyard reaches into the bracket strip (no parts there, D-026);
  - puts a through-hole pin over the battery (BATTERY_BACK, D-025), except the parts the cradle has a relief for
    (placement.BATTERY_RELIEF, D-044, D-047);
  - touches another part's courtyard, comes closer than rf_block.PART_CLEARANCE to another net's copper, or overlaps
    another silk outline (rf_block.spot_ok);
  - opens solder mask under another part's silkscreen outline, or lays its outline over another part's pad (DRC
    silk_over_copper: the fab would clip the silk);
  - comes within ASSEMBLY_GAP of another part, body or pads, or puts its body within EDGE_GAP of the board edge
    (assembly_problems, D-052).
It lays the silkscreen labels out (silk.py, D-041) and locks nothing: locking is the owner's (D-045). Re-running is a
no-op once the block's anchors are on the board; --replace moves an already placed block to its table again (after the owner changes it).
Run board.py first so the parts exist.
"""

import argparse
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402
import silk  # noqa: E402

SILK_TO_MASK = 0.0
# JLCPCB assembly (Terms and Conditions of JLCPCB Assembly Service, s2 Notes on DFM, checked 2026-11-16): footprints and
# placement to IPC-7351B medium or low density, "high density is not supported" (item 1); the components' bodies 2.5 mm
# or more from the board edge (item 3). IPC-7351B density level B (nominal) keeps a 0.25 mm courtyard excess round each
# part's pads and body, so neighbours keep 0.5 mm between them (D-052).
ASSEMBLY_GAP = 0.5
EDGE_GAP = 2.5
GAP_TOLERANCE = 0.0005
# Package bodies, from the parts' datasheets, for footprints that draw none on F.Fab (long side, short side; the long
# side lies along the pads' longer extent).
BODY_MM = {
    "MB1355_NX2016_4P": (2.0, 1.6),
    "MB1355_NX2012_2P": (2.0, 1.2),
    "MB1355_ST_CSP650x58P2x3_160x100x42": (1.6, 1.0),
    "MB1355_0805_COIL": (2.0, 1.25),
    "MB1355_0402_CAP_NPOL": (1.0, 0.5),
    "MB1355_0402_RES": (1.0, 0.5),
    "MB1355_0402_COIL": (1.0, 0.5),
    "MB1355_IND_0402_MURATA_LQW15AN_H0P5": (1.0, 0.5),
    "BOOST_R-PDSO-G38": (9.7, 4.4),
}
BLOCKS = {
    "motor_io": (placement.motor_io, ("J601", "J602")),
    "imu_memory": (placement.imu_memory, ("U701",)),
    "power": (placement.power, ("U201",)),
    "power_entry": (placement.power_entry, ("J101",)),
    "leds": (placement.leds, ("D802",)),
    "rest": (placement.rest, ("SW101",)),
}


def outline_of(board):
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    return outline


def problems(board, fp, outline, others):
    found = []
    fp.BuildCourtyardCaches()
    box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    corners = [pcbnew.VECTOR2I(x, y) for x in (box.GetLeft(), box.GetRight()) for y in (box.GetTop(), box.GetBottom())]
    if not all(outline.Contains(c) for c in corners):
        found.append("courtyard leaves the board")
    relief = fp.GetReference() in placement.BATTERY_RELIEF
    if box.GetBottom() >= B.to_board(0.0, placement.STRIP_TOP_Z).y:
        found.append("courtyard reaches the bracket strip")
    battery = placement.BATTERY
    x0, x1 = B.to_board(battery["x0"] - 1, 0).x, B.to_board(battery["x1"] + 1, 0).x
    y0, y1 = B.to_board(0, battery["z1"] + 1).y, B.to_board(0, battery["z0"] - 1).y
    for pad in fp.Pads():
        p = pad.GetPosition()
        if not relief and pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and x0 <= p.x <= x1 and y0 <= p.y <= y1:
            found.append(f"through-hole pin {pad.GetNumber()} over the battery")
    if not RF.spot_ok(board, fp, others):
        found.append("touches a courtyard, another net's copper or a silk outline")
    found += mask_under_silk(fp, others)
    found += assembly_problems(fp, others, outline)
    return found


def is_test_pad(fp):
    return fp.GetFPIDAsString().startswith("TestPoint:")


def assembled(fp):
    """A part JLCPCB places, fitted now or later (DNP parts count): not board-only, not left out of the BOM (antennas,
    net ties and holes are copper or holes, not parts). A test pad is bare copper: it counts by its pads only."""
    attributes = fp.GetAttributes()
    if is_test_pad(fp):
        return True
    return not attributes & (pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_BOARD_ONLY)


_BODIES = {}


def body(fp):
    """The part's pads and its package body (the F.Fab outline's box, or BODY_MM), as polygons."""
    key = (fp.GetReference(), fp.GetPosition().x, fp.GetPosition().y, fp.GetOrientationDegrees(), fp.IsFlipped())
    if key in _BODIES:
        return _BODIES[key]
    poly = pcbnew.SHAPE_POLY_SET()
    error = pcbnew.FromMM(0.005)
    for pad in fp.Pads():
        layer = pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        pad.TransformShapeToPolygon(poly, layer, 0, error, pcbnew.ERROR_OUTSIDE)
    fab_layer = pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab
    fab = pcbnew.BOX2I()
    for item in fp.GraphicalItems():
        if item.GetLayer() == fab_layer and item.GetClass() == "PCB_SHAPE":
            fab.Merge(item.GetBoundingBox())
    corners = []
    if fab.GetWidth() > 0 and fab.GetHeight() > 0:
        corners = [(fab.GetLeft(), fab.GetTop()), (fab.GetRight(), fab.GetTop()), (fab.GetRight(), fab.GetBottom()),
                   (fab.GetLeft(), fab.GetBottom())]
    elif fp.GetFPID().GetLibItemName().wx_str() in BODY_MM and not is_test_pad(fp):
        long_side, short_side = (pcbnew.FromMM(v) for v in BODY_MM[fp.GetFPID().GetLibItemName().wx_str()])
        angle = math.radians(fp.GetOrientationDegrees())
        origin = fp.GetPosition()
        local = []
        for pad in fp.Pads():
            d = pad.GetPosition() - origin
            local.append((d.x * math.cos(angle) - d.y * math.sin(angle), d.x * math.sin(angle) + d.y * math.cos(angle)))
        xs, ys = [p[0] for p in local], [p[1] for p in local]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        w, h = (long_side, short_side) if max(xs) - min(xs) >= max(ys) - min(ys) else (short_side, long_side)
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            lx, ly = cx + sx * w / 2, cy + sy * h / 2
            corners.append((origin.x + lx * math.cos(angle) + ly * math.sin(angle),
                            origin.y - lx * math.sin(angle) + ly * math.cos(angle)))
    if corners:
        poly.NewOutline()
        for x, y in corners:
            poly.Append(int(round(x)), int(round(y)))
    poly.Simplify()
    _BODIES[key] = poly
    return poly


def gap_problem(fp, other):
    """True when the two parts' bodies or pads come within ASSEMBLY_GAP; two test pads are bare copper, never a pair."""
    if not assembled(other) or (is_test_pad(fp) and is_test_pad(other)):
        return False
    a, b = body(fp), body(other)
    if not a.OutlineCount() or not b.OutlineCount():
        return False
    reach = a.BBox()
    reach.Inflate(pcbnew.FromMM(ASSEMBLY_GAP))
    if not reach.Intersects(b.BBox()):
        return False
    return a.Collide(b, pcbnew.FromMM(ASSEMBLY_GAP - GAP_TOLERANCE))


def edge_problem(fp, outline):
    """True when an assembled part's body (not a test pad) comes within EDGE_GAP of the board edge."""
    if is_test_pad(fp) or not assembled(fp):
        return False
    inner = pcbnew.SHAPE_POLY_SET(outline)
    inner.Deflate(pcbnew.FromMM(EDGE_GAP - GAP_TOLERANCE), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, pcbnew.FromMM(0.005))
    rest = pcbnew.SHAPE_POLY_SET(body(fp))
    rest.BooleanSubtract(inner)
    return not rest.IsEmpty()


def assembly_problems(fp, others, outline):
    """JLCPCB's assembly rules for a part on the board: ASSEMBLY_GAP to every other part, EDGE_GAP to the edge (D-052)."""
    if not assembled(fp):
        return []
    found = [f"within {ASSEMBLY_GAP} mm of {other.GetReference()}" for other in others
             if other.GetReference() != fp.GetReference() and gap_problem(fp, other)]
    if edge_problem(fp, outline):
        found.append(f"body within {EDGE_GAP} mm of the board edge")
    return found


def mask_opening(pad):
    opening = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(opening, pcbnew.F_Mask, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_OUTSIDE)
    return opening


def mask_under_silk(fp, others):
    """A pad's mask opening within SILK_TO_MASK of another part's silkscreen outline, or this part's outline over another
    part's pad (DRC silk_over_copper: the fab clips the silk)."""
    reach = fp.GetBoundingBox()
    reach.Inflate(pcbnew.FromMM(1.0))
    near = [o for o in others if not o.IsFlipped() and reach.Intersects(o.GetBoundingBox())]
    found = []
    own = RF.silk_outline(fp)
    for other in near:
        silk = RF.silk_outline(other)
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.F_Mask) and silk.OutlineCount() and \
                    silk.Collide(mask_opening(pad), pcbnew.FromMM(SILK_TO_MASK)):
                found.append(f"pad {pad.GetNumber()} under {other.GetReference()}'s silkscreen")
        for pad in other.Pads():
            if pad.IsOnLayer(pcbnew.F_Mask) and own.OutlineCount() and \
                    own.Collide(mask_opening(pad), pcbnew.FromMM(SILK_TO_MASK)):
                found.append(f"silkscreen over {other.GetReference()} pad {pad.GetNumber()}")
    return found


def has_placed(board, anchors):
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    return all(outline_of(board).Contains(footprints[ref].GetPosition()) for ref in anchors)


def apply(board, name):
    parts_of, anchors = BLOCKS[name]
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    parts = parts_of()
    missing = [ref for ref, *_ in parts if ref not in footprints]
    if missing:
        sys.exit(f"{', '.join(missing)} not on the board: run board.py first")
    for ref, x, z, rotation in parts:
        fp = footprints[ref]
        fp.SetLocked(False)
        fp.SetOrientationDegrees(rotation)
        fp.SetPosition(B.to_board(x, z))
        pads = pcbnew.BOX2I()
        for pad in fp.Pads():
            pads.Merge(pad.GetBoundingBox())
        fp.Move(B.to_board(x, z) - pads.GetCenter())
    outline = outline_of(board)
    failed = []
    for ref, *_ in parts:
        fp = footprints[ref]
        others = [f for f in board.GetFootprints() if f.GetReference() != ref]
        failed += [f"{ref}: {why}" for why in problems(board, fp, outline, others)]
    if failed:
        sys.exit(f"{name} not placed:\n  " + "\n  ".join(failed))
    silk.report(*silk.layout(board, check=False), check=False)
    for ref in anchors:
        fp = footprints[ref]
        print(f"{ref} at mechanical {RF.board_to_mech(fp.GetPosition())}, rotation {fp.GetOrientationDegrees():.0f}")
    print(f"placed {len(parts)} parts")


def stage(name, replace):
    board = pcbnew.LoadBoard(str(B.BOARD))
    anchors = BLOCKS[name][1]
    if has_placed(board, anchors) and not replace:
        print(f"{' / '.join(anchors)} already on the board: nothing to do")
        sys.exit(3)
    apply(board, name)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", choices=sorted(BLOCKS), help="the block to place (one shot)")
    parser.add_argument("--replace", action="store_true", help="move an already placed block to its table again")
    parser.add_argument("--pcbnew-stage", choices=sorted(BLOCKS), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.pcbnew_stage, args.replace)
        return
    if not args.apply:
        parser.error("nothing to do without --apply <block>")
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage", args.apply] + (["--replace"] if args.replace else []))
    B.PROJECT.write_bytes(project)
    if result.returncode == 3:
        return
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
