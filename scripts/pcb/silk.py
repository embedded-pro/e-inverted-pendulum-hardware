#!/usr/bin/env python3
"""Lay out the silkscreen labels: each part's reference (a test pad's net name, D-035) at JLCPCB's smallest text, clear
of everything else on the silkscreen (D-041).

    python3 scripts/pcb/silk.py            move the labels that are not clean, keep the ones that are
    python3 scripts/pcb/silk.py --check    report only; exit 1 if a label would move

board.py and the paste scripts run it last; run it yourself after moving parts in KiCad. Text is 1.0 mm high with a
0.15 mm line, JLCPCB's minimum (board.SILK_TEXT_MIN, pcb-design-rules jlcpcb profile), in KiCad's stroke font. A label
is clean when its ink box:
  - is upright, at 0 or 90 degrees;
  - clears every other label, every footprint's silk outline and every solder-mask opening (pads, holes) by 0.15 mm,
    JLCPCB's silk-to-pad and the board's min_silk_clearance;
  - does not touch a via (ink over a tented hole breaks up);
and, for a part on the board (the staging area is not built, so there only the rules above apply):
  - does not touch any part's courtyard, where it would sit under a body, nor the antenna tab (ANTENNA_TAB) unless it
    is the antenna's own label;
  - stays EDGE_CLEARANCE inside the board edge;
  - reads as its own part's (Side.belongs): its centre is nearer that part than any other, or it sits squarely beside
    the part, within ADJACENT, with no other part nearer.
Clean labels stay where they are, so the owner's adjustments survive and a second run changes nothing. The others are
placed fewest options first, each at its cheapest clean spot around the part's courtyard (distance, then sliding off
centre; horizontal before vertical, above before below and beside); a label left without a spot may move labels placed
in this run out of the way (up to REPAIR_BLOCKERS at a time, REPAIR_DEPTH deep), and where two parts can only share
one spot the larger part keeps it. A label with no clean spot within SEARCH_MM goes to the fab layer (assembly
drawing) and is listed.
"""

import argparse
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402

mm = pcbnew.FromMM
TEXT_SIZE, TEXT_LINE = (mm(v) for v in B.SILK_TEXT_MIN)
SILK_CLEARANCE = mm(0.15)
EDGE_CLEARANCE = mm(0.5)
SEARCH_MM = 3.0
STEP = mm(0.1)
ANGLES = ((0.0, 0), (90.0, mm(0.3)))
SIDES = (("above", 0), ("below", mm(0.05)), ("left", mm(0.1)), ("right", mm(0.1)))
SLIDE_COST = 0.25
LABEL_FREE_AREAS = {"ANTENNA_TAB"}
ADJACENT = mm(0.6)
REPAIR_SPOTS = 200
REPAIR_BLOCKERS = 2
REPAIR_DEPTH = 3
ERROR = mm(0.005)
CELL = mm(2.0)


