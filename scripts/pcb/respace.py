#!/usr/bin/env python3
"""Keep JLCPCB's assembly spacing: 0.5 mm between neighbouring parts, 2.5 mm from a part's body to the edge (D-052).

    python3 scripts/pcb/respace.py --check    list every pair closer than place_block.ASSEMBLY_GAP and every body
                                              within place_block.EDGE_GAP of the edge; exit 1 on any
    python3 scripts/pcb/respace.py --apply    move the parts that break them, by the smallest step (one shot)

The rules and the body of a part (its pads plus its F.Fab outline, or its datasheet size in place_block.BODY_MM) are
place_block's: JLCPCB's assembly terms (IPC-7351B medium density, 2.5 mm to the edge). --apply fixes the parts that no
placement.py table holds (the owner's, the MCU decoupling, the drive extras and the vendor copies' parts; a table part
is fixed by changing its table). In each pair the more movable part moves (MOBILITY: passives, then diodes, then
crystals; ICs, connectors, FETs, the IPD and table parts stay), along x or z, in STEP increments up to MAX_MOVE, the
shortest move that clears every gap of that part first. A track that ends on one of its pads moves its end with it,
unless the end is still on the moved pad, so a move is only taken along that track's direction (the copied routing
keeps its 45-degree geometry); a via in a pad,
or a track crossing a pad, must stay on it; a vendor's via under a pad stays where it is. A part with no copper of its
own that no straight move frees takes the nearest spot on a SPOT_STEP grid within MAX_SPOT, in any of four rotations;
so does one of our own parts that only sits on a vendor's copper of its net (the drive extras placed over TI's routing):
that copper stays, and the part is left for the owner to route.
A part with copper that no move frees may push one movable neighbour out of its way by that neighbour's own
shortest move (one level deep). A move is refused when it adds any problem place_block reports (courtyards, silk, battery, edge) or brings its copper
closer to another net than the board's rules allow (rule_clearance: ST's 0.1 mm on the RF / SMPS / HSE nets, TI's
0.178 mm on the DRV8711's, the net classes elsewhere). An edge part moves inward along the edge's normal.
Nothing is locked (D-045); silk.py lays the labels out last. A second run finds nothing to move.
"""

import argparse
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import place_block as P  # noqa: E402
import placement  # noqa: E402
import silk  # noqa: E402

mm = pcbnew.FromMM
STEP = 0.05
MAX_MOVE = 1.5
SPOT_STEP = 0.1
MAX_SPOT = 3.5
PUSH_TRIES = 12
HOLE_TO_COPPER = 0.2
CLASS_CLEARANCE = {"Default": B.DEFAULT_CLASS["clearance"], **{name: spec["clearance"] for name, spec in B.NET_CLASSES.items()}}
PARALLEL = 1e-6
MOBILITY = (("C", 0), ("R", 0), ("FB", 0), ("L", 0), ("D", 1), ("Y", 2))
TABLES = (placement.motor_io, placement.imu_memory, placement.power, placement.power_entry, placement.leds,
          placement.rest)


def vendor_refs():
    """The parts of the three vendor copies (D-037, D-039, D-040): their copper is the vendor's routing to them."""
    import drv_block
    import nfc_block
    import rf_block
    return ({part["ours"] for part in rf_block.DATA["parts"]} | {part["ours"] for part in nfc_block.DATA["parts"]}
            | {part["ours"] for part in drv_block.DATA["parts"]} | {"U301"})


def table_refs():
    return {ref for table in TABLES for ref, *_ in table()}


def rank(fp, fixed):
    ref = fp.GetReference()
    if ref in fixed:
        return None
    for prefix, value in MOBILITY:
        if ref.startswith(prefix) and ref[len(prefix):].isdigit():
            return value
    return None


def on_board(board):
    outline = P.outline_of(board)
    return [fp for fp in board.GetFootprints() if outline.Contains(fp.GetPosition()) and P.assembled(fp)], outline


