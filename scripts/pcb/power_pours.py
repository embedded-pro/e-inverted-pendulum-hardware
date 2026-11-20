#!/usr/bin/env python3
"""Power-bus copper: the L3 planes, the power entry's L1 pours and the via arrays between them (D-056).

    python3 scripts/pcb/power_pours.py --apply

docs/power-map.md gives the power bus (BAT_P → F101 → BAT_F → Q101 → PP_S → VBAT, 4.2 A) pours on L1 + L3, no necks
below 2.2 mm outer, and at least I / 1 A vias (0.3 mm drill) at every layer change. The owner chose L3 as one wide VBAT
corridor plus GND everywhere else (2026-11-16), so the bottom layer's signals keep a solid reference. This adds:
  - L3_VBAT on In2.Cu (placement.L3_VBAT): the corridor from the power entry past the buck input down over the drive, at
    least 11.3 mm wide (4.2 A on 0.5 oz inner copper, IPC-2221 at 10 degC); TI's VBAT vias under the bridges reach it.
    L3_GND under the rest of In2.Cu, lower priority. Both carved by the NFC and antenna keep-outs.
  - BUCK_SW_QUIET, a rule area on In2.Cu and B.Cu over the buck's switch node (its pads and copper plus 1 mm): no tracks
    and no pours under it on L3 / L4 (power map); vias stay allowed, so the buck's GND vias stand beside the node.
  - The L1 pours (placement.L1_POWER): BAT_P from J101 to F101, BAT_F from F101 to Q101, PP_S joining Q101's two sources
    (the full current) around gate pin 2, VBAT at Q101 and VBAT at the buck input. SMD pads solid, J101 on 4 spokes of
    0.6 mm (2.4 mm, above the 2.2 mm the current needs: power-pcb-layout, necks). The power entry's hops are under 6 mm
    and each pour is at least 2.2 mm wide, so they stay on L1.
  - VBAT via arrays from the L1 pours down to L3_VBAT, on a 0.25 mm search grid nearest the pads (tented vias may sit
    under a through-hole part's plastic body, J101's, and carve other nets' pours as TI's own vias do): at Q101 until the
    drills add up to 5 x 0.3 mm (the 4.2 A of the whole bus), at the buck input to 2 x 0.3 mm. Then one via at each
    VBAT pad still off the plane's island (the buck's EN divider R201, TP101, TI's bulk caps C502 / C506 outside TI's
    VBAT pours).
  - BAT_F's test pad TP102 joined to BAT_F by maze.Router at 0.3 mm: a test pad carries no current.
Checks: each L1 pour's fill deflated by 1.1 mm (half of 2.2 mm) stays one piece (no neck below 2.2 mm), the L3
corridor (its outline less the quiet area) deflated by 5.6 mm still joins the entry to the drive (11.2 mm or more all the
way), every power-bus net is one island.
One shot: a no-op once the pours are there. The zones are filled. Nothing is locked (D-045).
"""

import argparse
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import maze as M  # noqa: E402
import placement  # noqa: E402
import route_simple as RS  # noqa: E402

B.pcbnew = pcbnew
mm = pcbnew.FromMM
V = pcbnew.VECTOR2I
L3_VBAT, L3_GND, QUIET = "L3_VBAT", "L3_GND", "BUCK_SW_QUIET"
CLEARANCE = 0.2
MIN_WIDTH = 0.25
THERMAL_GAP = 0.3
THERMAL_SPOKE = 0.6
QUIET_MARGIN = 1.0
NECK = 1.1
CORRIDOR_NECK = 5.6
VIA = (0.6, 0.3)
SMALL_VIA = (0.45, 0.2)
SEARCH = 0.25
ARRAYS = {"L1_VBAT_ENTRY": 1.5, "L1_VBAT_BUCK": 0.6}
TEST_PADS = ("TP102.1",)
TEST_WIDTH = 0.3


def net_of(board, name):
    return next(n for n in board.GetNetsByName().values() if RS.short(n.GetNetname()) == name)


def outline(zone, points):
    poly = zone.Outline()
    poly.NewOutline()
    for x, z in points:
        poly.Append(B.to_board(x, z))


def pour(board, name, layer, net, points, priority, connection):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    zone.SetZoneName(name)
    zone.SetAssignedPriority(priority)
    if points is None:
        whole = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(whole, False)
        for i in range(whole.OutlineCount()):
            zone.Outline().AddOutline(whole.Outline(i))
    else:
        outline(zone, points)
    zone.SetLocalClearance(mm(CLEARANCE))
    zone.SetMinThickness(mm(MIN_WIDTH))
    zone.SetPadConnection(connection)
    zone.SetThermalReliefGap(mm(THERMAL_GAP))
    zone.SetThermalReliefSpokeWidth(mm(THERMAL_SPOKE))
    zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(zone)
    return zone


