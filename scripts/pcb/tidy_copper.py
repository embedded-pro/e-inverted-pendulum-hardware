#!/usr/bin/env python3
"""Tidy the copper so DRC has no error: exact 45-degree bends, branches on pads, vias clear of the RF line (D-053).

    python3 scripts/pcb/tidy_copper.py --apply

  - Exact angles: the vendors' copied routing (TI's mil coordinates, ST's) has diagonals 1-500 nm off 45 degrees, which
    DRC's 45-degree rule (pcb-design-rules: track_angle min 135) reads as 134.99x and flags. Each such diagonal is made
    exact by sliding its bend point along the straight track it meets (that track stays straight; at most 0.5 um moves).
  - Branches on pads: a track that starts in the middle of another track of its net (a tee, which the rule flags) is
    re-drawn from that track's pad end, straight then 45 degrees (ENC_L_A_RAW: from U601 pin 1, the ESD's pass-through
    pad, to R604).
  - A tee of three tracks off any pad, two of them in line and each ending on a via that reaches the ground pours: the
    two in-line arms go and a via of their size takes the junction (ST's NFC B.Cu ground, now carried by the pours).
  - A via closer to another net's copper than the hole clearance (JLCPCB 0.20 mm) moves by the smallest step that
    clears every rule (gnd_vias.Checker), away from the copper it was near (the GND via beside RF_50).
Re-running is a no-op once nothing is left to do; the zones are refilled. Nothing is locked (D-045).
"""

import argparse
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import gnd_vias as G  # noqa: E402
import mcu_escape as E  # noqa: E402

mm = pcbnew.FromMM
TOLERANCE = 500
HOLE_TO_COPPER = 0.2
STEP = 0.01
MAX_MOVE = 0.3
# Smaller vias for a tee's junction when its arms' via size doesn't fit there: sizes already on the board (ST's).
TEE_VIAS = ((0.6, 0.3), (0.45, 0.2))
# Items added to or taken off the board stay referenced until it is saved (SWIG would free them under the board).
KEEP = []


def segments(board):
    return [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]


def joined(board, item, point):
    """Same-net tracks on the item's layer with an end at the point, and vias at it."""
    found = []
    for other in board.GetTracks():
        if other.m_Uuid.AsString() == item.m_Uuid.AsString() or other.GetNetCode() != item.GetNetCode():
            continue
        if other.GetClass() == "PCB_VIA":
            if other.GetPosition() == point:
                found.append(other)
        elif other.GetClass() == "PCB_TRACK" and other.GetLayer() == item.GetLayer() and point in (other.GetStart(), other.GetEnd()):
            found.append(other)
    return found


def set_end(track, old, new):
    if track.GetStart() == old:
        track.SetStart(new)
    else:
        track.SetEnd(new)


def snap_angles(board):
    """Diagonals within TOLERANCE of 45 degrees made exact at a bend shared with one straight track."""
    fixed = 0
    for diag in segments(board):
        d = diag.GetEnd() - diag.GetStart()
        if d.x == 0 or d.y == 0 or abs(d.x) == abs(d.y) or abs(abs(d.x) - abs(d.y)) > TOLERANCE:
            continue
        for bend, far in ((diag.GetStart(), diag.GetEnd()), (diag.GetEnd(), diag.GetStart())):
            others = joined(board, diag, bend)
            if len(others) != 1 or others[0].GetClass() != "PCB_TRACK":
                continue
            straight = others[0]
            s = straight.GetEnd() - straight.GetStart()
            if s.x != 0 and s.y != 0:
                continue
            if s.y == 0:
                sign = 1 if far.x > bend.x else -1
                new = pcbnew.VECTOR2I(far.x - sign * abs(far.y - bend.y), bend.y)
            else:
                sign = 1 if far.y > bend.y else -1
                new = pcbnew.VECTOR2I(bend.x, far.y - sign * abs(far.x - bend.x))
            other_end = straight.GetEnd() if straight.GetStart() == bend else straight.GetStart()
            if (new - other_end).EuclideanNorm() < mm(0.01) or (new - bend).EuclideanNorm() > TOLERANCE:
                continue
            set_end(straight, bend, new)
            set_end(diag, bend, new)
            fixed += 1
            break
    return fixed


def inside(point, track):
    """The point lies on the track, not at either end."""
    a, b = track.GetStart(), track.GetEnd()
    if point in (a, b):
        return False
    seg = pcbnew.SEG(a, b)
    return seg.Distance(point) <= 1