def gap_mm(a, b):
    pa, pb = P.body(a), P.body(b)
    lo, hi = 0.0, P.ASSEMBLY_GAP
    for _ in range(16):
        mid = (lo + hi) / 2
        if pa.Collide(pb, mm(mid)):
            hi = mid
        else:
            lo = mid
    return lo


def violations(board):
    parts, outline = on_board(board)
    pairs = []
    for i, a in enumerate(parts):
        for b in parts[i + 1:]:
            if P.gap_problem(a, b):
                pairs.append((gap_mm(a, b), a, b))
    edges = [fp for fp in parts if P.edge_problem(fp, outline)]
    return sorted(pairs, key=lambda v: (v[0], v[1].GetReference(), v[2].GetReference())), edges


COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)


def touches(pad, item):
    return any(pad.IsOnLayer(layer) and item.IsOnLayer(layer)
               and pad.GetEffectiveShape(layer).Collide(item.GetEffectiveShape(layer), 0) for layer in COPPER)


def parallel(direction, delta):
    cross = direction.x * delta.y - direction.y * delta.x
    return abs(cross) <= PARALLEL * max(1, direction.EuclideanNorm()) * max(1, delta.EuclideanNorm())


def stretch(item, end, delta):
    """The track's end moved by delta keeps its direction and a usable length: delta lies along the track."""
    here, there = (item.GetStart(), item.GetEnd()) if end == "start" else (item.GetEnd(), item.GetStart())
    direction = here - there
    if not parallel(direction, delta):
        return False
    moved = here + delta - there
    return moved.EuclideanNorm() >= mm(STEP) and moved.x * direction.x + moved.y * direction.y > 0


class Move:
    """A part moved by a delta with its copper, keeping every track at its angle; undo() puts everything back.

    A track ending on one of the part's pads stays where it is while its end is still on the moved pad (the pad still
    connects it); otherwise it stretches when the delta lies along it, or it moves whole, and what meets its far end
    follows: a track there stretches if the delta lies along it, a via there moves if nothing else
    reaches it. A far end on another part's pad, or anything else, refuses the move. A vendor's via under a pad stays;
    a track crossing a pad must still touch it afterwards."""

    def __init__(self, board, fp, delta):
        self.fp, self.delta, self.edits, self.ok, self.crossing = fp, delta, {}, True, []
        pads = list(fp.Pads())
        tracks = [item for item in board.GetTracks()]
        other_pads = [pad for other in board.GetFootprints() if other.GetReference() != fp.GetReference()
                      for pad in other.Pads()]
        for item in tracks:
            hits = [pad for pad in pads if pad.GetNetCode() == item.GetNetCode() and pad.GetNetCode() > 0
                    and touches(pad, item)]
            if not hits or item.GetClass() == "PCB_VIA":
                continue
            ends = {end: point for end, point in (("start", item.GetStart()), ("end", item.GetEnd()))
                    if any(pad.HitTest(point) for pad in hits)}
            if not ends:
                self.crossing.append((item, hits))
                continue
            loose = [end for end, point in ends.items()
                     if not any(pad.HitTest(point - delta) for pad in hits if pad.HitTest(point))]
            if not loose:
                self.crossing.append((item, hits))
            elif len(loose) == 2:
                self.edit(item, "both")
            elif len(ends) == 2:
                self.ok = False
            elif stretch(item, loose[0], delta):
                self.edit(item, loose[0])
            else:
                far = item.GetEnd() if loose[0] == "start" else item.GetStart()
                self.ok &= self.follow(item, far, tracks, other_pads)
                self.edit(item, "both")

    def edit(self, item, kind):
        key = item.m_Uuid.AsString()
        if key in self.edits and self.edits[key][1] != kind:
            self.ok = False
        self.edits[key] = (item, kind)

    def follow(self, item, far, tracks, other_pads):
        if any(pad.GetNetCode() == item.GetNetCode() and pad.HitTest(far) for pad in other_pads):
            return False
        for other in tracks:
            if other.m_Uuid.AsString() == item.m_Uuid.AsString() or other.GetNetCode() != item.GetNetCode():
                continue
            if other.GetClass() == "PCB_VIA":
                if other.GetPosition() != far:
                    continue
                reaching = [t for t in tracks if t.GetClass() != "PCB_VIA" and t.GetNetCode() == item.GetNetCode()
                            and far in (t.GetStart(), t.GetEnd())]
                if len(reaching) != 1:
                    return False
                self.edit(other, "both")
                continue
            ends = [end for end, point in (("start", other.GetStart()), ("end", other.GetEnd())) if point == far]
            if not ends:
                continue
            if not stretch(other, ends[0], self.delta):
                return False
            self.edit(other, ends[0])
        return True

    def shift(self, delta):
        self.fp.Move(delta)
        for item, kind in self.edits.values():
            if kind == "both":
                item.Move(delta)
            elif kind == "start":
                item.SetStart(item.GetStart() + delta)
            else:
                item.SetEnd(item.GetEnd() + delta)

    def apply(self):
        self.shift(self.delta)
        return all(any(touches(pad, item) for pad in hits) for item, hits in self.crossing)

    def undo(self):
        self.shift(pcbnew.VECTOR2I(-self.delta.x, -self.delta.y))

    def copper(self):
        return [item for item, _ in self.edits.values()]

    @property
    def ends(self):
        return list(self.edits.values())


