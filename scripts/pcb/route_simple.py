#!/usr/bin/env python3
"""Routing pass 1: the simple connections, short and on one layer, with vias only down to the ground plane (D-054).

    python3 scripts/pcb/route_simple.py --apply

The owner asked for the simple connections first, at JLCPCB's track sizes, with vias only where they are needed. Each net
is split into its islands (board connectivity), and the closest terminals of two islands are joined first (shortest
first, like a minimum spanning tree, so no loop is ever closed). Every new track is checked against everything on the
board and everything routed before it:
  - links: two pads up to MAX_LINK apart, pad centre to pad centre (branches only on pads), straight or with one
    45-degree bend, on a copper layer both pads are on; no via. GND pads of one part side by side (up to GND_TIE apart)
    are tied the same way. PWR_4.2A (VBAT, PP_S, BAT_F, BAT_P) is left to the pours (docs/power-map.md: pours on L1 + L3,
    no necks below 2.2 mm). A crystal's nets are routed together or not at all (power map: short and symmetric). Pads
    of one part that share a number are joined inside the footprint (AE801's coil, ST's copper) and count as one;
  - gaps: a pad, a free track end or a via joined to a free track end or a via of its net up to MAX_GAP away (the
    vendor copies' and the MCU fan-out's open ends). A track end is left within 45 degrees of its direction, and tracks
    meet at a via at 135 degrees or more (pcb-design-rules: tracks meeting at a via are not exempt from the 45-degree
    rule, tracks meeting at a pad are);
  - ground: each GND island still off the L2 plane gets one stub and one via, at the nearest spot outward from a pad.
    The class via is 0.3 / 0.6 mm, else 0.2 / 0.45 mm (tidy_copper.TEE_VIAS; the board already has 0.15 mm holes, D-049).
    The via is never in a pad (VIA_WEB) or under its part's body (place_block.body), stays outside other parts'
    courtyards and the test pads' silkscreen names, and lands on the L2 fill.
The vendor copies (MB1355 with U301, MB1163 with AE801, BOOST-DRV8711) keep their own routing: no track joins two
parts of one copy, no gap starts at a copy's pad and no ground via goes on a copy's pad here; those are restored from the
vendor's reference (CLAUDE.md). A copy's pin may still be linked to one of our parts.
Widths: the net class width (docs/power-map.md, board.NET_CLASSES). Where a pad is narrower, the track takes the
narrower pad's width, but never less than MIN_WIDTH (the board's 0.15 mm design value; JLCPCB's 4-layer minimum is
0.09 mm). PWR_2A keeps its class width. A gap takes the narrower track's width.
Clearances: respace.rule_clearance to other nets' copper (the class clearances and the ST / TI custom rules); 0.2 mm hole
to copper (0.28 mm to plated pad holes, 0.5 mm to NPTH, .kicad_dru); 0.2 mm to the edge. Nothing enters another net's
pour or a rule area that forbids tracks or vias, the board's or a footprint's (U701's no-track area under the IMU, the
mounting holes' keep-outs).
Re-running is a no-op once nothing simple is left. The zones are refilled. Nothing is locked (D-045).
"""

import argparse
import math
import pathlib
import subprocess
import sys
from collections import defaultdict

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import drv_block as D  # noqa: E402
import mcu_escape as E  # noqa: E402
import nfc_block as N  # noqa: E402
import place_block as PB  # noqa: E402
import pours as P  # noqa: E402
import respace as R  # noqa: E402
import rf_block as RF  # noqa: E402
import tidy_copper as T  # noqa: E402