def two_legs(a, f):
    """Straight then 45 degrees from a to f, or 45 degrees then straight: the two bend points."""
    dx, dy = f.x - a.x, f.y - a.y
    sx, sy = (1 if dx >= 0 else -1), (1 if dy >= 0 else -1)
    if abs(dy) >= abs(dx):
        return [pcbnew.VECTOR2I(a.x, f.y - sy * abs(dx)), pcbnew.VECTOR2I(a.x + dx, a.y + sy * abs(dx))]
    return [pcbnew.VECTOR2I(f.x - sx * abs(dy), a.y), pcbnew.VECTOR2I(a.x + sx * abs(dy), a.y + dy)]


def new_track(board, like, start, end):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetWidth(like.GetWidth())
    track.SetLayer(like.GetLayer())
    track.SetNet(like.GetNet())
    board.Add(track)
    KEEP.append(track)
    return track


def clear_of_others(board, tracks):
    ids = {t.m_Uuid.AsString() for t in tracks}
    checker = G.Checker(board)
    for track in tracks:
        layer = track.GetLayer()
        shape = track.GetEffectiveShape(layer)
        for item in checker.items:
            if item.m_Uuid.AsString() in ids or item.GetNetCode() == track.GetNetCode() or not item.IsOnLayer(layer):
                continue
            if (item.GetPosition() - track.GetPosition()).EuclideanNorm() > mm(6):
                continue
            clearance = max(E.CLEARANCE, G.CLASS_CLEARANCE.get(item.GetNetClassName(), E.CLEARANCE))
            if item.GetEffectiveShape(layer).Collide(shape, mm(clearance + E.MARGIN)):
                return False
    return True


def branches_to_pads(board):
    """A track starting mid-track: re-drawn from that track's end on a pad."""
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    moved = []
    for branch in segments(board):
        for start, far in ((branch.GetStart(), branch.GetEnd()), (branch.GetEnd(), branch.GetStart())):
            hosts = [t for t in segments(board) if t.GetNetCode() == branch.GetNetCode()
                     and t.GetLayer() == branch.GetLayer() and t.m_Uuid.AsString() != branch.m_Uuid.AsString()
                     and inside(start, t)]
            if not hosts:
                continue
            host = hosts[0]
            ends = [p for p in (host.GetStart(), host.GetEnd())
                    if any(pad.GetNetCode() == host.GetNetCode() and pad.HitTest(p) for pad in pads)]
            if not ends:
                continue
            anchor = min(ends, key=lambda p: (p - far).EuclideanNorm())
            if anchor == far:
                moved.append(branch.GetNetname().rsplit("/", 1)[-1] + " (a duplicate along its host)")
                KEEP.append(branch)
                board.Remove(branch)
                break
            for bend in two_legs(anchor, far):
                legs = [new_track(board, branch, p, q) for p, q in ((anchor, bend), (bend, far)) if p != q]
                if clear_of_others(board, legs):
                    moved.append(branch.GetNetname().rsplit("/", 1)[-1])
                    KEEP.append(branch)
                    board.Remove(branch)
                    break
                for leg in legs:
                    board.Remove(leg)
            break
    return moved


def tees_to_vias(board):
    """Three tracks meeting off any pad, two in line ending on vias: the in-line arms go, a via takes the junction."""
    pads = [pad for fp in board.GetFootprints() for pad in fp.Pads()]
    done = []
    for track in segments(board):
        for point in (track.GetStart(), track.GetEnd()):
            others = joined(board, track, point)
            arms = [track] + [t for t in others if t.GetClass() == "PCB_TRACK"]
            if len(arms) != 3 or len(others) != 2:
                continue
            if any(pad.GetNetCode() == track.GetNetCode() and pad.HitTest(point) for pad in pads):
                continue
            far = {a.m_Uuid.AsString(): (a.GetEnd() if a.GetStart() == point else a.GetStart()) for a in arms}
            dirs = {k: v - point for k, v in far.items()}
            inline = [(a, b) for i, a in enumerate(arms) for b in arms[i + 1:]
                      if dirs[a.m_Uuid.AsString()].x * dirs[b.m_Uuid.AsString()].y
                      == dirs[a.m_Uuid.AsString()].y * dirs[b.m_Uuid.AsString()].x]
            if len(inline) != 1:
                continue
            a, b = inline[0]
            vias = [next((v for v in joined(board, arm, far[arm.m_Uuid.AsString()]) if v.GetClass() == "PCB_VIA"), None)
                    for arm in (a, b)]
            if None in vias:
                continue
            checker = G.Checker(board)
            checker.items = [i for i in checker.items if i.m_Uuid.AsString() not in {a.m_Uuid.AsString(), b.m_Uuid.AsString()}]
            sizes = [(vias[0].GetWidth(pcbnew.F_Cu), vias[0].GetDrillValue())] + [(mm(d), mm(h)) for d, h in TEE_VIAS]
            size = next((s for s in sizes if fits(checker, track.GetNetCode(), point, *s)), None)
            if size is None:
                continue
            via = pcbnew.PCB_VIA(board)
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetPosition(point)
            via.SetWidth(size[0])
            via.SetDrill(size[1])
            via.SetNet(track.GetNet())
            KEEP.extend([a, b, via])
            board.Remove(a)
            board.Remove(b)
            board.Add(via)
            done.append(f"{track.GetNetname().rsplit('/', 1)[-1]} at {G.mech(point)} "
                        f"({pcbnew.ToMM(size[0]):.2f} / {pcbnew.ToMM(size[1]):.2f} mm)")
            return done
    return done