def rule_clearance(a, b):
    """The copper clearance the board's rules give two items (board.CUSTOM_RULES, NET_CLASSES): ST's 0.1 mm on the RF,
    SMPS and HSE nets and C318, TI's 0.178 mm on the DRV8711's nets (the later rule wins), else the larger class
    clearance."""
    names = [item.GetNetname() for item in (a, b)]
    classes = [item.GetNetClassName() for item in (a, b)]
    parts = [item.GetParentFootprint().GetReference() if item.GetClass() == "PAD" else "" for item in (a, b)]
    if any("/DRV_" in name for name in names):
        return 0.178
    if "RF" in classes or any("SMPS" in name or "HSE_" in name for name in names) or "C318" in parts:
        return 0.1
    return max(CLASS_CLEARANCE.get(c, CLASS_CLEARANCE["Default"]) for c in classes)


def copper_problems(board, fp, copper):
    """Moved pads and track ends closer to other-net copper than rule_clearance, or to a hole than HOLE_TO_COPPER."""
    mine = list(fp.Pads()) + list(copper)
    ids = {item.m_Uuid.AsString() for item in mine}
    fixed = [pad for other in board.GetFootprints() if other.GetReference() != fp.GetReference() for pad in other.Pads()]
    fixed += [item for item in board.GetTracks() if item.m_Uuid.AsString() not in ids]
    found = set()
    for item in mine:
        for other in fixed:
            if other.GetNetCode() == item.GetNetCode() and item.GetNetCode() > 0:
                continue
            if (other.GetPosition() - item.GetPosition()).EuclideanNorm() > mm(6):
                continue
            clearance = mm(rule_clearance(item, other) - 0.0005)
            for layer in COPPER:
                if item.IsOnLayer(layer) and other.IsOnLayer(layer) and \
                        item.GetEffectiveShape(layer).Collide(other.GetEffectiveShape(layer), clearance):
                    found.add(f"{item.GetClass()} {item.GetNetname()} near {other.GetNetname()}")
                    break
            drilled = other.GetClass() == "PCB_VIA" or (other.GetClass() == "PAD" and other.HasHole())
            if drilled and item.GetEffectiveShape(pcbnew.F_Cu).Collide(other.GetEffectiveHoleShape(), mm(HOLE_TO_COPPER)):
                found.add(f"{item.GetClass()} {item.GetNetname()} near a hole of {other.GetNetname()}")
    return found


def state(board, fp, copper):
    """Everything place_block reports for the part but the assembly rules, and its copper against the board's rules."""
    outline = P.outline_of(board)
    others = [o for o in board.GetFootprints() if o.GetReference() != fp.GetReference()]
    assembly = P.assembly_problems(fp, others, outline)
    found = {why for why in P.problems(board, fp, outline, others) if why not in assembly}
    return found | copper_problems(board, fp, copper)


