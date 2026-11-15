#!/usr/bin/env python3
"""Fan the MCU's signal pins out to vias, then position its decoupling caps (owner, D-048).

    python3 scripts/pcb/mcu_escape.py --fanout       a track and a via from every U301 pin another part uses
    python3 scripts/pcb/mcu_escape.py --decoupling   the MCU decoupling caps at ST's spots or the nearest free spot

Fan-out (owner: the smallest via JLCPCB makes, 0.15 / 0.25 mm on 4 layers, pcb-design-rules jlcpcb profile):
  - every U301 pad whose net reaches another part, except power, ground and the MB1355 copy's own nets (crystals, RF,
    SMPS), gets a straight F.Cu stub (STUB_WIDTH, the Default class) out along the pad's axis to a through via;
  - the vias sit in two rows, ROW_A and ROW_B past the pad tip; neighbouring signal pins alternate rows, so vias at the
    0.4 mm pin pitch are staggered;
  - every stub and via clears other-net copper by CLEARANCE on every layer, every hole by HOLE_TO_COPPER and
    HOLE_TO_HOLE (JLCPCB), each with MARGIN to spare, the courtyards of other parts, the spots kept for ST's VDDSMPS
    caps (RESERVED, ST's lands, AN5165: ESL < 2 nH) and the antenna tab; a via also keeps QUIET_GAP from the crystals
    and the RF and clock nets (rf-layout s5 / s6: no GPIO at the RF lines or the crystals), except on STATIC_NETS, which
    hold a level and don't switch while the radio and the oscillators run;
  - a blocked spot moves to the other row, then further out along the axis, then to a 45-degree bend at BENDS_AT, up to
    MAX_OUT past the tip; a spot is taken only if the next pin along the side still has one (one-pin lookahead); a pin
    with no spot is listed and left alone;
  - a pad that already has a track is left alone, so a second run changes nothing.
Decoupling (DS11929 s6.1.6 Fig. 16, D-038; owner: on top, beside the pins): the parked caps go to ST's top-side lands
(C309 / C318), the Nucleo's top-side spots (C303 / C304 / C305 / C306) or, where those are taken, the nearest spot
to their pin that clears every courtyard, other-net copper, every via and every silk outline (rf_block.spot_ok).
Positions only: the owner routes them. Nothing is locked (D-045); silk.py lays the labels out last.
"""

import argparse
import math
import pathlib
import subprocess
import sys

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402
import silk  # noqa: E402

mm = pcbnew.FromMM
MCU = "U301"
VIA_DRILL, VIA_DIAMETER = 0.15, 0.25
STUB_WIDTH = 0.2
ROW_A, ROW_B = 0.30, 0.75
MAX_OUT = 2.0
STEP = 0.05
BENDS_AT = (0.10, 0.30, 0.50)
CLEARANCE = 0.15
MARGIN = 0.005
HOLE_TO_COPPER = 0.20
HOLE_TO_HOLE = 0.20
QUIET_GAP = 0.5
SKIP_NETS = {"+3V3", "VDDA", "GND", "OSC32_IN", "OSC32_OUT", "HSE_IN", "HSE_OUT", "RF1", "VFBSMPS", "SMPS_LX"}
QUIET_NETS = {"OSC32_IN", "OSC32_OUT", "HSE_IN", "HSE_OUT", "RF1", "RF_50", "RF_ANT"}
QUIET_PARTS = {"Y301", "Y302"}
STATIC_NETS = {"BOOT0", "DRV_NSLEEP", "DRV_RESET", "NRST"}
RESERVED = ("C309", "C318")
CAPS = [
    ("C309", "land", "44"),
    ("C318", "land", "44"),
    ("C307", None, "33"),
    ("C302", None, "45"),
    ("C303", "C18", "68"),
    ("C304", "C28", "1"),
    ("C305", "C31", "55"),
    ("C317", None, "8"),
    ("C306", "C17", "68"),
]
VIA_SIZE = {"diameter": VIA_DIAMETER, "drill": VIA_DRILL}


