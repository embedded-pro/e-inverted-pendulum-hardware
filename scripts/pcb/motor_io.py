#!/usr/bin/env python3
"""Place the motor connectors and encoder inputs at the side edges (owner, D-042).

One shot, on the owner's request: `python3 scripts/pcb/motor_io.py --apply`. It moves J601 / J602 (JST PH side entry,
plug toward the edge), their encoder chains (ESD, RC, Schmitt buffer, bypass, test pads), the encoder supply and its
test pads from the staging area to placement.motor_io() (each part's pad centre on its spot), and refuses if any part:
  - leaves the board, or its courtyard reaches into the bracket strip (no parts there, D-026);
  - puts a through-hole pin over the battery (BATTERY_BACK, D-025);
  - touches another part's courtyard, comes closer than rf_block.PART_CLEARANCE to another net's copper, or overlaps
    another silk outline (rf_block.spot_ok).
It locks J601 / J602 (the anchors) and lays the silkscreen labels out (silk.py, D-041). Re-running is a no-op once J601
is on the board. Run board.py first so the parts exist.
"""

import argparse
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402
import silk  # noqa: E402

ANCHORS = ("J601", "J602")


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
    if box.GetBottom() >= B.to_board(0.0, placement.STRIP_TOP_Z).y:
        found.append("courtyard reaches the bracket strip")
    battery = placement.BATTERY
    x0, x1 = B.to_board(battery["x0"] - 1, 0).x, B.to_board(battery["x1"] + 1, 0).x
    y0, y1 = B.to_board(0, battery["z1"] + 1).y, B.to_board(0, battery["z0"] - 1).y
    for pad in fp.Pads():
        p = pad.GetPosition()
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and x0 <= p.x <= x1 and y0 <= p.y <= y1:
            found.append(f"through-hole pin {pad.GetNumber()} over the battery")
    if not RF.spot_ok(board, fp, others):
        found.append("touches a courtyard, another net's copper or a silk outline")
    return found


def has_placed(board):
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    return all(outline_of(board).Contains(footprints[ref].GetPosition()) for ref in ANCHORS)


def apply(board):
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    parts = placement.motor_io()
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
        sys.exit("motor I/O not placed:\n  " + "\n  ".join(failed))
    for ref in ANCHORS:
        footprints[ref].SetLocked(True)
    silk.report(*silk.layout(board, check=False), check=False)
    for ref in ANCHORS:
        fp = footprints[ref]
        pins = sorted(fp.Pads(), key=lambda p: int(p.GetNumber()))
        print(f"{ref} at mechanical {RF.board_to_mech(fp.GetPosition())}, rotation {fp.GetOrientationDegrees():.0f}: "
              f"pin 1 {RF.board_to_mech(pins[0].GetPosition())}, pin 6 {RF.board_to_mech(pins[-1].GetPosition())}")
    print(f"placed {len(parts)} parts: J601 / J602 locked")


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    if has_placed(board):
        print("J601 / J602 are already on the board: nothing to do")
        sys.exit(3)
    apply(board)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="place the motor connectors and encoder inputs (one shot)")
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