mm = pcbnew.FromMM
V = pcbnew.VECTOR2I
MAX_LINK = 8.0
MAX_GAP = 3.0
GND_TIE = 1.0
MIN_WIDTH = 0.15
STUB_WIDTH = (0.2, 0.5)
VIA_SIZES = T.TEE_VIAS
VIA_WEB = 0.1
VIA_REACH = 1.5
STEP = 0.05
SAMPLE = 0.025
SNAP = 0.02
EDGE = 0.2
HOLE_TO_COPPER = 0.2
PAD_HOLE_TO_COPPER = 0.28
NPTH_TO_COPPER = 0.5
HOLE_TO_HOLE = 0.2
POUR_GAP = 0.2
LABEL_GAP = 0.05
NEAR = 2.0
SKIP_CLASSES = {"PWR_4.2A"}
FULL_WIDTH = {"PWR_2A"}
GND = "GND"
COS45 = math.cos(math.radians(45)) - 1e-6
DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
OUTER = (pcbnew.F_Cu, pcbnew.B_Cu)
COPPER = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
WIDTH = {"Default": B.DEFAULT_CLASS["track_width"], **{name: spec["track_width"] for name, spec in B.NET_CLASSES.items()}}
# The vendor copies (D-037, D-039, D-040): their parts' connections among themselves are the vendor's routing, changed
# only with the vendor's reference in hand (CLAUDE.md), so this pass leaves them alone.
COPIES = {
    "MB1355": {part["ours"] for part in RF.DATA["parts"]} | {"U301"},
    "MB1163": {part["ours"] for part in N.DATA["parts"]} | {"AE801"},
    "BOOST-DRV8711": {part["ours"] for part in D.DATA["parts"]},
}


def short(net):
    return net.split("/")[-1]


def copy_of(item):
    if item.GetClass() != "PAD":
        return None
    ref = item.GetParentFootprint().GetReference()
    return next((name for name, refs in COPIES.items() if ref in refs), None)


COPY_NETS = {
    "MB1355": {short(str(n)) for n in RF.DATA["net_map"].values()},
    "MB1163": {short(str(n)) for n in N.DATA["net_map"].values()},
    "BOOST-DRV8711": {short(str(n)) for n in D.DATA["net_map"].values()},
}


def vendor_internal(a, b):
    """A connection that is the vendor's own routing: a net of that copy between its own parts, or from one of its pads
    to loose copper of the net (D-055: vendor_gaps.py closes these from the reference)."""
    ca, cb = copy_of(a.item), copy_of(b.item)
    copy = ca or cb
    if copy is None or short(a.item.GetNetname()) not in COPY_NETS[copy]:
        return False
    if a.kind == "pad" and b.kind == "pad":
        return ca == cb
    return True


def uid(item):
    return item.m_Uuid.AsString()


def unit(v):
    n = math.hypot(v.x, v.y)
    return (v.x / n, v.y / n) if n else (0.0, 0.0)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def paths(a, b):
    """Straight when the two points lie on a 0 / 45 / 90-degree line, else the two one-bend paths (tidy_copper.two_legs)."""
    dx, dy = b.x - a.x, b.y - a.y
    if dx == 0 or dy == 0 or abs(abs(dx) - abs(dy)) <= 2:
        return [[a, b]]
    return [[a, m, b] for m in T.two_legs(a, b)]


def snap(a, b):
    """Terminals nearly on a 0 / 45 / 90-degree line (within SNAP): a pad end moves, inside its pad, onto the line, so
    the track is exact and has no micro-leg."""
    dx, dy = b.at.x - a.at.x, b.at.y - a.at.y
    tol = mm(SNAP)
    if 0 < abs(dx) < tol:
        shift = V(-dx, 0)
    elif 0 < abs(dy) < tol:
        shift = V(0, -dy)
    elif 0 < abs(abs(dx) - abs(dy)) < tol:
        shift = V(int(math.copysign(abs(dy) - abs(dx), dx)), 0)
    else:
        return a.at, b.at
    for term, sign in ((b, 1), (a, -1)):
        moved = term.at + V(shift.x * sign, shift.y * sign)
        if term.kind == "pad" and term.item.HitTest(moved):
            return (a.at, moved) if term is b else (moved, b.at)
    return a.at, b.at


def tee_problem(world, legs, layer, net):
    """A new leg over a same-net track's end, or ending on a track's middle: a tee, which the board never has
    (tidy_copper.branches_to_pads, pcb-design-rules track_junctions), even inside a pad."""
    hosts = [t for t in world.tracks if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net and t.GetLayer() == layer]
    for p, q in legs:
        seg = pcbnew.SEG(p, q)
        for t in hosts:
            if any(e not in (p, q) and seg.Distance(e) <= 1 for e in (t.GetStart(), t.GetEnd())):
                return "tee"
            if any(T.inside(e, t) for e in (p, q)):
                return "tee"
    return None