class Grid:
    """Boxes (left, top, right, bottom) in nm with a payload, bucketed for neighbourhood queries."""

    def __init__(self):
        self.cells, self.items = {}, []

    @staticmethod
    def keys(box):
        for i in range(box[0] // CELL, box[2] // CELL + 1):
            for j in range(box[1] // CELL, box[3] // CELL + 1):
                yield i, j

    def add(self, box, payload):
        for key in self.keys(box):
            self.cells.setdefault(key, []).append(len(self.items))
        self.items.append((box, payload))

    def near(self, box):
        seen = set()
        for key in self.keys(box):
            for index in self.cells.get(key, ()):
                if index not in seen:
                    seen.add(index)
                    item = self.items[index]
                    if overlaps(item[0], box):
                        yield item


class Placed:
    """Labels already on the silkscreen, by ink box; a label can be taken out again while repairing."""

    def __init__(self):
        self.cells, self.boxes = {}, {}

    def add(self, label, box):
        self.boxes[label] = box
        for key in Grid.keys(grow(box, SILK_CLEARANCE)):
            self.cells.setdefault(key, set()).add(label)

    def remove(self, label):
        box = self.boxes.pop(label)
        for key in Grid.keys(grow(box, SILK_CLEARANCE)):
            self.cells[key].discard(label)

    def blockers(self, box, label):
        found = set()
        for key in Grid.keys(grow(box, SILK_CLEARANCE)):
            for other in self.cells.get(key, ()):
                if other is not label and gap(box, self.boxes[other]) < SILK_CLEARANCE:
                    found.add(other)
        return sorted(found, key=lambda lb: lb.ref)

    def free(self, box, label):
        return not self.blockers(box, label)


def overlaps(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def grow(box, by):
    return box[0] - by, box[1] - by, box[2] + by, box[3] + by


def box_of(bbox):
    return bbox.GetLeft(), bbox.GetTop(), bbox.GetRight(), bbox.GetBottom()


def gap(a, b):
    dx, dy = max(a[0] - b[2], b[0] - a[2], 0), max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy)


def point_to_box(p, box):
    return math.hypot(max(box[0] - p[0], p[0] - box[2], 0), max(box[1] - p[1], p[1] - box[3], 0))


def rect_shape(box):
    return pcbnew.SHAPE_RECT(pcbnew.VECTOR2I(box[0], box[1]), box[2] - box[0], box[3] - box[1])


def poly_of(item, layer):
    poly = pcbnew.SHAPE_POLY_SET()
    item.TransformShapeToPolygon(poly, layer, 0, ERROR, pcbnew.ERROR_OUTSIDE)
    return poly


def side_layers(flipped):
    if flipped:
        return pcbnew.B_SilkS, pcbnew.B_Mask, pcbnew.B_Cu, pcbnew.B_CrtYd, pcbnew.B_Fab
    return pcbnew.F_SilkS, pcbnew.F_Mask, pcbnew.F_Cu, pcbnew.F_CrtYd, pcbnew.F_Fab


def body_box(fp, flipped):
    fp.BuildCourtyardCaches()
    court = fp.GetCourtyard(side_layers(flipped)[3])
    if court.OutlineCount():
        return box_of(court.BBox())
    return box_of(fp.GetBoundingBox(False))


class Side:
    """What a label on one side of the board must clear."""

    def __init__(self, board, flipped, labels, outline):
        silk, mask, copper, court, _ = side_layers(flipped)
        self.hard, self.bodies, self.free = Grid(), Grid(), Grid()
        self.outline = outline
        self.inner = pcbnew.SHAPE_POLY_SET(outline)
        self.inner.Deflate(EDGE_CLEARANCE, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERROR)
        managed = {(label.ref, label.field.GetName()) for label in labels}
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.IsOnLayer(mask):
                    self.obstacle(poly_of(pad, mask), SILK_CLEARANCE + max(0, pad.GetSolderMaskExpansion(mask)))
                if pad.HasHole():
                    hole = pcbnew.SHAPE_POLY_SET()
                    pad.TransformHoleToPolygon(hole, 0, ERROR, pcbnew.ERROR_OUTSIDE)
                    self.obstacle(hole, SILK_CLEARANCE)
            for item in list(fp.GraphicalItems()) + list(fp.GetFields()):
                if item.GetClass() in ("PCB_TEXT", "PCB_FIELD") and not item.IsVisible():
                    continue
                if item.GetClass() == "PCB_FIELD" and (fp.GetReference(), item.GetName()) in managed:
                    continue
                if item.GetLayer() in (silk, mask):
                    self.obstacle(poly_of(item, item.GetLayer()), SILK_CLEARANCE)
            if fp.IsFlipped() == flipped:
                fp.BuildCourtyardCaches()
                poly = fp.GetCourtyard(court)
                if poly.OutlineCount():
                    self.free.add(box_of(poly.BBox()), (poly, fp.GetReference()))
                self.bodies.add(body_box(fp, flipped), fp.GetReference())
        for item in board.GetDrawings():
            if item.GetLayer() in (silk, mask) and not (item.GetClass() == "PCB_TEXT" and not item.IsVisible()):
                self.obstacle(poly_of(item, item.GetLayer()), SILK_CLEARANCE)
        for track in board.GetTracks():
            if track.GetClass() == "PCB_VIA":
                self.obstacle(poly_of(track, copper), 0)
        for zone in board.Zones():
            if zone.GetIsRuleArea() and zone.GetZoneName() in LABEL_FREE_AREAS:
                poly = zone.Outline()
                self.free.add(box_of(poly.BBox()), (poly, None))

    def belongs(self, box, label):
        """The label reads as its own part's: its centre is nearer that part than any other, or it sits squarely
        beside the part (centred within the part's extent, within ADJACENT) with no other part nearer."""
        centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        own = point_to_box(centre, label.body)
        reach = int(own) + 1
        probe = (int(centre[0]) - reach, int(centre[1]) - reach, int(centre[0]) + reach, int(centre[1]) + reach)
        if all(ref == label.ref or point_to_box(centre, other) > own for other, ref in self.bodies.near(probe)):
            return True
        l, t, r, b = label.body
        if box[3] <= t or box[1] >= b:
            squarely = l <= centre[0] <= r
        elif box[2] <= l or box[0] >= r:
            squarely = t <= centre[1] <= b
        else:
            return False
        near = gap(box, label.body)
        if not squarely or near > ADJACENT:
            return False
        return all(ref == label.ref or gap(box, other) >= near for other, ref in self.bodies.near(grow(box, int(near) + 1)))

    def obstacle(self, poly, clearance):
        if poly.OutlineCount():
            self.hard.add(grow(box_of(poly.BBox()), clearance), (poly, clearance))

    def fits(self, box, label):
        """Every rule but the label-to-label clearance."""
        shape = rect_shape(box)
        for _, (poly, clearance) in self.hard.near(box):
            if poly.Collide(shape, clearance):
                return False
        if not label.on_board:
            return True
        for _, (poly, owner) in self.free.near(box):
            if owner != label.ref and not (owner is None and poly.Contains(label.fp.GetPosition())) \
                    and poly.Collide(shape, 0):
                return False
        if not self.belongs(box, label):
            return False
        rect = pcbnew.SHAPE_POLY_SET()
        rect.NewOutline()
        for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
            rect.Append(x, y)
        rect.BooleanSubtract(self.inner)
        return rect.IsEmpty()


class Label:
    def __init__(self, fp, field, on_board):
        self.fp, self.field, self.ref, self.on_board = fp, field, fp.GetReference(), on_board
        self.flipped = fp.IsFlipped()
        self.layer, self.fab = side_layers(self.flipped)[0], side_layers(self.flipped)[4]
        self.body = body_box(fp, self.flipped)

    def style(self, angle):
        field = self.field
        field.SetLayer(self.layer)
        field.SetVisible(True)
        field.SetFont(None)
        field.SetBold(False)
        field.SetItalic(False)
        field.SetTextSize(pcbnew.VECTOR2I(TEXT_SIZE, TEXT_SIZE))
        field.SetTextThickness(TEXT_LINE)
        field.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        field.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        field.SetKeepUpright(True)
        field.SetMirrored(self.flipped)
        field.SetTextAngleDegrees(angle)

    def ink(self):
        return box_of(poly_of(self.field, self.layer).BBox())

    def is_styled(self):
        field = self.field
        return (field.IsVisible() and field.GetLayer() == self.layer and field.GetFont() is None
                and field.GetTextSize() == pcbnew.VECTOR2I(TEXT_SIZE, TEXT_SIZE) and field.GetTextThickness() == TEXT_LINE
                and not field.IsBold() and not field.IsItalic() and field.IsKeepUpright()
                and field.GetHorizJustify() == pcbnew.GR_TEXT_H_ALIGN_CENTER
                and field.GetVertJustify() == pcbnew.GR_TEXT_V_ALIGN_CENTER
                and field.IsMirrored() == self.flipped
                and any(abs(field.GetTextAngleDegrees() - a) < 1e-6 for a, _ in ANGLES))

    def shapes(self):
        """Ink box offset from the text position, per angle, without moving the label for good."""
        position, angle = self.field.GetPosition(), self.field.GetTextAngleDegrees()
        layer, visible = self.field.GetLayer(), self.field.IsVisible()
        out = {}
        for a, _ in ANGLES:
            self.style(a)
            self.field.SetPosition(pcbnew.VECTOR2I(0, 0))
            out[a] = self.ink()
        self.field.SetLayer(layer)
        self.field.SetVisible(visible)
        self.field.SetTextAngleDegrees(angle)
        self.field.SetPosition(position)
        return out

    def candidates(self):
        l, t, r, b = self.body
        cx, cy = (l + r) // 2, (t + b) // 2
        found = []
        for angle, angle_cost in ANGLES:
            ink = self.ink_by_angle[angle]
            w, h = ink[2] - ink[0], ink[3] - ink[1]
            for side, side_cost in SIDES:
                along = (r - l, w) if side in ("above", "below") else (b - t, h)
                reach = (along[0] + along[1]) // 2
                slides = sorted(range(-(reach // STEP) * STEP, reach + 1, STEP), key=abs)
                for g in range(STEP, mm(SEARCH_MM) + 1, STEP):
                    for s in slides:
                        if side == "above":
                            box = (cx + s - w // 2, t - g - h, cx + s - w // 2 + w, t - g)
                        elif side == "below":
                            box = (cx + s - w // 2, b + g, cx + s - w // 2 + w, b + g + h)
                        elif side == "left":
                            box = (l - g - w, cy + s - h // 2, l - g, cy + s - h // 2 + h)
                        else:
                            box = (r + g, cy + s - h // 2, r + g + w, cy + s - h // 2 + h)
                        cost = g + SLIDE_COST * abs(s) + side_cost + angle_cost
                        found.append((cost, angle, box))
        found.sort(key=lambda c: (c[0], c[1], c[2]))
        return found

    def put(self, angle, box):
        ink = self.ink_by_angle[angle]
        self.style(angle)
        self.field.SetPosition(pcbnew.VECTOR2I(box[0] - ink[0], box[1] - ink[1]))


def layout(board, check):
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    labels = [Label(fp, B.silk_label(fp), outline.Contains(fp.GetPosition()))
              for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()) if B.silk_label(fp) is not None]
    sides = {flipped: Side(board, flipped, labels, outline) for flipped in (False, True)}
    placed = Placed()
    kept, todo = [], []
    for label in labels:
        box = label.ink() if label.is_styled() else None
        if box is not None and sides[label.flipped].fits(box, label) and placed.free(box, label):
            placed.add(label, box)
            kept.append(label)
        else:
            todo.append(label)
    for label in todo:
        label.ink_by_angle = label.shapes()
        side = sides[label.flipped]
        label.spots = [spot for spot in label.candidates() if side.fits(spot[2], label)]
    spot_of = {}

    def first_free(label):
        return next((spot for spot in label.spots if placed.free(spot[2], label)), None)

    failed = []
    for label in sorted(todo, key=lambda lb: (not lb.on_board, len(lb.spots), lb.ref)):
        spot = first_free(label)
        if spot is None:
            failed.append(label)
        else:
            placed.add(label, spot[2])
            spot_of[label] = spot
    journal = []

    def place(label, spot):
        journal.append((label, spot_of.get(label)))
        if label in spot_of:
            placed.remove(label)
        placed.add(label, spot[2])
        spot_of[label] = spot

    def lift(label):
        journal.append((label, spot_of[label]))
        placed.remove(label)
        del spot_of[label]

    def undo(mark):
        while len(journal) > mark:
            label, before = journal.pop()
            if label in spot_of:
                placed.remove(label)
                del spot_of[label]
            if before is not None:
                placed.add(label, before[2])
                spot_of[label] = before

    def relocate(label, depth, chain):
        """Put `label` on its cheapest spot, moving at most REPAIR_BLOCKERS labels placed in this run out of the way,
        each of which may move others in turn, `depth` levels deep."""
        for spot in label.spots[:REPAIR_SPOTS]:
            blockers = placed.blockers(spot[2], label)
            if len(blockers) > REPAIR_BLOCKERS or any(b not in spot_of or b in chain for b in blockers):
                continue
            if blockers and depth == 0:
                continue
            mark = len(journal)
            for b in blockers:
                lift(b)
            place(label, spot)
            if all(relocate(b, depth - 1, chain | {label}) for b in blockers):
                return True
            undo(mark)
        return False

    for label in list(failed):
        if relocate(label, REPAIR_DEPTH, frozenset()):
            failed.remove(label)

    def area(label):
        return (label.body[2] - label.body[0]) * (label.body[3] - label.body[1])

    for label in sorted(failed, key=lambda lb: lb.ref):
        for spot in label.spots[:REPAIR_SPOTS]:
            blockers = placed.blockers(spot[2], label)
            if len(blockers) != 1 or blockers[0] not in spot_of or area(blockers[0]) >= area(label):
                continue
            lift(blockers[0])
            place(label, spot)
            failed.remove(label)
            if not relocate(blockers[0], REPAIR_DEPTH, frozenset({label})):
                failed.append(blockers[0])
            break
    moved = []
    for label in todo:
        if label in spot_of:
            cost, angle, box = spot_of[label]
            if not check:
                label.put(angle, box)
            moved.append((label, cost))
        elif not check:
            label.style(0.0)
            label.field.SetLayer(label.fab)
            label.field.SetPosition(label.fp.GetPosition())
    return kept, moved, failed


def report(kept, moved, failed, check):
    verb = "would move" if check else "placed"
    on_board = [m for m in moved if m[0].on_board]
    print(f"silkscreen labels: {len(kept)} already clean, {len(moved)} {verb} "
          f"({len(on_board)} on the board, {len(moved) - len(on_board)} in the staging area), "
          f"{len(failed)} with no clean spot")
    if on_board:
        worst = max(on_board, key=lambda m: m[1])
        print(f"  on the board: furthest {pcbnew.ToMM(worst[1]):.2f} mm (cost) for {worst[0].ref}")
    for label in failed:
        print(f"  {label.ref}: no clean spot within {SEARCH_MM} mm; label on {'B' if label.flipped else 'F'}.Fab")


def stage(check):
    board = pcbnew.LoadBoard(str(B.BOARD))
    kept, moved, failed = layout(board, check)
    report(kept, moved, failed, check)
    if check:
        sys.exit(1 if moved else 0)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="report only; exit 1 if a label would move")
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.check)
        return
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage"] + (["--check"] if args.check else []))
    B.PROJECT.write_bytes(project)
    if result.returncode or args.check:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
