#!/usr/bin/env python3
"""GND vias on a regular lattice: U301's exposed pad and a stitching grid over ST's RF ground strip (owner, D-049).

    python3 scripts/pcb/gnd_vias.py --apply

Both use the board's smallest via, 0.15 / 0.25 mm (the fan-out's, D-048; owner):
  - exposed pad: a via on every PAD_PITCH point of the gaps between ST's 4 x 4 paste windows (MB1355 copy, D-037):
    straight rows and columns, none under a paste window, so the solder stays on the pad (rf-layout s5: an exposed
    pad takes as many vias as the rules allow);
  - RF strip: a via on every STITCH_PITCH point of the board grid (multiples from the axle origin) inside ST's strip
    ground (mb1355_rf.json, F.Cu GND) where it fits (rf-layout s2: 1 to 1.3 mm along RF lines and edges). A point that
    doesn't fit is skipped, not moved, so the grid stays regular. These vias join the strip ground the owner pours.
A via fits when it clears other-net copper by the larger of the Default clearance and the net's class clearance, holes
by HOLE_TO_COPPER, every hole by HOLE_TO_HOLE (JLCPCB), each with mcu_escape.MARGIN to spare, stays outside every part's
courtyard, the antenna tab and the rule areas that forbid vias, and inside the board by the copper-to-edge clearance.
Re-running is a no-op once the pad and the strip have their vias. Nothing is locked (D-045).
"""

import argparse
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import mcu_escape as E  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402
import silk  # noqa: E402

mm = pcbnew.FromMM
VIA_DRILL, VIA_DIAMETER = E.VIA_DRILL, E.VIA_DIAMETER
PAD_PITCH = 0.8
STITCH_PITCH = 1.2
EDGE_CLEARANCE = 0.2
CLASS_CLEARANCE = {name: spec["clearance"] for name, spec in B.NET_CLASSES.items()}


def exact(x, z):
    return pcbnew.VECTOR2I(int(round((B.ORIGIN[0] + x) * 1e6)), int(round((B.ORIGIN[1] - z) * 1e6)))


def mech(v):
    return ((v.x / 1e6) - B.ORIGIN[0], B.ORIGIN[1] - v.y / 1e6)


def strip_rectangle():
    zone = next(z for z in RF.DATA["zones"] if z["layer"] == "F.Cu" and RF.DATA["net_map"].get(z["net"]) == "GND")
    points = [placement.from_mb1355(x, y) for x, y in zone["polygons"][0]]
    xs, zs = [p[0] for p in points], [p[1] for p in points]
    return min(xs), max(xs), min(zs), max(zs)