def try_moves(board, fp, deltas, cleared):
    """The first delta (shortest first) that clears the part and adds no other problem; the part is left moved."""
    for delta in deltas:
        move = Move(board, fp, delta)
        if not move.ok:
            continue
        before = state(board, fp, move.copper())
        if not move.apply():
            move.undo()
            continue
        if cleared() and state(board, fp, move.copper()) <= before:
            return move
        move.undo()
    return None


def pads_centre(fp):
    pads = pcbnew.BOX2I()
    for pad in fp.Pads():
        pads.Merge(pad.GetBoundingBox())
    return pads.GetCenter()


def free_of_copper(board, fp):
    """No track ends on or crosses the part's pads: it can go anywhere nearby, turned."""
    move = Move(board, fp, pcbnew.VECTOR2I(mm(STEP), 0))
    return not move.ends and not move.crossing


def try_spots(board, fp):
    """For a part with no copper of its own: the nearest spot, on a SPOT_STEP grid round its pads' centre up to MAX_SPOT,
    in any of four rotations, that clears it and adds no other problem; the part is left there."""
    centre, rotation = pads_centre(fp), fp.GetOrientationDegrees()
    before = state(board, fp, [])
    count = int(round(MAX_SPOT / SPOT_STEP))
    spots = sorted(((i * i + j * j, i, j) for i in range(-count, count + 1) for j in range(-count, count + 1)
                    if 0 < i * i + j * j <= count * count))
    for _, i, j in spots:
        target = centre + pcbnew.VECTOR2I(mm(i * SPOT_STEP), mm(j * SPOT_STEP))
        for turn in (0.0, 90.0, 180.0, 270.0):
            fp.SetOrientationDegrees((rotation + turn) % 360)
            fp.Move(target - pads_centre(fp))
            if part_clear(board, fp) and state(board, fp, []) <= before:
                return target - centre, turn
    fp.SetOrientationDegrees(rotation)
    fp.Move(centre - pads_centre(fp))
    return None


def axis_deltas(away=None):
    steps = [round(k * STEP, 4) for k in range(1, int(round(MAX_MOVE / STEP)) + 1)]
    out = []
    for s in steps:
        for dx, dz in ((s, 0), (-s, 0), (0, s), (0, -s)):
            out.append(pcbnew.VECTOR2I(mm(dx), -mm(dz)))
    if away is not None:
        out.sort(key=lambda d: (d.EuclideanNorm(), -(d.x * away.x + d.y * away.y)))
    return out


def part_clear(board, fp):
    outline = P.outline_of(board)
    others = [o for o in board.GetFootprints() if o.GetReference() != fp.GetReference()]
    return not P.assembly_problems(fp, others, outline)


def blockers(board, fp):
    outline = P.outline_of(board)
    return [other for other in board.GetFootprints() if other.GetReference() != fp.GetReference()
            and outline.Contains(other.GetPosition()) and P.assembled(other) and P.gap_problem(fp, other)]


def push(board, fp, other, fixed):
    """The part's shortest move away from `other` that clears it but for one movable neighbour, which then moves out of
    its way by its own shortest move (one level deep). Returns the log lines, or None with everything put back."""
    away = fp.GetPosition() - other.GetPosition()
    for delta in axis_deltas(away)[:PUSH_TRIES]:
        move = Move(board, fp, delta)
        if not move.ok:
            continue
        before = state(board, fp, move.copper())
        if not move.apply():
            move.undo()
            continue
        if state(board, fp, move.copper()) <= before:
            near = blockers(board, fp)
            if len(near) == 1 and near[0].GetReference() != other.GetReference() and rank(near[0], fixed) is not None:
                neighbour = near[0]
                apart = neighbour.GetPosition() - fp.GetPosition()
                second = try_moves(board, neighbour, axis_deltas(apart),
                                   lambda: part_clear(board, neighbour) and part_clear(board, fp))
                if second is not None:
                    return [(fp.GetReference(), move.delta, other.GetReference()),
                            (neighbour.GetReference(), second.delta, fp.GetReference() + ", pushed")]
        move.undo()
    return None


