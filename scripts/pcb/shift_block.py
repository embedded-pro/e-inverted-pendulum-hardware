#!/usr/bin/env python3
"""Move a placed block of parts together with its copper, to a target set by its anchor part (owner, D-050).

    python3 scripts/pcb/shift_block.py --apply drive        the BOOST-DRV8711 stage and our extras beside it (D-050)
    python3 scripts/pcb/shift_block.py --apply motor_left   J601's chain and the encoder supply, to J601's table spot
    python3 scripts/pcb/shift_block.py --apply motor_right  J602's chain, to J602's table spot (D-052: 2.5 mm from the edge)

A block (BLOCKS) is a list of references in placement.py and the target of its anchor: the footprint position (drive),
or the centre of its pads as the placement tables hold it (the motor chains, whose tables place_block.py uses). The script
moves the parts, and every track and via that lies inside their courtyards' box (plus REACH) on one of their nets, by the
offset that puts the anchor on its target: copied routing stays with its parts, the owner's copper elsewhere stays put.
It refuses, before saving, if a moved courtyard touches a part that stays, moved copper comes within CLEARANCE of
copper that stays (other nets), a moved part breaks JLCPCB's assembly gap or edge distance (place_block, D-052), or
anything leaves the board. A second run finds the anchor on its target and changes
nothing. Nothing is locked (D-045); silk.py lays the labels out last.
"""

import argparse
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import place_block as P  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402
import silk  # noqa: E402

mm = pcbnew.FromMM
REACH = 1.0
CLEARANCE = 0.15
def _table_spot(table, ref):
    return next((x, z) for r, x, z, _ in table if r == ref)


BLOCKS = {
    "drive": (placement.DRIVE_REFS, "U501", placement.DRIVE_TARGET, "position"),
    "motor_left": (tuple(r for r, *_ in placement.MOTOR_IO_LEFT + placement.MOTOR_IO_SUPPLY), "J601",
                   _table_spot(placement.MOTOR_IO_LEFT, "J601"), "pads"),
    "motor_right": (tuple(r for r, *_ in placement.MOTOR_IO_RIGHT), "J602",
                    _table_spot(placement.MOTOR_IO_RIGHT, "J602"), "pads"),
}


def exact(x, z):
    return pcbnew.VECTOR2I(int(round((B.ORIGIN[0] + x) * 1e6)), int(round((B.ORIGIN[1] - z) * 1e6)))


def courtyards(fp):
    fp.BuildCourtyardCaches()
    found = []
    for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        court = fp.GetCourtyard(layer)
        if court.OutlineCount():
            found.append((layer, court))
    return found


def select(board, refs):
    parts = [fp for fp in board.GetFootprints() if fp.GetReference() in refs]
    missing = set(refs) - {fp.GetReference() for fp in parts}
    if missing:
        sys.exit(f"{', '.join(sorted(missing))} not on the board")
    box = pcbnew.BOX2I()
    for fp in parts:
        for _, court in courtyards(fp):
            box.Merge(court.BBox())
    box.Inflate(mm(REACH))
    nets = {pad.GetNetCode() for fp in parts for pad in fp.Pads() if pad.GetNetCode() > 0}
    copper = []
    for item in board.GetTracks():
        if item.GetNetCode() not in nets:
            continue
        ends = [item.GetPosition()] if item.GetClass() == "PCB_VIA" else [item.GetStart(), item.GetEnd()]
        if all(box.Contains(p) for p in ends):
            copper.append(item)
    return parts, copper


def problems(board, parts, copper):
    moved_ids = {fp.m_Uuid.AsString() for fp in parts} | {item.m_Uuid.AsString() for item in copper}
    staying = [fp for fp in board.GetFootprints() if fp.m_Uuid.AsString() not in moved_ids]
    found = []
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    for fp in parts:
        found += [f"{fp.GetReference()}: {why}" for why in P.assembly_problems(fp, staying, outline)]
        for layer, court in courtyards(fp):
            box = court.BBox()
            if not (outline.Contains(box.GetOrigin()) and outline.Contains(box.GetEnd())):
                found.append(f"{fp.GetReference()} leaves the board")
            for other in staying:
                for other_layer, other_court in courtyards(other):
                    if other_layer == layer and court.Collide(other_court, 0):
                        found.append(f"{fp.GetReference()} touches {other.GetReference()}'s courtyard")
    moving = [pad for fp in parts for pad in fp.Pads()] + copper
    fixed = [pad for fp in staying for pad in fp.Pads()]
    fixed += [item for item in board.GetTracks() if item.m_Uuid.AsString() not in moved_ids]
    layers = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
    for item in moving:
        near = [o for o in fixed if o.GetNetCode() != item.GetNetCode()
                and (o.GetPosition() - item.GetPosition()).EuclideanNorm() < mm(6)]
        for other in near:
            for layer in layers:
                if item.IsOnLayer(layer) and other.IsOnLayer(layer) and \
                        item.GetEffectiveShape(layer).Collide(other.GetEffectiveShape(layer), mm(CLEARANCE)):
                    found.append(f"{item.GetClass()} {item.GetNetname()} at {RF.board_to_mech(item.GetPosition())} "
                                 f"comes within {CLEARANCE} mm of {other.GetNetname()}")
                    break
    return sorted(set(found))


def pads_centre(fp):
    pads = pcbnew.BOX2I()
    for pad in fp.Pads():
        pads.Merge(pad.GetBoundingBox())
    return pads.GetCenter()


def stage(name):
    board = pcbnew.LoadBoard(str(B.BOARD))
    refs, anchor, target, kind = BLOCKS[name]
    parts, copper = select(board, refs)
    anchor_fp = next(fp for fp in parts if fp.GetReference() == anchor)
    here = anchor_fp.GetPosition() if kind == "position" else pads_centre(anchor_fp)
    delta = (exact(*target) if kind == "position" else B.to_board(*target)) - here
    if delta.x == 0 and delta.y == 0:
        print(f"{anchor} is on its target: nothing to do")
        sys.exit(3)
    for fp in parts:
        fp.Move(delta)
    for item in copper:
        item.Move(delta)
    found = problems(board, parts, copper)
    if found:
        sys.exit(f"{name} not moved:\n  " + "\n  ".join(found))
    silk.report(*silk.layout(board, check=False), check=False)
    pcbnew.SaveBoard(str(B.BOARD), board)
    tracks = sum(1 for item in copper if item.GetClass() != "PCB_VIA")
    print(f"{name}: {len(parts)} parts, {tracks} tracks and {len(copper) - tracks} vias moved by "
          f"({pcbnew.ToMM(delta.x):+.3f}, {-pcbnew.ToMM(delta.y):+.3f}) mm; {anchor} at {RF.board_to_mech(anchor_fp.GetPosition())}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", choices=sorted(BLOCKS), help="the block to move to its target")
    parser.add_argument("--pcbnew-stage", choices=sorted(BLOCKS), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.pcbnew_stage)
        return
    if not args.apply:
        parser.error("nothing to do without --apply <block>")
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage", args.apply])
    B.PROJECT.write_bytes(project)
    if result.returncode == 3:
        return
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