def short(net):
    return net.rsplit("/", 1)[-1]


def outline_of(board):
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    return outline


def signal_pads(board, mcu):
    users = {}
    for fp in board.GetFootprints():
        if fp.GetReference() == MCU:
            continue
        for pad in fp.Pads():
            users.setdefault(pad.GetNetname(), set()).add(fp.GetReference())
    tracked = {t.GetNetname() for t in board.GetTracks()}
    pads = []
    for pad in mcu.Pads():
        net = pad.GetNetname()
        if not net or net.startswith("unconnected") or short(net) in SKIP_NETS or not users.get(net):
            continue
        touched = any(t.GetClass() != "PCB_VIA" and (pad.HitTest(t.GetStart()) or pad.HitTest(t.GetEnd()))
                      for t in board.GetTracks() if t.GetNetname() == net) if net in tracked else False
        if not touched:
            pads.append(pad)
    return sorted(pads, key=lambda p: int(p.GetNumber()))


def axis(mcu, pad):
    """Unit vector out of the package along the pad, and the pad's tip on that axis."""
    box = pad.GetBoundingBox()
    rel = pad.GetPosition() - mcu.GetPosition()
    if box.GetWidth() > box.GetHeight():
        out = (1 if rel.x > 0 else -1, 0)
        tip = pcbnew.VECTOR2I(box.GetRight() if out[0] > 0 else box.GetLeft(), pad.GetPosition().y)
    else:
        out = (0, 1 if rel.y > 0 else -1)
        tip = pcbnew.VECTOR2I(pad.GetPosition().x, box.GetBottom() if out[1] > 0 else box.GetTop())
    return out, tip


def point(origin, direction, distance):
    return pcbnew.VECTOR2I(int(origin.x + direction[0] * mm(distance)), int(origin.y + direction[1] * mm(distance)))


def candidates(pad, out, tip, preferred):
    """(via, [stub points]) in the order they are tried: straight out on the preferred row, on the other row, further
    out; then a 45-degree bend at BENDS_AT past the tip, either side, shortest first."""
    distances = [ROW_A + k * STEP for k in range(int(round((MAX_OUT - ROW_A) / STEP)) + 1)]
    other = ROW_B if preferred == ROW_A else ROW_A
    distances.sort(key=lambda d: (abs(d - preferred) > 1e-6, abs(d - other) > 1e-6, d))
    found = [(point(tip, out, d), [pad.GetPosition(), point(tip, out, d)]) for d in distances]
    bends = []
    for bend_at in BENDS_AT:
        bend = point(tip, out, bend_at)
        for side in (1, -1):
            diagonal = ((out[0] - side * out[1]) / math.sqrt(2), (out[1] + side * out[0]) / math.sqrt(2))
            for k in range(1, int(round((MAX_OUT - bend_at) / STEP)) + 1):
                bends.append((bend_at + k * STEP, (point(bend, diagonal, k * STEP), [pad.GetPosition(), bend,
                                                                                    point(bend, diagonal, k * STEP)])))
    return found + [c for _, c in sorted(bends, key=lambda b: b[0])]


def reach(item):
    if item.GetClass() == "PAD":
        return item.GetBoundingRadius()
    if item.GetClass() == "PCB_VIA":
        return item.GetWidth(pcbnew.F_Cu)
    return item.GetLength() + item.GetWidth()


