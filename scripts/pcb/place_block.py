#!/usr/bin/env python3
"""Place a block of parts at the owner's chosen spots, once (D-042, D-043, D-047, D-049, D-050).

    python3 scripts/pcb/place_block.py --apply motor_io      J601 / J602 at the side edges, their encoder chains and the
                                                            encoder supply (D-042, D-044)
    python3 scripts/pcb/place_block.py --apply imu_memory    the IMU on the centre line, the flash and the EEPROM left of
                                                            the MCU, with their support parts (D-043)
    python3 scripts/pcb/place_block.py --apply power         the TPS62933F buck and the TLV75533P LDO right of the power
                                                            entry, to TI's layout guidance (D-049)
    python3 scripts/pcb/place_block.py --apply leds          the 12 RGB LEDs as two square rings in the centre, their
                                                            caps, the chain's driver and the status LED (D-050)

Each block is a list from placement.py of (ref, x, z, rotation): mechanical, at the centre of the footprint's pads. The
tables hold the owner's positions from KiCad (D-047), so --replace on the owner's board changes nothing; the parts the
owner parked off the board (placement.*_PARKED) are not in them and stay where they are. The parts move to their spots,
and the script refuses if any part:
  - leaves the board, or its courtyard reaches into the bracket strip (no parts there, D-026);
  - puts a through-hole pin over the battery (BATTERY_BACK, D-025), except the parts the cradle has a relief for
    (placement.BATTERY_RELIEF, D-044, D-047);
  - touches another part's courtyard, comes closer than rf_block.PART_CLEARANCE to another net's copper, or overlaps
    another silk outline (rf_block.spot_ok).
It lays the silkscreen labels out (silk.py, D-041) and locks nothing: locking is the owner's (D-045). Re-running is a
no-op once the block's anchors are on the board; --replace moves an already placed block to its table again (after the owner changes it).
Run board.py first so the parts exist.
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

BLOCKS = {
    "motor_io": (placement.motor_io, ("J601", "J602")),
    "imu_memory": (placement.imu_memory, ("U701",)),
    "power": (placement.power, ("U201",)),
    "leds": (placement.leds, ("D802",)),
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