class Checker:
    def __init__(self, board):
        self.items = []
        for fp in board.GetFootprints():
            self.items += list(fp.Pads())
        self.items += list(board.GetTracks())
        self.courts = []
        for fp in board.GetFootprints():
            fp.BuildCourtyardCaches()
            for layer in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
                court = fp.GetCourtyard(layer)
                if court.OutlineCount():
                    self.courts.append(pcbnew.SHAPE_POLY_SET(court))
        self.keepouts = [pcbnew.SHAPE_POLY_SET(z.Outline()) for z in board.Zones()
                         if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
        tab = next(a for a in placement.RULE_AREAS if a["name"] == "ANTENNA_TAB")
        poly = pcbnew.SHAPE_POLY_SET()
        poly.NewOutline()
        for x, z in tab["polygon"]:
            poly.Append(B.to_board(x, z))
        self.keepouts.append(poly)
        self.inside = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(self.inside, False)
        self.inside.Deflate(mm(EDGE_CLEARANCE + VIA_DIAMETER / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.005))

    def fits(self, netcode, at, courts=True):
        ring = pcbnew.SHAPE_CIRCLE(at, mm(VIA_DIAMETER) // 2)
        hole = pcbnew.SHAPE_CIRCLE(at, mm(VIA_DRILL) // 2)
        if not self.inside.Contains(at):
            return False
        layers = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
        for item in self.items:
            if (item.GetPosition() - at).EuclideanNorm() > mm(3) + E.reach(item):
                continue
            drilled = item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole())
            if drilled and item.GetEffectiveHoleShape().Collide(hole, mm(E.HOLE_TO_HOLE + E.MARGIN)):
                return False
            if item.GetNetCode() == netcode:
                continue
            clearance = max(E.CLEARANCE, CLASS_CLEARANCE.get(item.GetNetClassName(), E.CLEARANCE))
            for layer in layers:
                if not item.IsOnLayer(layer):
                    continue
                shape = item.GetEffectiveShape(layer)
                if shape.Collide(ring, mm(clearance + E.MARGIN)) or shape.Collide(hole, mm(E.HOLE_TO_COPPER + E.MARGIN)):
                    return False
        if courts and any(court.Collide(ring, 0) for court in self.courts):
            return False
        return not any(area.Collide(ring, 0) for area in self.keepouts)

    def add(self, via):
        self.items.append(via)


def make_via(board, at, net):
    via = pcbnew.PCB_VIA(board)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetPosition(at)
    via.SetWidth(mm(VIA_DIAMETER))
    via.SetDrill(mm(VIA_DRILL))
    via.SetNet(net)
    board.Add(via)
    return via


def pad_points(mcu):
    """The PAD_PITCH points on the gaps between the exposed pad's paste windows."""
    windows = [p for p in mcu.Pads() if not p.GetNumber() and p.IsOnLayer(pcbnew.F_Paste)]
    xs = sorted({w.GetPosition().x for w in windows})
    ys = sorted({w.GetPosition().y for w in windows})
    gaps_x = [(a + b) // 2 for a, b in zip(xs, xs[1:])]
    gaps_y = [(a + b) // 2 for a, b in zip(ys, ys[1:])]
    def along(values):
        count = round((values[-1] - values[0]) / mm(PAD_PITCH)) + 1
        return [values[0] + round(k * (values[-1] - values[0]) / (count - 1)) for k in range(count)]

    along_y, along_x = along(ys), along(xs)
    points = {(x, y) for x in gaps_x for y in along_y} | {(x, y) for y in gaps_y for x in along_x}
    return [pcbnew.VECTOR2I(x, y) for x, y in sorted(points)], windows


def stitch_points():
    x0, x1, z0, z1 = strip_rectangle()
    first_x, first_z = int(-(-x0 // STITCH_PITCH)), int(-(-z0 // STITCH_PITCH))
    points = []
    k = first_x
    while k * STITCH_PITCH <= x1:
        j = first_z
        while j * STITCH_PITCH <= z1:
            points.append((round(k * STITCH_PITCH, 6), round(j * STITCH_PITCH, 6)))
            j += 1
        k += 1
    return [exact(x, z) for x, z in points], (x0, x1, z0, z1)


def apply(board):
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    mcu = footprints[E.MCU]
    exposed = next(p for p in mcu.Pads() if p.GetNumber() and p.GetSize().x > mm(3))
    gnd = exposed.GetNet()
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    pad_done = any(exposed.HitTest(v.GetPosition()) for v in vias)
    points, rectangle = stitch_points()
    on_grid = {(p.x, p.y) for p in points}
    stitch_done = any((v.GetPosition().x, v.GetPosition().y) in on_grid and v.GetNetCode() == gnd.GetNetCode()
                      for v in vias)
    if pad_done and stitch_done:
        print("the exposed pad and the RF strip already have their GND vias: nothing to do")
        sys.exit(3)
    checker = Checker(board)
    report = []
    if not pad_done:
        lattice, windows = pad_points(mcu)
        for at in lattice:
            ring = pcbnew.SHAPE_CIRCLE(at, mm(VIA_DIAMETER) // 2)
            if any(w.GetEffectiveShape(pcbnew.F_Paste).Collide(ring, 0) for w in windows):
                sys.exit(f"pad via at {mech(at)} would sit under a paste window")
            if not exposed.HitTest(at) or not checker.fits(gnd.GetNetCode(), at, courts=False):
                sys.exit(f"pad via at {mech(at)} doesn't fit")
            checker.add(make_via(board, at, gnd))
        report.append(f"exposed pad: {len(lattice)} vias on a {PAD_PITCH} mm lattice in the paste gaps")
    if not stitch_done:
        placed = [at for at in points if checker.fits(gnd.GetNetCode(), at)]
        for at in placed:
            checker.add(make_via(board, at, gnd))
        x0, x1, z0, z1 = rectangle
        report.append(f"RF strip (x {x0:.2f}..{x1:.2f}, z {z0:.2f}..{z1:.2f}): {len(placed)} of {len(points)} grid points "
                      f"at {STITCH_PITCH} mm get a via; {len(points) - len(placed)} are taken by parts, copper or keep-outs")
    silk.report(*silk.layout(board, check=False), check=False)
    for line in report:
        print(line)


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    apply(board)
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="add the GND vias (one shot)")
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