class Obstacles:
    """Copper and holes near the MCU, other parts' courtyards, the kept spots and the antenna tab; stubs and vias are
    added and taken away as the search goes."""

    def __init__(self, board, mcu, reserved):
        centre = mcu.GetPosition()
        self.items = []
        for fp in board.GetFootprints():
            if (fp.GetPosition() - centre).EuclideanNorm() < mm(16):
                self.items += list(fp.Pads())
        for track in board.GetTracks():
            if (track.GetPosition() - centre).EuclideanNorm() < mm(10) + reach(track):
                self.items.append(track)
        self.courts = []
        for fp in board.GetFootprints():
            if fp.GetReference() != MCU and not fp.IsFlipped() and (fp.GetPosition() - centre).EuclideanNorm() < mm(16):
                fp.BuildCourtyardCaches()
                court = fp.GetCourtyard(pcbnew.F_CrtYd)
                if court.OutlineCount():
                    self.courts.append(pcbnew.SHAPE_POLY_SET(court))
        self.reserved = reserved
        tab = next(a for a in placement.RULE_AREAS if a["name"] == "ANTENNA_TAB")
        self.tab = pcbnew.SHAPE_POLY_SET()
        self.tab.NewOutline()
        for x, z in tab["polygon"]:
            self.tab.Append(B.to_board(x, z))

    def add(self, items):
        self.items += items

    def remove(self, items):
        self.items = [i for i in self.items if not any(i is j for j in items)]

    def near(self, centre):
        return [i for i in self.items if (i.GetPosition() - centre).EuclideanNorm() < mm(3.5) + reach(i)]

    def fits(self, pad, via, stub, local):
        netcode, net = pad.GetNetCode(), short(pad.GetNetname())
        ring = pcbnew.SHAPE_CIRCLE(via, mm(VIA_DIAMETER) // 2)
        hole = pcbnew.SHAPE_CIRCLE(via, mm(VIA_DRILL) // 2)
        segments = [pcbnew.SHAPE_SEGMENT(a, b, mm(STUB_WIDTH)) for a, b in zip(stub, stub[1:])]
        layers = (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)
        for item in local:
            drilled = item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole())
            if drilled and item.GetEffectiveHoleShape().Collide(hole, mm(HOLE_TO_HOLE + MARGIN)):
                return False
            if item.GetNetCode() == netcode:
                continue
            if drilled and any(item.GetEffectiveHoleShape().Collide(s, mm(HOLE_TO_COPPER + MARGIN)) for s in segments):
                return False
            quiet = net not in STATIC_NETS and (short(item.GetNetname()) in QUIET_NETS or (
                item.GetClass() == "PAD" and item.GetParentFootprint().GetReference() in QUIET_PARTS))
            for layer in layers:
                if not item.IsOnLayer(layer):
                    continue
                shape = item.GetEffectiveShape(layer)
                if shape.Collide(ring, mm((QUIET_GAP if quiet else CLEARANCE) + MARGIN)) or shape.Collide(hole, mm(HOLE_TO_COPPER + MARGIN)):
                    return False
                if layer == pcbnew.F_Cu and any(shape.Collide(s, mm(CLEARANCE + MARGIN)) for s in segments):
                    return False
        for court in self.courts:
            if court.Collide(ring, 0):
                return False
        for court in self.reserved:
            if court.Collide(ring, mm(CLEARANCE)) or any(court.Collide(s, mm(CLEARANCE)) for s in segments):
                return False
        return not self.tab.Collide(ring, 0)


def build(board, pad, via_at, stub):
    items = []
    for a, b in zip(stub, stub[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(a)
        track.SetEnd(b)
        track.SetWidth(mm(STUB_WIDTH))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(pad.GetNet())
        items.append(track)
    via = pcbnew.PCB_VIA(board)
    via.SetViaType(pcbnew.VIATYPE_THROUGH)
    via.SetPosition(via_at)
    via.SetWidth(mm(VIA_DIAMETER))
    via.SetDrill(mm(VIA_DRILL))
    via.SetNet(pad.GetNet())
    items.append(via)
    return items


def land(board, fp):
    part = next(p for p in RF.DATA["parts"] if p["ours"] == fp.GetReference())
    fp.SetPosition(RF.to_ours(*part["at"]))
    RF.orient(fp, part, RF.net_lookup(board))


def reserved_courts(board):
    """The courtyards of ST's VDDSMPS caps on ST's lands, if those are free; the caps go back where they were."""
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    courts = []
    for ref in RESERVED:
        fp = footprints[ref]
        position, rotation = fp.GetPosition(), fp.GetOrientationDegrees()
        land(board, fp)
        fp.BuildCourtyardCaches()
        others = [f for f in board.GetFootprints() if f.GetReference() != ref]
        if RF.spot_ok(board, fp, others):
            courts.append(pcbnew.SHAPE_POLY_SET(fp.GetCourtyard(pcbnew.F_CrtYd)))
        else:
            print(f"{ref}: ST's land is taken; not kept")
        fp.SetOrientationDegrees(rotation)
        fp.SetPosition(position)
    return courts


def sides(mcu, pads):
    """The signal pads per package side, in order along it, with their axis."""
    grouped = {}
    for pad in pads:
        out, tip = axis(mcu, pad)
        grouped.setdefault(out, []).append((pad, tip))
    return [(out, sorted(group, key=lambda g: int(g[0].GetNumber()))) for out, group in grouped.items()]


def fanout(board):
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    mcu = footprints[MCU]
    pads = signal_pads(board, mcu)
    if not pads:
        print("every MCU signal pad already has a track: nothing to do")
        sys.exit(3)
    obstacles = Obstacles(board, mcu, reserved_courts(board))
    placed, missed = [], []
    for out, group in sides(mcu, pads):
        previous = None
        for index, (pad, tip) in enumerate(group):
            neighbour = group[index + 1] if index + 1 < len(group) else None
            if neighbour and int(neighbour[0].GetNumber()) - int(pad.GetNumber()) != 1:
                neighbour = None
            row = ROW_B if previous == ROW_A else ROW_A
            local = obstacles.near(tip)
            chosen, fallback = None, None
            for via_at, stub in candidates(pad, out, tip, row):
                if not obstacles.fits(pad, via_at, stub, local):
                    continue
                items = build(board, pad, via_at, stub)
                if neighbour is None:
                    chosen = (via_at, stub, items)
                    break
                obstacles.add(items)
                next_pad, next_tip = neighbour
                next_local = obstacles.near(next_tip)
                ok = any(obstacles.fits(next_pad, v, s, next_local)
                         for v, s in candidates(next_pad, out, next_tip, ROW_B if abs(
                             (via_at - tip).EuclideanNorm() - mm(ROW_A)) < mm(0.01) else ROW_A))
                obstacles.remove(items)
                if ok:
                    chosen = (via_at, stub, items)
                    break
                if fallback is None:
                    fallback = (via_at, stub, items)
            chosen = chosen or fallback
            if chosen is None:
                missed.append(pad)
                previous = None
                continue
            via_at, stub, items = chosen
            obstacles.add(items)
            for item in items:
                board.Add(item)
            previous = ROW_A if len(stub) == 2 and abs((via_at - tip).EuclideanNorm() - mm(ROW_A)) < mm(0.01) else ROW_B
            length = sum((b - a).EuclideanNorm() for a, b in zip(stub, stub[1:])) - (pad.GetPosition() - tip).EuclideanNorm()
            placed.append((pad, via_at, len(stub) > 2, pcbnew.ToMM(length)))
    silk.report(*silk.layout(board, check=False), check=False)
    for pad, via_at, bent, length in sorted(placed, key=lambda p: int(p[0].GetNumber())):
        print(f"pin {pad.GetNumber():>2} {short(pad.GetNetname()):12s} via at {RF.board_to_mech(via_at)}, "
              f"{length:.2f} mm past the pad{' (45-degree bend)' if bent else ''}")
    print(f"{len(placed)} pins fanned out with {VIA_DRILL} / {VIA_DIAMETER} mm vias")
    for pad in missed:
        print(f"pin {pad.GetNumber()} {short(pad.GetNetname())}: no free spot within {MAX_OUT} mm; left alone")
    return not missed


def free_of_vias(board, fp):
    """No pad of the part on or within HOLE_TO_COPPER of any via, whatever its net (no via in a pad)."""
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"
            and (t.GetPosition() - fp.GetPosition()).EuclideanNorm() < mm(4)]
    for pad in fp.Pads():
        shape = pad.GetEffectiveShape(pcbnew.F_Cu)
        if any(shape.Collide(v.GetEffectiveShape(pcbnew.F_Cu), mm(HOLE_TO_COPPER)) for v in vias):
            return False
    return True


def place_cap(board, fp, centre, first):
    others = [f for f in board.GetFootprints() if f.GetReference() != fp.GetReference()]
    if first is not None:
        first()
        fp.BuildCourtyardCaches()
        if RF.spot_ok(board, fp, others) and free_of_vias(board, fp):
            return "ST's spot"
    for ring in range(1, 200):
        r = mm(0.05) * ring
        steps = max(8, int(2 * math.pi * ring / 2))
        for k in range(steps):
            angle = 2 * math.pi * k / steps
            for rot in (90.0, 270.0, 0.0, 180.0):
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(centre + pcbnew.VECTOR2I(int(r * math.cos(angle)), int(r * math.sin(angle))))
                fp.BuildCourtyardCaches()
                if RF.spot_ok(board, fp, others) and free_of_vias(board, fp):
                    return "nearest free spot"
    sys.exit(f"no free spot for {fp.GetReference()}")


def decoupling(board):
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    outline = outline_of(board)
    todo = [c for c in CAPS if not outline.Contains(footprints[c[0]].GetPosition())]
    if not todo:
        print("the MCU decoupling caps are on the board: nothing to do")
        sys.exit(3)
    mcu = footprints[MCU]
    pins = {p.GetNumber(): p for p in mcu.Pads()}
    report = []
    for ref, spot, pin in todo:
        fp = footprints[ref]
        fp.SetLocked(False)
        target = pins[pin].GetPosition()
        if spot == "land":
            how = place_cap(board, fp, target, lambda fp=fp: land(board, fp))
        elif spot:
            st = RF.DATA["decoupling"][spot]
            nucleo = RF.to_ours(*st["at"])

            def first(fp=fp, nucleo=nucleo, rot=st["rot"]):
                fp.SetOrientationDegrees(rot)
                fp.SetPosition(nucleo)
            how = place_cap(board, fp, nucleo, first)
            how = "Nucleo spot" if how == "ST's spot" else how
        else:
            how = place_cap(board, fp, target, None)
        B.label_fields(fp)
        distance = pcbnew.ToMM((fp.GetPosition() - target).EuclideanNorm())
        report.append((ref, pin, short(pins[pin].GetNetname()), how, distance))
    silk.report(*silk.layout(board, check=False), check=False)
    for ref, pin, net, how, distance in report:
        fp = footprints[ref]
        print(f"{ref} ({net} pin {pin}) at mechanical {RF.board_to_mech(fp.GetPosition())}, rotation "
              f"{fp.GetOrientationDegrees():.0f}: {how}, {distance:.2f} mm from the pin")
    return True


def stage(step):
    board = pcbnew.LoadBoard(str(B.BOARD))
    done = fanout(board) if step == "fanout" else decoupling(board)
    pcbnew.SaveBoard(str(B.BOARD), board)
    if not done:
        sys.exit(4)


def add_via_size(project_bytes):
    import json
    project = json.loads(project_bytes)
    sizes = project.setdefault("board", {}).setdefault("design_settings", {}).setdefault("via_dimensions", [])
    if VIA_SIZE not in sizes:
        sizes.append(dict(VIA_SIZE))
    return (json.dumps(project, indent=2) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fanout", action="store_true", help="stubs and vias from the MCU's signal pins (one shot)")
    parser.add_argument("--decoupling", action="store_true", help="position the parked MCU decoupling caps (one shot)")
    parser.add_argument("--pcbnew-stage", choices=["fanout", "decoupling"], help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage(args.pcbnew_stage)
        return
    if args.fanout == args.decoupling:
        parser.error("choose one: --fanout or --decoupling")
    step = "fanout" if args.fanout else "decoupling"
    project = B.PROJECT.read_bytes()
    if step == "fanout":
        project = add_via_size(project)
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage", step])
    B.PROJECT.write_bytes(project)
    if result.returncode == 3:
        return
    if result.returncode not in (0, 4):
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)
    if result.returncode == 4:
        sys.exit(4)


if __name__ == "__main__":
    main()