class Islands:
    """Union-find over the board's copper, seeded from KiCad's connectivity."""

    def __init__(self, board):
        self.parent = {}
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        items = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() > 0]
        items += [t for t in board.GetTracks() if t.GetNetCode() > 0]
        for item in items:
            for other in conn.GetConnectedItems(item):
                self.union(uid(item), uid(other))
        for fp in board.GetFootprints():
            first = {}
            for pad in fp.Pads():
                if pad.GetNetCode() > 0:
                    self.union(uid(pad), uid(first.setdefault(pad.GetNumber(), pad)))

    def find(self, key):
        self.parent.setdefault(key, key)
        root = key
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


class Terminal:
    """Where a new track may start: a pad's centre, a via, or a track end that nothing else meets."""

    def __init__(self, item, at, track=None):
        self.item, self.at, self.track = item, at, track
        self.kind = "via" if item.GetClass() == "PCB_VIA" else ("pad" if item.GetClass() == "PAD" else "end")

    def layers(self):
        if self.kind == "end":
            return [self.track.GetLayer()]
        return [layer for layer in OUTER if self.item.IsOnLayer(layer)]

    def name(self):
        if self.kind == "pad":
            return f"{self.item.GetParentFootprint().GetReference()}.{self.item.GetNumber()}"
        return f"{self.kind} ({self.at.x / 1e6 - 100:.2f}, {150 - self.at.y / 1e6:.2f})"


