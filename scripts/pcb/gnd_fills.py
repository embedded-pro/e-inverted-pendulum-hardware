#!/usr/bin/env python3
"""Ground fills on L1 and L4, stitched to the L2 plane every 5 mm (D-061).

    python3 scripts/pcb/gnd_fills.py --apply

docs/plan.md gives L4 to signals and a GND fill; power-pcb-layout s4 step 6 asks for fills and GND stitching about every
5 mm. This adds:
  - L1_GND (F.Cu) and L4_GND (B.Cu): GND pours over the whole outline at the lowest priority, so every other pour wins
    where they meet. They leave out the vendor copies' own areas, where the copied pours stand as drawn (D-037, D-039,
    D-040): ST's RF strip, TI's drive box and, on B.Cu, ST's NFC ground. The board's rule areas carve the rest: the
    antenna tab, the NFC coil and its pour gap, the bracket base on the back and the buck's quiet area. Settings are
    those of the L2 plane: 0.2 mm clearance, 0.25 mm minimum width, solid to SMD pads, thermal reliefs on through-hole
    pins.
  - Stitching vias, 0.3 / 0.6 mm, on a 5 mm lattice (a point with no room takes the nearest spot within 1.5 mm). One
    goes wherever an outer layer has GND fill and the via fits the board's rules: other nets' copper and pours, holes, keep-outs, no part's courtyard, the edge. It also goes where only
    TI's GND fill is. No stitching via goes in ST's RF strip,
    which has its own 1.2 mm grid (D-049), in the NFC keep-outs, or in L3's VBAT corridor, which stays solid (D-056).
Each piece of TI's GND fills that the routing cut off (no copper path to the plane) gets one GND via where it fits, as TI's
own vias tie its ground to the plane; it passes L3's VBAT corridor there, as TI's do. Islands of our fills that no via
or pad reaches are removed, then every zone is refilled. One shot: a no-op once both fills are on the
board. Nothing is locked (D-045).
"""

import argparse
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import gnd_vias as G  # noqa: E402
import route_phases as RP  # noqa: E402
import route_simple as RS  # noqa: E402

B.pcbnew = pcbnew
mm = pcbnew.FromMM
FILLS = (("L1_GND", "F.Cu"), ("L4_GND", "B.Cu"))
CLEARANCE = 0.2
MIN_WIDTH = 0.25
THERMAL_GAP = 0.3
THERMAL_SPOKE = 0.5
PITCH = 5.0
VIA = (0.6, 0.3)
FILL_MARGIN = 0.6
# Our outlines keep this off the vendor copies' GND pours (same net, same priority: DRC flags zones that intersect).
OUTLINE_GAP = 0.1
# A stitching via keeps this off every silkscreen name (silk.py lays the test pads' names clear of vias).
LABEL_GAP = 0.2
# A lattice point with no room tries the nearest spots within SEARCH mm (STEP grid), closest first.
SEARCH = 1.5
STEP = 0.25
OFFSETS = sorted(((i * STEP, j * STEP) for i in range(-int(SEARCH / STEP), int(SEARCH / STEP) + 1)
                  for j in range(-int(SEARCH / STEP), int(SEARCH / STEP) + 1)
                  if (i * STEP) ** 2 + (j * STEP) ** 2 <= SEARCH ** 2), key=lambda d: (d[0] ** 2 + d[1] ** 2, d))
TI_BOX_ZONE = "BOOST-DRV8711 F.Cu GND 0"
NFC_GROUND = "MB1163 B.Cu GND"
NO_STITCH = ("NFC_COIL", "NFC_POUR_GAP", "ANTENNA_TAB", "L3_VBAT")
TI_GROUND = ("BOOST-DRV8711 F.Cu GND 0", "BOOST-DRV8711 B.Cu GND 1")
KEEP = []


def rectangle(x0, x1, z0, z1):
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
        poly.Append(B.to_board(x, z))
    return poly


def zone_named(board, name):
    return next((z for z in board.Zones() if z.GetZoneName() == name), None)