def apply(board):
    fixed = table_refs()
    vendor = vendor_refs()
    log = []
    pairs, edges = violations(board)
    for fp in edges:
        outline = P.outline_of(board)
        box = P.body(fp).BBox()
        left = box.GetLeft() - outline.BBox().GetLeft()
        right = outline.BBox().GetRight() - box.GetRight()
        inward = pcbnew.VECTOR2I(1, 0) if left < right else pcbnew.VECTOR2I(-1, 0)
        deltas = [pcbnew.VECTOR2I(inward.x * mm(round(k * STEP, 4)), 0)
                  for k in range(1, int(round(MAX_MOVE * 2 / STEP)) + 1)]
        move = try_moves(board, fp, deltas, lambda fp=fp: part_clear(board, fp))
        if move is None:
            sys.exit(f"{fp.GetReference()}: no inward move up to {2 * MAX_MOVE} mm clears the edge without a new problem")
        log.append((fp.GetReference(), move.delta, "edge"))
    while True:
        pairs, _ = violations(board)
        if not pairs:
            break
        progress = False
        for gap, a, b in pairs:
            if not P.gap_problem(a, b):
                continue
            movers = sorted([fp for fp in (a, b) if rank(fp, fixed) is not None],
                            key=lambda fp: (rank(fp, fixed), P.body(fp).Area(), fp.GetReference()))
            for fp in movers:
                other = b if fp.GetReference() == a.GetReference() else a
                away = fp.GetPosition() - other.GetPosition()
                move = try_moves(board, fp, axis_deltas(away), lambda fp=fp: part_clear(board, fp))
                if move is not None:
                    log.append((fp.GetReference(), move.delta, other.GetReference()))
                    progress = True
                    break
            else:
                for fp in movers:
                    other = b if fp.GetReference() == a.GetReference() else a
                    if not free_of_copper(board, fp) and fp.GetReference() in vendor:
                        continue
                    found = try_spots(board, fp)
                    if found is not None:
                        delta, turn = found
                        log.append((fp.GetReference(), delta, other.GetReference() + (f", turned {turn:.0f}" if turn else "")))
                        progress = True
                        break
                else:
                    for fp in movers:
                        other = b if fp.GetReference() == a.GetReference() else a
                        pushed = push(board, fp, other, fixed)
                        if pushed:
                            log += pushed
                            progress = True
                            break
        if not progress:
            left = ", ".join(f"{a.GetReference()}/{b.GetReference()} {gap:.2f} mm" for gap, a, b in pairs)
            sys.exit(f"no move clears: {left}")
    return log


def report(pairs, edges):
    for gap, a, b in pairs:
        print(f"  {a.GetReference()} / {b.GetReference()}: {gap:.2f} mm (min {P.ASSEMBLY_GAP})")
    for fp in edges:
        print(f"  {fp.GetReference()}: body within {P.EDGE_GAP} mm of the edge")


def stage(check):
    board = pcbnew.LoadBoard(str(B.BOARD))
    pairs, edges = violations(board)
    if check:
        report(pairs, edges)
        print(f"{len(pairs)} pair(s) closer than {P.ASSEMBLY_GAP} mm, {len(edges)} part(s) within {P.EDGE_GAP} mm of the edge")
        sys.exit(1 if pairs or edges else 0)
    if not pairs and not edges:
        print("every part keeps JLCPCB's spacing: nothing to do")
        sys.exit(3)
    log = apply(board)
    silk.report(*silk.layout(board, check=False), check=False)
    for ref, delta, why in log:
        print(f"{ref} moved ({pcbnew.ToMM(delta.x):+.2f}, {-pcbnew.ToMM(delta.y):+.2f}) mm, clear of {why}")
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report; exit 1 if any part breaks the spacing")
    group.add_argument("--apply", action="store_true", help="move the parts that break it (one shot)")
    group.add_argument("--pcbnew-stage", choices=("check", "apply"), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.pcbnew_stage == "check")
        return
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage", "check" if args.check else "apply"])
    B.PROJECT.write_bytes(project)
    if args.check or result.returncode == 3:
        sys.exit(0 if result.returncode == 3 else result.returncode)
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