class World:
    def __init__(self, board):
        self.board = board
        self.pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
        self.tracks = list(board.GetTracks())
        self.fills = defaultdict(list)
        self.keep_tracks = defaultdict(list)
        self.keep_vias = []
        owned = [zone for fp in board.GetFootprints() for zone in fp.Zones()]
        for zone in list(board.Zones()) + owned:
            if zone.GetIsRuleArea():
                for layer in COPPER:
                    if zone.IsOnLayer(layer) and zone.GetDoNotAllowTracks():
                        self.keep_tracks[layer].append(pcbnew.SHAPE_POLY_SET(zone.Outline()))
                if zone.GetDoNotAllowVias():
                    self.keep_vias.append(pcbnew.SHAPE_POLY_SET(zone.Outline()))
                continue
            gap = max(POUR_GAP, zone.GetLocalClearance() / 1e6 if zone.GetLocalClearance() else 0)
            for layer in COPPER:
                if zone.IsOnLayer(layer):
                    poly = zone.GetFilledPolysList(layer)
                    if poly.OutlineCount():
                        self.fills[layer].append((zone.GetNetCode(), pcbnew.SHAPE_POLY_SET(poly), mm(gap)))
        self.plane = next(z for z in board.Zones() if z.GetZoneName() == P.PLANE)
        self.plane_fill = pcbnew.SHAPE_POLY_SET(self.plane.GetFilledPolysList(pcbnew.In1_Cu))
        outline = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(outline, False)
        box = outline.BBox()
        self.outside = pcbnew.SHAPE_POLY_SET()
        self.outside.NewOutline()
        grow = mm(5)
        for x, y in ((box.GetLeft() - grow, box.GetTop() - grow), (box.GetRight() + grow, box.GetTop() - grow),
                     (box.GetRight() + grow, box.GetBottom() + grow), (box.GetLeft() - grow, box.GetBottom() + grow)):
            self.outside.Append(x, y)
        self.outside.BooleanSubtract(outline)
        self.courts = []
        self.bodies = {fp.GetReference(): PB.body(fp) for fp in board.GetFootprints()}
        for fp in board.GetFootprints():
            fp.BuildCourtyardCaches()
            for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                court = fp.GetCourtyard(layer)
                if court.OutlineCount():
                    self.courts.append((fp.GetReference(), pcbnew.SHAPE_POLY_SET(court)))
        self.labels = []
        for fp in board.GetFootprints():
            if B.silk_label(fp) is not None and fp.Value().IsVisible():
                box = fp.Value().GetBoundingBox()
                rect = pcbnew.SHAPE_POLY_SET()
                rect.NewOutline()
                for x, y in ((box.GetLeft(), box.GetTop()), (box.GetRight(), box.GetTop()),
                             (box.GetRight(), box.GetBottom()), (box.GetLeft(), box.GetBottom())):
                    rect.Append(x, y)
                self.labels.append(rect)

    def near(self, items, centre, radius):
        return [i for i in items if (i.GetPosition() - centre).EuclideanNorm() <= radius + E.reach(i)]

    def add(self, item):
        self.board.Add(item)
        T.KEEP.append(item)
        self.tracks.append(item)

    def remove(self, item):
        self.board.Remove(item)
        self.tracks = [t for t in self.tracks if uid(t) != uid(item)]

    # Tracks.

    def track_problem(self, a, b, layer, width, probe, own, pours=True):
        """Why a track from a to b on this layer would break a rule, or None. own: the terminals it joins. pours=False
        leaves other nets' pours out (a vendor's own track, which its pour flows around when refilled)."""
        shape = pcbnew.SHAPE_SEGMENT(a, b, width)
        half = width // 2
        if self.outside.Collide(shape, mm(EDGE)):
            return "edge"
        if any(area.Collide(shape, 0) for area in self.keep_tracks[layer]):
            return "rule area"
        own_ids = {uid(t.item) for t in own} | {uid(t.track) for t in own if t.track is not None}
        meeting = [t.item.GetEffectiveShape(layer) if t.kind != "end" else pcbnew.SHAPE_CIRCLE(t.at, t.track.GetWidth() // 2)
                   for t in own]
        middle = V((a.x + b.x) // 2, (a.y + b.y) // 2)
        radius = (b - a).EuclideanNorm() / 2 + half + mm(NEAR)
        for pad in self.near(self.pads, middle, radius):
            if uid(pad) in own_ids:
                continue
            if pad.HasHole() and pad.GetNetCode() != probe.GetNetCode():
                gap = NPTH_TO_COPPER if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else PAD_HOLE_TO_COPPER
                if pad.GetEffectiveHoleShape().Collide(shape, mm(gap)):
                    return f"hole {pad.GetParentFootprint().GetReference()}"
            if not pad.IsOnLayer(layer):
                continue
            if pad.GetNetCode() == probe.GetNetCode() and pad.GetNetCode() > 0:
                if pad.GetEffectiveShape(layer).Collide(shape, 0):
                    return f"own net at {pad.GetParentFootprint().GetReference()}"
                continue
            if pad.GetEffectiveShape(layer).Collide(shape, mm(R.rule_clearance(pad, probe))):
                return f"pad {pad.GetParentFootprint().GetReference()}"
        for item in self.near(self.tracks, middle, radius):
            if uid(item) in own_ids:
                continue
            via = item.GetClass() == "PCB_VIA"
            if via and item.GetNetCode() != probe.GetNetCode() and \
                    item.GetEffectiveHoleShape().Collide(shape, mm(HOLE_TO_COPPER)):
                return "via hole"
            if not item.IsOnLayer(layer):
                continue
            theirs = item.GetEffectiveShape(layer)
            if item.GetNetCode() == probe.GetNetCode():
                if theirs.Collide(shape, 0) and self.touches_elsewhere(theirs, a, b, half, meeting):
                    return "own net copper"
                continue
            if theirs.Collide(shape, mm(R.rule_clearance(item, probe))):
                return "via" if via else "track"
        for net, poly, gap in (self.fills[layer] if pours else ()):
            if net != probe.GetNetCode() and poly.Collide(shape, gap):
                return "pour"
        return None

    def touches_elsewhere(self, theirs, a, b, half, meeting):
        """Same-net copper touching the new track anywhere but at the terminals it joins (where tracks meet)."""
        length = (b - a).EuclideanNorm()
        steps = max(1, int(length / mm(SAMPLE)))
        for i in range(steps + 1):
            p = V(a.x + (b.x - a.x) * i // steps, a.y + (b.y - a.y) * i // steps)
            dot_ = pcbnew.SHAPE_CIRCLE(p, max(1, half))
            if any(shape.Collide(dot_, 2 * half) for shape in meeting):
                continue
            if theirs.Collide(dot_, 0):
                return True
        return False

    # Vias.

    def via_problem(self, at, diameter, drill, probe, pad, nearby):
        ring = pcbnew.SHAPE_CIRCLE(at, diameter // 2)
        hole = pcbnew.SHAPE_CIRCLE(at, drill // 2)
        if self.outside.Collide(ring, mm(EDGE)):
            return "edge"
        if not self.plane_fill.Contains(at):
            return "no plane"
        if any(area.Collide(ring, 0) for area in self.keep_vias):
            return "rule area"
        ref = pad.GetParentFootprint().GetReference()
        if any(owner != ref and court.Collide(ring, 0) for owner, court in self.courts):
            return "courtyard"
        if self.bodies[ref].Collide(ring, 0):
            return "under its part"
        if any(label.Collide(ring, mm(LABEL_GAP)) for label in self.labels):
            return "label"
        pads, tracks = nearby
        for other in pads:
            if other.HasHole():
                if other.GetEffectiveHoleShape().Collide(hole, mm(HOLE_TO_HOLE)):
                    return "hole"
                if other.GetNetCode() != probe.GetNetCode():
                    gap = NPTH_TO_COPPER if other.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else PAD_HOLE_TO_COPPER
                    if other.GetEffectiveHoleShape().Collide(ring, mm(gap)):
                        return "hole"
            for layer in COPPER:
                if not other.IsOnLayer(layer):
                    continue
                shape = other.GetEffectiveShape(layer)
                if other.GetNetCode() == probe.GetNetCode():
                    if shape.Collide(ring, mm(VIA_WEB)):
                        return "in a pad"
                elif shape.Collide(ring, mm(R.rule_clearance(other, probe))) or \
                        shape.Collide(hole, mm(HOLE_TO_COPPER)):
                    return "pad"
        for item in tracks:
            if item.GetClass() == "PCB_VIA" and item.GetEffectiveHoleShape().Collide(hole, mm(HOLE_TO_HOLE)):
                return "via hole"
            for layer in COPPER:
                if not item.IsOnLayer(layer):
                    continue
                shape = item.GetEffectiveShape(layer)
                if item.GetNetCode() == probe.GetNetCode():
                    if shape.Collide(ring, 0):
                        return "own net track"
                elif shape.Collide(ring, mm(R.rule_clearance(item, probe))) or shape.Collide(hole, mm(HOLE_TO_COPPER)):
                    return "track"
        for layer in COPPER:
            for net, poly, gap in self.fills[layer]:
                if net != probe.GetNetCode() and poly.Collide(ring, gap):
                    return "pour"
        return None


def probe_for(board, net):
    probe = pcbnew.PCB_TRACK(board)
    probe.SetNet(net)
    T.KEEP.append(probe)
    return probe


def link_width(net_class, a, b):
    """The class width, narrowed to a narrower pad (never below MIN_WIDTH); a gap takes the narrower track's width."""
    width = WIDTH.get(net_class, WIDTH["Default"])
    for t in (a, b):
        if t.kind == "end":
            width = min(width, t.track.GetWidth() / 1e6)
    if net_class not in FULL_WIDTH:
        for t in (a, b):
            if t.kind == "pad":
                width = min(width, min(t.item.GetSize().x, t.item.GetSize().y) / 1e6)
            elif t.kind == "via":
                width = min(width, t.item.GetWidth(pcbnew.F_Cu) / 1e6)
    return mm(max(MIN_WIDTH, round(width, 4)))


def angle_ok(term, leg_end, layer, world):
    """A track end goes on within 45 degrees; at a via, every pair of tracks meets at 135 degrees or more and no third
    track joins (pcb-design-rules: track_angle, track_junctions)."""
    leg = unit(leg_end - term.at)
    if term.kind == "end":
        t = term.track
        far = t.GetStart() if t.GetEnd() == term.at else t.GetEnd()
        return dot(unit(term.at - far), leg) >= COS45
    if term.kind == "via":
        meeting = [t for t in world.tracks if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == term.item.GetNetCode()
                   and t.GetLayer() == layer and term.at in (t.GetStart(), t.GetEnd())]
        if len(meeting) >= 2:
            return False
        for t in meeting:
            far = t.GetStart() if t.GetEnd() == term.at else t.GetEnd()
            if dot(unit(far - term.at), leg) > -COS45:
                return False
    return True


def terminals(board):
    """Per net: its pads' centres, its vias, and its track ends that meet nothing else."""
    found = defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() > 0 and any(pad.IsOnLayer(layer) for layer in OUTER):
                found[pad.GetNetCode()].append(Terminal(pad, pad.GetPosition()))
    tracks = list(board.GetTracks())
    ends = defaultdict(list)
    for t in tracks:
        if t.GetClass() == "PCB_VIA":
            found[t.GetNetCode()].append(Terminal(t, t.GetPosition()))
        elif t.GetClass() == "PCB_TRACK":
            for p in (t.GetStart(), t.GetEnd()):
                ends[(t.GetNetCode(), t.GetLayer(), p.x, p.y)].append(t)
    vias = {(t.GetNetCode(), t.GetPosition().x, t.GetPosition().y) for t in tracks if t.GetClass() == "PCB_VIA"}
    pads = defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pads[pad.GetNetCode()].append(pad)
    for (net, layer, x, y), meeting in ends.items():
        if len(meeting) != 1 or (net, x, y) in vias or net <= 0:
            continue
        at = V(x, y)
        dot_ = pcbnew.SHAPE_CIRCLE(at, 1)
        if any(p.IsOnLayer(layer) and p.GetEffectiveShape(layer).Collide(dot_, 0) for p in pads[net]):
            continue
        found[net].append(Terminal(meeting[0], at, track=meeting[0]))
    return found


def candidates(board, islands, found):
    """Pairs of terminals of one net in different islands, within reach: links (pad to pad) up to MAX_LINK, gaps up to
    MAX_GAP, GND ties between one part's pads up to GND_TIE. Shortest first."""
    pairs = []
    for net, terms in found.items():
        if not terms:
            continue
        name = short(terms[0].item.GetNetname())
        net_class = terms[0].item.GetNetClassName()
        if net_class in SKIP_CLASSES:
            continue
        for i, a in enumerate(terms):
            for b in terms[i + 1:]:
                if islands.find(uid(a.item)) == islands.find(uid(b.item)):
                    continue
                if a.kind == "end" and b.kind == "end" and uid(a.track) == uid(b.track):
                    continue
                if vendor_internal(a, b):
                    continue
                length = (b.at - a.at).EuclideanNorm() / 1e6
                both_pads = a.kind == "pad" and b.kind == "pad"
                if name == GND:
                    if not (both_pads and length <= GND_TIE and not a.item.HasHole() and not b.item.HasHole()
                            and a.item.GetParentFootprint().GetReference() == b.item.GetParentFootprint().GetReference()):
                        continue
                    kind = "tie"
                elif both_pads:
                    if length > MAX_LINK:
                        continue
                    kind = "link"
                else:
                    if length > MAX_GAP:
                        continue
                    kind = "gap"
                pairs.append((length, kind, a, b))
    pairs.sort(key=lambda p: (p[0], p[2].name(), p[3].name()))
    return pairs


def find_route(board, world, kind, a, b):
    """The first path that breaks no rule: (layer, legs, width), or (None, reason)."""
    width = link_width(a.item.GetNetClassName(), a, b)
    probe = probe_for(board, a.item.GetNet())
    why = "no shared layer"
    start, end = snap(a, b)
    for layer in [layer for layer in a.layers() if layer in b.layers()]:
        for path in paths(start, end):
            if not (angle_ok(a, path[1], layer, world) and angle_ok(b, path[-2], layer, world)):
                why = "angle"
                continue
            legs = [(p, q) for p, q in zip(path, path[1:]) if p != q]
            why = tee_problem(world, legs, layer, a.item.GetNetCode())
            why = why or next((w for w in (world.track_problem(p, q, layer, width, probe, (a, b)) for p, q in legs) if w),
                              None)
            if why is None:
                return (layer, legs, width), None
    return None, why


def lay(board, world, net, layer, legs, width):
    tracks = []
    for p, q in legs:
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(p)
        track.SetEnd(q)
        track.SetWidth(width)
        track.SetLayer(layer)
        track.SetNet(net)
        world.add(track)
        tracks.append(track)
    return tracks


def crystal_of(a, b):
    """The crystal a CLK-class pair belongs to (its Y part), so both of its nets are routed or neither."""
    for t in (a, b):
        if t.kind == "pad" and t.item.GetParentFootprint().GetReference().startswith("Y"):
            return t.item.GetParentFootprint().GetReference()
    return short(a.item.GetNetname())


def route_pairs(board, world, islands, pairs):
    """Crystal pairs first, each crystal's nets together or not at all (docs/power-map.md: short and symmetric); then
    every other pair, shortest first."""
    routed, refused = [], defaultdict(int)
    crystals = defaultdict(list)
    for pair in pairs:
        if pair[2].item.GetNetClassName() == "CLK":
            crystals[crystal_of(pair[2], pair[3])].append(pair)
    for name in sorted(crystals):
        laid, done, nets = [], [], set()
        for length, kind, a, b in crystals[name]:
            nets.add(a.item.GetNetCode())
            if a.item.GetNetCode() in {d[2].item.GetNetCode() for d in done}:
                continue
            found, why = find_route(board, world, kind, a, b)
            if found is None:
                refused[f"{kind}: crystal {name} ({why.split(' ')[0]})"] += 1
                continue
            tracks = lay(board, world, a.item.GetNet(), *found)
            laid += tracks
            done.append((length, kind, a, b, found, tracks))
        if {d[2].item.GetNetCode() for d in done} != nets:
            for track in laid:
                world.remove(track)
            continue
        for length, kind, a, b, (layer, legs, width), tracks in done:
            for track in tracks:
                islands.union(uid(track), uid(a.item))
            islands.union(uid(a.item), uid(b.item))
            routed.append((kind, short(a.item.GetNetname()), a.name(), b.name(), width / 1e6, length,
                           board.GetLayerName(layer), len(legs)))
    for length, kind, a, b in pairs:
        if a.item.GetNetClassName() == "CLK" or islands.find(uid(a.item)) == islands.find(uid(b.item)):
            continue
        found, why = find_route(board, world, kind, a, b)
        if found is None:
            refused[f"{kind}: {why.split(' ')[0]}"] += 1
            continue
        layer, legs, width = found
        for track in lay(board, world, a.item.GetNet(), layer, legs, width):
            islands.union(uid(track), uid(a.item))
        islands.union(uid(a.item), uid(b.item))
        routed.append((kind, short(a.item.GetNetname()), a.name(), b.name(), width / 1e6, length,
                       board.GetLayerName(layer), len(legs)))
    return routed, refused


def via_spot(world, pad, probe):
    """The nearest via spot outward from the pad: (stub length, at, diameter, drill, layer, stub width) or None."""
    fp = pad.GetParentFootprint()
    layer = next(layer for layer in OUTER if pad.IsOnLayer(layer))
    centre = pad.GetPosition()
    outward = unit(centre - fp.GetPosition())
    dirs = sorted(DIRECTIONS, key=lambda d: -dot(outward, (d[0] / math.hypot(*d), d[1] / math.hypot(*d))))
    nearby = (world.near(world.pads, centre, mm(VIA_REACH + 3)), world.near(world.tracks, centre, mm(VIA_REACH + 3)))
    pad_shape = pad.GetEffectiveShape(layer)
    stub = mm(max(STUB_WIDTH[0], min(STUB_WIDTH[1], min(pad.GetSize().x, pad.GetSize().y) / 1e6)))
    own = (Terminal(pad, centre),)
    for diameter_mm, drill_mm in VIA_SIZES:
        diameter, drill = mm(diameter_mm), mm(drill_mm)
        best = None
        for dx, dy in dirs:
            n = math.hypot(dx, dy)
            start = None
            for k in range(int(round((VIA_REACH + 3) / STEP))):
                d = k * STEP
                at = V(centre.x + int(round(mm(d) * dx / n)), centre.y + int(round(mm(d) * dy / n)))
                ring = pcbnew.SHAPE_CIRCLE(at, diameter // 2)
                if pad_shape.Collide(ring, mm(VIA_WEB)):
                    continue
                if start is None:
                    start = d
                if d - start > VIA_REACH or (best and d >= best[0]):
                    break
                if world.via_problem(at, diameter, drill, probe, pad, nearby):
                    continue
                width = min(stub, diameter)
                if tee_problem(world, [(centre, at)], layer, pad.GetNetCode()) or \
                        world.track_problem(centre, at, layer, width, probe, own):
                    continue
                best = (d, at, diameter, drill, layer, width)
                break
        if best:
            return best
    return None


def ground_islands(board, world, islands, copies=False):
    """One via per GND island that is off the plane (on the vendor copies' pads too when copies is set)."""
    gnd = board.FindNet(GND).GetNetCode()
    plane = islands.find(uid(world.plane))
    groups = defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == gnd and not pad.HasHole() and islands.find(uid(pad)) != plane and \
                    (copies or copy_of(pad) is None):
                groups[islands.find(uid(pad))].append(pad)
    added, failed = [], []
    probe = probe_for(board, board.FindNet(GND))
    for key in sorted(groups, key=lambda k: min(f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}" for p in groups[k])):
        pads = sorted(groups[key], key=lambda p: (p.GetParentFootprint().GetReference(), p.GetNumber()))
        spots = [(spot, pad) for pad in pads for spot in [via_spot(world, pad, probe)] if spot]
        names = "+".join(f"{p.GetParentFootprint().GetReference()}.{p.GetNumber()}" for p in pads)
        if not spots:
            failed.append(names)
            continue
        (d, at, diameter, drill, layer, width), pad = min(spots, key=lambda s: (-s[0][2], s[0][0]))
        via = pcbnew.PCB_VIA(board)
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetPosition(at)
        via.SetWidth(diameter)
        via.SetDrill(drill)
        via.SetNet(pad.GetNet())
        world.add(via)
        stub = pcbnew.PCB_TRACK(board)
        stub.SetStart(pad.GetPosition())
        stub.SetEnd(at)
        stub.SetWidth(width)
        stub.SetLayer(layer)
        stub.SetNet(pad.GetNet())
        world.add(stub)
        for item in (via, stub, pad):
            islands.union(uid(item), plane)
        added.append((names, f"{pad.GetParentFootprint().GetReference()}.{pad.GetNumber()}",
                      (stub.GetLength()) / 1e6, diameter / 1e6, drill / 1e6, width / 1e6))
    return added, failed


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    world = World(board)
    islands = Islands(board)
    routed, refused = route_pairs(board, world, islands, candidates(board, islands, terminals(board)))
    vias, failed = ground_islands(board, world, islands)
    if not (routed or vias):
        print("nothing simple left to route: nothing to do")
        sys.exit(3)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for kind, net, a, b, width, length, layer, legs in routed:
        print(f"{kind:4} {net:14} {a:>22} -> {b:<22} {width:.3f} mm  {length:5.2f} mm  {layer}  {legs} leg(s)")
    for names, at, length, diameter, drill, width in vias:
        print(f"via  GND  {names:28} at {at:10} stub {length:.2f} mm x {width:.2f}  via {drill:.2f} / {diameter:.2f}")
    for names in failed:
        print(f"no via spot for GND {names}")
    print(f"{len(routed)} tracks ({sum(1 for r in routed if r[0] == 'link')} links, "
          f"{sum(1 for r in routed if r[0] == 'gap')} gaps, {sum(1 for r in routed if r[0] == 'tie')} GND ties), "
          f"{len(vias)} GND vias; refused: {dict(sorted(refused.items()))}")
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="route the simple connections (one shot)")
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