def fits(checker, netcode, at, diameter, drill):
    """gnd_vias.Checker.fits for a via of this size: inside the board by the copper-to-edge clearance, clear of other
    nets' copper by the rule clearance and of holes by HOLE_TO_COPPER / HOLE_TO_HOLE, outside the via keep-outs."""
    ring, hole = pcbnew.SHAPE_CIRCLE(at, diameter // 2), pcbnew.SHAPE_CIRCLE(at, drill // 2)
    inside = pcbnew.SHAPE_POLY_SET(checker.inside)
    inside.Inflate(mm(G.VIA_DIAMETER / 2) - diameter // 2, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
    if not inside.Contains(at):
        return False
    for item in checker.items:
        if (item.GetPosition() - at).EuclideanNorm() > mm(3) + E.reach(item):
            continue
        drilled = item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole())
        if drilled and item.GetEffectiveHoleShape().Collide(hole, mm(E.HOLE_TO_HOLE + E.MARGIN)):
            return False
        if item.GetNetCode() == netcode:
            continue
        clearance = max(E.CLEARANCE, G.CLASS_CLEARANCE.get(item.GetNetClassName(), E.CLEARANCE))
        for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            if item.IsOnLayer(layer):
                shape = item.GetEffectiveShape(layer)
                if shape.Collide(ring, mm(clearance + E.MARGIN)) or shape.Collide(hole, mm(HOLE_TO_COPPER + E.MARGIN)):
                    return False
    return not any(area.Collide(ring, 0) for area in checker.keepouts)


def vias_off_copper(board):
    """Vias within HOLE_TO_COPPER of another net's copper, moved by the smallest step that fits every rule."""
    moved = []
    for via in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        hole = pcbnew.SHAPE_CIRCLE(via.GetPosition(), via.GetDrillValue() // 2)
        near = [t for t in board.GetTracks() if t.GetNetCode() != via.GetNetCode() and t.GetClass() != "PCB_VIA"
                and (t.GetPosition() - via.GetPosition()).EuclideanNorm() < mm(5)
                and t.GetEffectiveShape(t.GetLayer()).Collide(hole, mm(HOLE_TO_COPPER) - 1)]
        if not near:
            continue
        checker = G.Checker(board)
        checker.items = [i for i in checker.items if i.m_Uuid.AsString() != via.m_Uuid.AsString()]
        here = via.GetPosition()
        steps = int(round(MAX_MOVE / STEP))
        spots = sorted(((i * i + j * j, i, j) for i in range(-steps, steps + 1) for j in range(-steps, steps + 1)
                        if 0 < i * i + j * j <= steps * steps))
        for _, i, j in spots:
            at = here + pcbnew.VECTOR2I(mm(i * STEP), mm(j * STEP))
            ring = pcbnew.SHAPE_CIRCLE(at, via.GetDrillValue() // 2)
            if any(t.GetEffectiveShape(t.GetLayer()).Collide(ring, mm(HOLE_TO_COPPER + E.MARGIN)) for t in near):
                continue
            if fits(checker, via.GetNetCode(), at, via.GetWidth(pcbnew.F_Cu), via.GetDrillValue()):
                via.SetPosition(at)
                moved.append(f"{via.GetNetname()} via {G.mech(here)} -> {G.mech(at)}")
                break
        else:
            sys.exit(f"no spot within {MAX_MOVE} mm for the via at {G.mech(here)}")
    return moved


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    snapped = snap_angles(board)
    branches = branches_to_pads(board)
    tees = tees_to_vias(board)
    vias = vias_off_copper(board)
    if not (snapped or branches or tees or vias):
        print("the copper is tidy: nothing to do")
        sys.exit(3)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"{snapped} bends made exactly 45 degrees")
    for net in branches:
        print(f"{net}: branch re-drawn from its pad" if "duplicate" not in net else f"{net}: removed")
    for tee in tees:
        print(f"tee on {tee} replaced by a via")
    for line in vias:
        print(line)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="tidy the copper (one shot)")
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