def quiet_area(board):
    """BUCK_SW's pads and copper, plus QUIET_MARGIN, as a rule area on In2.Cu and B.Cu."""
    net = net_of(board, "BUCK_SW").GetNetCode()
    box = pcbnew.BOX2I()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == net:
                box.Merge(pad.GetBoundingBox())
    for track in board.GetTracks():
        if track.GetNetCode() == net:
            box.Merge(track.GetBoundingBox())
    box.Inflate(mm(QUIET_MARGIN))
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetZoneName(QUIET)
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.In2_Cu)
    layers.AddLayer(pcbnew.B_Cu)
    zone.SetLayerSet(layers)
    poly = zone.Outline()
    poly.NewOutline()
    for x, y in ((box.GetLeft(), box.GetTop()), (box.GetRight(), box.GetTop()), (box.GetRight(), box.GetBottom()),
                 (box.GetLeft(), box.GetBottom())):
        poly.Append(x, y)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(False)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    board.Add(zone)
    return zone


def corridor(board):
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, z in placement.L3_VBAT:
        poly.Append(B.to_board(x, z))
    return poly


def zone_named(board, name):
    return next(z for z in board.Zones() if z.GetZoneName() == name)


def through_hole_parts(board):
    """Parts whose pads are all through-hole (connectors, the switch): a tented via under their plastic body is fine."""
    return {fp.GetReference() for fp in board.GetFootprints()
            if fp.Pads() and all(p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) for p in fp.Pads())}


def add_via(board, world, at, size, net):
    via = pcbnew.PCB_VIA(board)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetPosition(at)
    via.SetWidth(mm(size[0]))
    via.SetDrill(mm(size[1]))
    via.SetNet(net)
    world.add(via)
    return via