def exclusions(board, layer_name):
    """The vendor copies' own areas, which our fill leaves to their pours."""
    out = pcbnew.SHAPE_POLY_SET()
    out.Append(rectangle(*G.strip_rectangle()))
    out.Append(pcbnew.SHAPE_POLY_SET(zone_named(board, TI_BOX_ZONE).Outline()))
    if layer_name == "B.Cu" and zone_named(board, NFC_GROUND):
        out.Append(pcbnew.SHAPE_POLY_SET(zone_named(board, NFC_GROUND).Outline()))
    out.Simplify()
    out.Inflate(mm(OUTLINE_GAP), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
    return out


def add_fill(board, name, layer_name, gnd):
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    outline.BooleanSubtract(exclusions(board, layer_name))
    zone = pcbnew.ZONE(board)
    zone.SetLayer(board.GetLayerID(layer_name))
    zone.SetNet(gnd)
    zone.SetZoneName(name)
    zone.SetAssignedPriority(0)
    for i in range(outline.OutlineCount()):
        index = zone.Outline().AddOutline(outline.Outline(i))
        for h in range(outline.HoleCount(i)):
            zone.Outline().AddHole(outline.Hole(i, h), index)
    zone.SetLocalClearance(mm(CLEARANCE))
    zone.SetMinThickness(mm(MIN_WIDTH))
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    zone.SetThermalReliefGap(mm(THERMAL_GAP))
    zone.SetThermalReliefSpokeWidth(mm(THERMAL_SPOKE))
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    board.Add(zone)
    KEEP.append(zone)
    return zone


def gnd_fill(board, layer):
    """Every GND zone's fill on this layer, shrunk by FILL_MARGIN so a via inside sits wholly on copper."""
    poly = pcbnew.SHAPE_POLY_SET()
    for zone in board.Zones():
        if not zone.GetIsRuleArea() and zone.IsOnLayer(layer) and RS.short(zone.GetNetname()) == "GND":
            poly.Append(pcbnew.SHAPE_POLY_SET(zone.GetFilledPolysList(layer)))
    poly.Simplify()
    poly.Deflate(mm(FILL_MARGIN), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
    return poly


def no_stitch(board):
    areas = [rectangle(*G.strip_rectangle())]
    for zone in board.Zones():
        if zone.GetZoneName() in NO_STITCH:
            areas.append(pcbnew.SHAPE_POLY_SET(zone.Outline()))
    return areas


def lattice(board):
    box = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(box, False)
    bbox = box.BBox()
    x0, x1 = pcbnew.ToMM(bbox.GetLeft()) - B.ORIGIN[0], pcbnew.ToMM(bbox.GetRight()) - B.ORIGIN[0]
    z0, z1 = B.ORIGIN[1] - pcbnew.ToMM(bbox.GetBottom()), B.ORIGIN[1] - pcbnew.ToMM(bbox.GetTop())
    points = []
    z = z0 + PITCH / 2
    while z < z1:
        x = x0 + PITCH / 2
        while x < x1:
            points.append((round(x, 3), round(z, 3)))
            x += PITCH
        z += PITCH
    return points


def stitch(board):
    fills = [gnd_fill(board, layer) for layer in (pcbnew.F_Cu, pcbnew.B_Cu)]
    avoid = no_stitch(board)
    world = RS.World(board)
    gnd = board.FindNet("GND")
    added, skipped = 0, 0
    for x, z in lattice(board):
        if not any(f.Contains(RP.at(x, z)) for f in fills):
            continue
        spot = next((RP.at(x + dx, z + dz) for dx, dz in OFFSETS
                     if fits(board, world, gnd, RP.at(x + dx, z + dz), fills, avoid)), None)
        if spot is None:
            skipped += 1
            continue
        RP.add_via(board, world, gnd, spot, VIA)
        added += 1
    return added, skipped


def fits(board, world, gnd, at, fills, avoid, stitch=True):
    if not any(f.Contains(at) for f in fills) or any(a.Contains(at) for a in avoid):
        return False
    ring = pcbnew.SHAPE_CIRCLE(at, mm(VIA[0]) // 2)
    if any(court.Collide(ring, 0) for _, court in world.courts):
        return False
    if any(label.Collide(ring, mm(LABEL_GAP)) for label in world.labels):
        return False
    return not RP.via_problems(board, world, gnd, at, VIA)


def cut_off(board, names):
    """Pieces of these GND zones' fills with no copper path to the L2 plane: a union-find over every GND fill piece on
    F.Cu / B.Cu, GND pad, track and via (KiCad's connectivity holds a zone as one item, not per piece). Every via and
    through-hole pad reaches the plane."""
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        parent[find(a)] = find(b)

    gnd = board.FindNet("GND").GetNetCode()
    pieces = []
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetCode() != gnd:
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not zone.IsOnLayer(layer):
                continue
            fill = zone.GetFilledPolysList(layer)
            for i in range(fill.OutlineCount()):
                piece = pcbnew.SHAPE_POLY_SET(fill.Outline(i))
                for h in range(fill.HoleCount(i)):
                    piece.AddHole(fill.Hole(i, h), 0)
                pieces.append((("piece", len(pieces)), zone.GetZoneName(), layer, piece, piece.BBox()))
    items = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == gnd]
    items += [t for t in board.GetTracks() if t.GetNetCode() == gnd]
    for item in items:
        key = RS.uid(item)
        find(key)
        if item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole()):
            union(key, "plane")
        box = item.GetBoundingBox()
        for pkey, _, layer, piece, pbox in pieces:
            if item.IsOnLayer(layer) and pbox.Intersects(box) and piece.Collide(item.GetEffectiveShape(layer), 0):
                union(key, pkey)
    boxes = [item.GetBoundingBox() for item in items]
    for i, item in enumerate(items):
        if item.GetClass() != "PCB_TRACK":
            continue
        for j, other in enumerate(items):
            if j == i or not boxes[i].Intersects(boxes[j]):
                continue
            if any(other.IsOnLayer(lay) and item.IsOnLayer(lay) and
                   other.GetEffectiveShape(lay).Collide(item.GetEffectiveShape(lay), 0) for lay in (pcbnew.F_Cu, pcbnew.B_Cu)):
                union(RS.uid(item), RS.uid(other))
    for item in items:
        if item.GetClass() == "PAD":
            for other in items:
                if other.GetClass() == "PAD" and other.GetParentFootprint() is item.GetParentFootprint() and \
                        other.GetNumber() == item.GetNumber():
                    union(RS.uid(item), RS.uid(other))
    plane = find("plane")
    return [(name, layer, piece) for pkey, name, layer, piece, _ in pieces if name in names and find(pkey) != plane]


def repair_islands(board):
    """One GND via in each piece of TI's GND fills that the routing cut off: TI's own vias tie its ground to the plane."""
    world = RS.World(board)
    gnd = board.FindNet("GND")
    added = 0
    for name, layer, piece in cut_off(board, TI_GROUND):
        inner = pcbnew.SHAPE_POLY_SET(piece)
        inner.Deflate(mm(VIA[0] / 2 + 0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
        if not inner.OutlineCount():
            continue
        box = inner.BBox()
        spot = None
        y = box.GetTop()
        while y <= box.GetBottom() and spot is None:
            x = box.GetLeft()
            while x <= box.GetRight():
                at = pcbnew.VECTOR2I(x, y)
                if inner.Contains(at) and fits(board, world, gnd, at, [inner], [], stitch=False):
                    spot = at
                    break
                x += mm(STEP)
            y += mm(STEP)
        if spot is not None:
            RP.add_via(board, world, gnd, spot, VIA)
            added += 1
    return added


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    names = {z.GetZoneName() for z in board.Zones()}
    if all(name in names for name, _ in FILLS):
        print("L1 and L4 ground fills are on the board: nothing to do")
        sys.exit(3)
    gnd = board.FindNet("GND")
    zones = [add_fill(board, name, layer, gnd) for name, layer in FILLS if name not in names]
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    added, skipped = stitch(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    repaired = repair_islands(board)
    for zone in zones:
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    area = {zone.GetZoneName(): zone.GetFilledPolysList(zone.GetLayer()).Area() / 1e12 for zone in zones}
    print(f"added {', '.join(f'{n} ({a:.0f} mm2 filled)' for n, a in area.items())}; {added} stitching vias "
          f"({PITCH} mm lattice; {skipped} lattice points on fill had no room); {repaired} vias tie cut-off pieces of TI's "
          f"GND fills to the plane")
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="add the L1 / L4 ground fills and stitching (one shot)")
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