def array(board, world, router, name, target, plane):
    """Vias inside the L1 pour, nearest its pads first, until their drills add up to target (mm)."""
    zone = zone_named(board, name)
    net = zone.GetNet()
    probe = RS.probe_for(board, net)
    fill = pcbnew.SHAPE_POLY_SET(zone.GetFilledPolysList(pcbnew.F_Cu))
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()
            if p.GetNetCode() == net.GetNetCode() and zone.Outline().Contains(p.GetPosition())]
    box = zone.Outline().BBox()
    step = mm(SEARCH)
    points = [V(x, y) for x in range(box.GetLeft(), box.GetRight() + 1, step)
              for y in range(box.GetTop(), box.GetBottom() + 1, step)]
    points.sort(key=lambda p: min((p - q.GetPosition()).EuclideanNorm() for q in pads))
    total, added = 0.0, []
    for size in (VIA, SMALL_VIA):
        for at in points:
            if total >= target - 1e-9:
                break
            ring = pcbnew.SHAPE_CIRCLE(at, mm(size[0]) // 2)
            inner = pcbnew.SHAPE_POLY_SET(fill)
            inner.Deflate(mm(size[0] / 2 + 0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
            if not inner.Contains(at) or not plane.Contains(at):
                continue
            if any(p.GetEffectiveShape(pcbnew.F_Cu).Collide(ring, mm(0.1)) for p in pads):
                continue
            if router.via_problem(at, mm(size[0]), mm(size[1]), probe, own_net_ok=True,
                                  ignore_bodies=through_hole_parts(board), soft_pours=True):
                continue
            added.append(add_via(board, world, at, size, net))
            total += size[1]
    return added, total


def plane_via(board, world, router, pad, plane):
    """One via to the L3 plane at the pad: the nearest spot outward that fits, with a stub (route_simple.via_spot's
    search, with the plane's polygon in place of L2)."""
    fp = pad.GetParentFootprint()
    layer = next(layer for layer in RS.OUTER if pad.IsOnLayer(layer))
    centre = pad.GetPosition()
    outward = RS.unit(centre - fp.GetPosition())
    dirs = sorted(RS.DIRECTIONS, key=lambda d: -RS.dot(outward, (d[0] / math.hypot(*d), d[1] / math.hypot(*d))))
    probe = RS.probe_for(board, pad.GetNet())
    own = (RS.Terminal(pad, centre),)
    stub = mm(max(0.2, min(0.5, min(pad.GetSize().x, pad.GetSize().y) / 1e6)))
    shape = pad.GetEffectiveShape(layer)
    for size in (VIA, SMALL_VIA):
        best = None
        for dx, dy in dirs:
            n = math.hypot(dx, dy)
            start = None
            for k in range(80):
                d = k * 0.05
                at = V(centre.x + int(round(mm(d) * dx / n)), centre.y + int(round(mm(d) * dy / n)))
                if shape.Collide(pcbnew.SHAPE_CIRCLE(at, mm(size[0]) // 2), mm(0.1)):
                    continue
                start = d if start is None else start
                if d - start > 1.5 or (best and d >= best[0]):
                    break
                if not plane.Contains(at) or router.via_problem(at, mm(size[0]), mm(size[1]), probe,
                                                                ignore_bodies=through_hole_parts(board),
                                                                soft_pours=True):
                    continue
                width = min(stub, mm(size[0]))
                if RS.tee_problem(world, [(centre, at)], layer, pad.GetNetCode()) or \
                        world.track_problem(centre, at, layer, width, probe, own, pours=False):
                    continue
                best = (d, at, width, layer)
                break
        if best:
            d, at, width, layer = best
            RS.lay(board, world, pad.GetNet(), layer, [(centre, at)], width)
            return add_via(board, world, at, size, pad.GetNet()), size
    return None, None


def pad_named(board, name):
    ref, number = name.split(".")
    return next(p for p in board.FindFootprintByReference(ref).Pads() if p.GetNumber() == number)


def deflated_pieces(poly, by):
    shrunk = pcbnew.SHAPE_POLY_SET(poly)
    shrunk.Deflate(mm(by), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
    return shrunk


def checks(board):
    problems = []
    for name, (net, _) in placement.L1_POWER.items():
        zone = zone_named(board, name)
        fill = zone.GetFilledPolysList(pcbnew.F_Cu)
        shrunk = deflated_pieces(fill, NECK)
        if fill.OutlineCount() != 1:
            problems.append(f"{name}: {fill.OutlineCount()} pieces")
        elif shrunk.OutlineCount() != 1:
            problems.append(f"{name}: {shrunk.OutlineCount()} pieces once deflated by {NECK} mm (a neck below 2.2 mm)")
    body = pcbnew.SHAPE_POLY_SET(zone_named(board, L3_VBAT).Outline())
    body.BooleanSubtract(zone_named(board, QUIET).Outline())
    shrunk = deflated_pieces(body, CORRIDOR_NECK)
    ends = [B.to_board(-33.0, 55.5), B.to_board(10.0, 25.0)]
    where = [next((i for i in range(shrunk.OutlineCount()) if shrunk.Outline(i).PointInside(p)), None) for p in ends]
    if None in where or where[0] != where[1]:
        problems.append(f"L3_VBAT: the corridor deflated by {CORRIDOR_NECK} mm does not join the entry to the drive")
    board.BuildConnectivity()
    islands = RS.Islands(board)
    for name in ("BAT_P", "BAT_F", "PP_S", "VBAT"):
        code = net_of(board, name).GetNetCode()
        roots = {islands.find(RS.uid(p)) for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetCode() == code}
        if len(roots) != 1:
            problems.append(f"{name}: {len(roots)} islands")
    return problems


def apply(board):
    names = {zone.GetZoneName() for zone in board.Zones()}
    wanted = [L3_VBAT, L3_GND, QUIET] + list(placement.L1_POWER)
    if all(name in names for name in wanted):
        print("the power-bus copper is on the board: nothing to do")
        sys.exit(3)
    quiet_area(board)
    pour(board, L3_VBAT, pcbnew.In2_Cu, net_of(board, "VBAT"), placement.L3_VBAT, 1, pcbnew.ZONE_CONNECTION_THT_THERMAL)
    pour(board, L3_GND, pcbnew.In2_Cu, net_of(board, "GND"), None, 0, pcbnew.ZONE_CONNECTION_THT_THERMAL)
    for name, (net, points) in placement.L1_POWER.items():
        pour(board, name, pcbnew.F_Cu, net_of(board, net), points, 2, pcbnew.ZONE_CONNECTION_THT_THERMAL)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    world = RS.World(board)
    islands = RS.Islands(board)
    router = M.Router(board, world, islands)
    plane = corridor(board)
    plane.Deflate(mm(0.6), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))
    report = []
    for name, target in ARRAYS.items():
        vias, total = array(board, world, router, name, target, plane)
        report.append(f"{name}: {len(vias)} vias, drills {total:.2f} mm (target {target:.2f})")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    islands = RS.Islands(board)
    main = islands.find(RS.uid(zone_named(board, L3_VBAT)))
    code = net_of(board, "VBAT").GetNetCode()
    for fp in sorted(board.GetFootprints(), key=lambda f: f.GetReference()):
        for pad in fp.Pads():
            if pad.GetNetCode() != code or pad.HasHole() or islands.find(RS.uid(pad)) == main:
                continue
            via, size = plane_via(board, world, router, pad, plane)
            name = f"{fp.GetReference()}.{pad.GetNumber()}"
            report.append(f"{name}: " + (f"via {size[1]:.2f} / {size[0]:.2f} to L3" if via else "no via spot"))
            if via:
                islands.union(RS.uid(pad), main)
                islands.union(RS.uid(via), main)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    islands = RS.Islands(board)
    router = M.Router(board, RS.World(board), islands)
    for name in TEST_PADS:
        pad = pad_named(board, name)
        terms = [t for t in RS.terminals(board)[pad.GetNetCode()]
                 if islands.find(RS.uid(t.item)) != islands.find(RS.uid(pad))]
        target = RS.Terminal(pad, pad.GetPosition())
        done = None
        for t in sorted(terms, key=lambda t: (t.at - pad.GetPosition()).EuclideanNorm()):
            result, why = router.route(target, t, mm(TEST_WIDTH), allow_vias=True, via_cost=3.0, margins=(6.0, 14.0))
            if result:
                done = f"{name}: joined to {t.name()} at {TEST_WIDTH} mm, {len(result[1])} via(s)"
                break
        report.append(done or f"{name}: not joined ({why})")
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for line in report:
        print(line)
    problems = checks(board)
    for line in problems:
        print(f"CHECK: {line}")
    return problems


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    apply(board)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="add the power-bus copper (one shot)")
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
