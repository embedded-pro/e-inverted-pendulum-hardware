#!/usr/bin/env python3
"""Shorter connections by moving a few parts: a wirelength study and the moves the owner chose (D-059).

    python3 scripts/pcb/improve_placement.py --study                  the ratsnest length, and the parts and groups
                                                                       whose move would shorten it most
    python3 scripts/pcb/improve_placement.py --apply j301 flash ...    move these groups, one translation each

The measure is each net's minimum spanning tree over its pads, in Manhattan distance (mst_manhattan, from the
pcb-design-rules skill's pcb_rules.py, whose gate reports a route's detour against it). GND and the power bus (PWR_4.2A:
its pours, D-056) are left out; so are the crystal nets (at their pins, D-048).
  - --study: the board's total; per part, the best translation within STUDY_REACH mm (STUDY_STEP lattice) and what it
    saves, ignoring collisions; per group, the same for the group as one.
  - --apply: each group moves as one, by the translation on a STEP mm lattice within REACH mm that gives the shortest
    total over the group's nets and that every part passes: place_block.problems (on the board, clear of the bracket
    strip and the battery's through-hole rule, courtyards, other-net copper and silk outlines, no pad under silk, JLCPCB's
    0.5 mm between parts and 2.5 mm to the edge, D-052), clear of another net's pour that carries current or is a vendor
    copy's (maze.soft_fill: a GND fill outside TI's bridges gives way) and of the rule areas that keep copper out, with
    a clean silkscreen spot for every label on the board (silk.py: a test pad keeps its name, D-041). J301 keeps
    J301_CLEAR mm free round its body for the debug cable's plug. A group whose best legal spot saves under MIN_GAIN mm
    stays. Groups move in the order given; each sees the ones before.
The new positions go into placement.py's tables (the test pad rows' origins, the parts' rows), so place_block.py
--replace changes nothing. The silkscreen names are laid out again (silk.py). Run it on a board without passes 1, 3 and 4
(ripup.py): the tracks of the moved parts would be left behind. Re-running is a no-op once no group can gain. Nothing is
locked (D-045).
"""

import argparse
import pathlib
import re
import subprocess
import sys
from collections import defaultdict

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402
import maze as M  # noqa: E402
import place_block as PB  # noqa: E402
import placement  # noqa: E402
import rf_block as RF  # noqa: E402
import route_simple as RS  # noqa: E402
import silk  # noqa: E402

PLACEMENT = pathlib.Path(__file__).resolve().parent / "placement.py"
SKIP_CLASSES = {"PWR_4.2A", "CLK"}
GROUPS = {
    "j301": ("J301",),
    "mcu_tp": ("TP301", "TP304", "TP302"),
    "flash": ("U702", "R702", "R703", "R704", "C704"),
    "imu_tp": ("TP706", "TP704", "TP701", "TP702", "TP703", "TP705"),
    "drive_tp": ("TP511", "TP515", "TP512", "TP514", "TP513", "TP508", "TP507", "TP509", "TP510"),
}
STUDY_REACH = 12.0
STUDY_STEP = 1.0
REACH = 15.0
STEP = 0.25
MIN_GAIN = 1.0
MAX_TRIES = 6000
# The ribbon's IDC plug (STLINK-V3's 14-pin 1.27 mm cable) is wider and longer than the header it plugs onto: no part
# within this of J301's body. ASSUMPTION (docs/layout.md open items): the plug's drawing is not in hand.
J301_CLEAR = 1.5


def mst_manhattan(points):
    """The minimum spanning tree's length over the points, in Manhattan distance (Prim). From the pcb-design-rules
    skill, scripts/pcb_rules.py _mst_manhattan (hardware-skills plugin), unchanged but for the name."""
    pts = list({(round(x, 3), round(y, 3)) for x, y in points})
    if len(pts) < 2:
        return 0.0
    dist, total = {i: abs(pts[i][0] - pts[0][0]) + abs(pts[i][1] - pts[0][1]) for i in range(1, len(pts))}, 0.0
    while dist:
        j = min(dist, key=dist.get)
        total += dist.pop(j)
        for i in dist:
            d = abs(pts[i][0] - pts[j][0]) + abs(pts[i][1] - pts[j][1])
            if d < dist[i]:
                dist[i] = d
    return total


def nets_of(board):
    """{net name: [(ref, x, y) in mm per pad]} for the nets the measure counts (two pads or more)."""
    nets = defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            name = RS.short(pad.GetNetname())
            if pad.GetNetCode() <= 0 or name == "GND" or pad.GetNetClassName() in SKIP_CLASSES:
                continue
            p = pad.GetPosition()
            nets[name].append((fp.GetReference(), p.x / 1e6, p.y / 1e6))
    return {name: pads for name, pads in nets.items() if len(pads) > 1}


def cost(nets, names, refs, dx, dy):
    """The nets' total with the refs' pads moved by (dx, dy) mm (board axes)."""
    return sum(mst_manhattan([(x + dx, y + dy) if ref in refs else (x, y) for ref, x, y in nets[name]]) for name in names)


def best_shift(nets, refs, reach, step):
    names = sorted({name for name, pads in nets.items() if any(ref in refs for ref, _, _ in pads)})
    now = cost(nets, names, refs, 0.0, 0.0)
    count = int(round(reach / step))
    shifts = [(i * step, j * step) for i in range(-count, count + 1) for j in range(-count, count + 1)]
    ranked = sorted(((cost(nets, names, refs, dx, dy), abs(dx) + abs(dy), dx, dy) for dx, dy in shifts))
    return now, ranked


def study(board):
    nets = nets_of(board)
    total = sum(mst_manhattan([(x, y) for _, x, y in pads]) for pads in nets.values())
    print(f"ratsnest (MST, Manhattan) over {len(nets)} nets: {total:.0f} mm")
    rows = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if not any(r == ref for pads in nets.values() for r, _, _ in pads):
            continue
        now, ranked = best_shift(nets, {ref}, STUDY_REACH, STUDY_STEP)
        best, _, dx, dy = ranked[0]
        if now - best >= MIN_GAIN:
            rows.append((now - best, ref, dx, -dy))
    rows.sort(reverse=True)
    print("parts (best translation within 12 mm, collisions ignored):")
    for gain, ref, dx, dz in rows[:25]:
        print(f"  {ref:7} saves {gain:5.1f} mm  by ({dx:+5.1f}, {dz:+5.1f})")
    print("groups:")
    for name, refs in GROUPS.items():
        now, ranked = best_shift(nets, set(refs), STUDY_REACH, STUDY_STEP)
        best, _, dx, dy = ranked[0]
        print(f"  {name:9} {now:6.1f} mm -> {best:6.1f} mm by ({dx:+5.1f}, {-dy:+5.1f})")


def pad_centre(fp):
    pads = pcbnew.BOX2I()
    for pad in fp.Pads():
        pads.Merge(pad.GetBoundingBox())
    return pads.GetCenter()


def keep_outs(board):
    """(layer, polygon, net code or None) that a pad must stay clear of: rule areas that keep copper out, and other
    nets' pours that do not give way (maze.soft_fill)."""
    found = []
    for zone in board.Zones():
        layers = [layer for layer in (pcbnew.F_Cu, pcbnew.B_Cu) if zone.IsOnLayer(layer)]
        outline = pcbnew.SHAPE_POLY_SET(zone.Outline())
        if zone.GetIsRuleArea():
            if zone.GetDoNotAllowTracks() or zone.GetDoNotAllowVias() or zone.GetDoNotAllowZoneFills():
                found += [(layer, outline, None) for layer in layers]
            continue
        for layer in layers:
            hard = pcbnew.SHAPE_POLY_SET(outline)
            if M.soft_fill(zone):
                hard.BooleanIntersection(M.bridges())
            elif zone.GetZoneName() == "MB1355 B.Cu GND" and layer == pcbnew.B_Cu:
                hard.BooleanIntersection(M.rf_band())
            if hard.OutlineCount():
                found.append((layer, hard, zone.GetNetCode()))
    return found


def pour_problems(fp, zones):
    found = []
    for pad in fp.Pads():
        for layer, poly, net in zones:
            if net == pad.GetNetCode() or not pad.IsOnLayer(layer):
                continue
            if poly.Collide(pad.GetEffectiveShape(layer), pcbnew.FromMM(RF.PART_CLEARANCE)):
                found.append(f"pad {pad.GetNumber()} in {'a rule area' if net is None else 'another net' + chr(39) + 's pour'}")
                break
    return found


def clear_round(fp, others, gap):
    """Another part's body or pads within gap mm of this part's body (J301's plug)."""
    own = PB.body(fp)
    found = []
    for other in others:
        if other.GetReference() == fp.GetReference() or not PB.assembled(other):
            continue
        theirs = PB.body(other)
        if theirs.OutlineCount() and own.Collide(theirs, pcbnew.FromMM(gap)):
            found.append(f"{other.GetReference()} within {gap} mm (the debug plug)")
    return found


def courtyards_clear(fps, others):
    for fp in fps:
        fp.BuildCourtyardCaches()
        court = fp.GetCourtyard(pcbnew.F_CrtYd)
        box = court.BBox()
        for other in others:
            if other.IsFlipped() or not box.Intersects(other.GetCourtyard(pcbnew.F_CrtYd).BBox()):
                continue
            if court.Collide(other.GetCourtyard(pcbnew.F_CrtYd), 0):
                return False
    return True


def spot_problems(board, fps, outline, zones):
    refs = {fp.GetReference() for fp in fps}
    others_all = [f for f in board.GetFootprints() if f.GetReference() not in refs]
    if not courtyards_clear(fps, others_all):
        return ["courtyard"]
    found = []
    for fp in fps:
        others = [f for f in board.GetFootprints() if f.GetReference() != fp.GetReference()]
        found += [f"{fp.GetReference()}: {why}" for why in PB.problems(board, fp, outline, others)]
        found += [f"{fp.GetReference()}: {why}" for why in pour_problems(fp, zones)]
        if fp.GetReference() == "J301":
            found += [f"J301: {why}" for why in clear_round(fp, others, J301_CLEAR)]
        if found:
            return found
    _, _, failed = silk.layout(board, check=True)
    return [f"{label.ref}: no clean spot for its name" for label in failed]


def move(fps, dx, dy):
    delta = pcbnew.VECTOR2I(pcbnew.FromMM(dx), pcbnew.FromMM(dy))
    for fp in fps:
        fp.Move(delta)


def place_group(board, name, outline, zones):
    refs = GROUPS[name]
    fps = [board.FindFootprintByReference(ref) for ref in refs]
    nets = nets_of(board)
    now, ranked = best_shift(nets, set(refs), REACH, STEP)
    tried = 0
    for value, _, dx, dy in ranked:
        if now - value < MIN_GAIN:
            break
        if tried >= MAX_TRIES:
            break
        tried += 1
        move(fps, dx, dy)
        if not spot_problems(board, fps, outline, zones):
            print(f"{name}: ({dx:+.2f}, {-dy:+.2f}) mm, {now:.1f} -> {value:.1f} mm over its nets ({tried} spots tried)")
            return dx, -dy
        move(fps, -dx, -dy)
    print(f"{name}: stays (no legal spot saves {MIN_GAIN} mm or more; {tried} spots tried)")
    return None


def table_rows(text):
    """{ref: (start, end) of its x, z numbers in placement.py} for explicit rows, and the tp_row origins by first ref."""
    rows = {m.group(1): m.span(2) for m in re.finditer(r'\("(\w+)", (-?[\d.]+, -?[\d.]+), -?[\d.]+\)', text)}
    rows_tp = {}
    for m in re.finditer(r'tp_row\(\(([^)]*)\), (-?[\d.]+, -?[\d.]+)', text):
        members = re.findall(r'"(\w+)"', m.group(1))
        rows_tp[members[0]] = (m.span(2), members)
    return rows, rows_tp


def number(value):
    value = round(value, 4)
    return repr(value + 0.0)


def update_tables(moves):
    """Shift each moved part's table entry by its group's translation (mechanical x, z)."""
    text = PLACEMENT.read_text()
    edits = []
    for name, (dx, dz) in moves.items():
        rows, rows_tp = table_rows(text)
        refs = set(GROUPS[name])
        done = set()
        for first, (span, members) in rows_tp.items():
            if set(members) & refs:
                if not set(members) <= refs:
                    sys.exit(f"{name}: the test pad row starting {first} holds parts outside the group")
                edits.append((span, dx, dz))
                done |= set(members)
        for ref in sorted(refs - done):
            if ref not in rows:
                sys.exit(f"{name}: {ref} is in no placement table")
            edits.append((rows[ref], dx, dz))
    for (start, end), dx, dz in sorted(edits, reverse=True):
        x, z = (float(v) for v in text[start:end].split(", "))
        text = text[:start] + f"{number(x + dx)}, {number(z + dz)}" + text[end:]
    PLACEMENT.write_text(text)


def table_agrees(board, refs):
    rows = {ref: (x, z) for ref, x, z, _ in placement.rest() + placement.imu_memory()}
    for ref in refs:
        centre = RF.board_to_mech(pad_centre(board.FindFootprintByReference(ref)))
        if ref not in rows or abs(centre[0] - rows[ref][0]) > 0.001 or abs(centre[1] - rows[ref][1]) > 0.001:
            return ref
    return None


def stage(groups):
    board = pcbnew.LoadBoard(str(B.BOARD))
    if groups is None:
        study(board)
        return
    for name in groups:
        stray = table_agrees(board, GROUPS[name])
        if stray:
            sys.exit(f"{stray} is not where placement.py has it: sync the tables first (place_block.py --replace)")
    outline = PB.outline_of(board)
    zones = keep_outs(board)
    moves = {}
    for name in groups:
        shift = place_group(board, name, outline, zones)
        if shift:
            moves[name] = shift
    if not moves:
        print("no group gains: nothing to do")
        sys.exit(3)
    silk.report(*silk.layout(board, check=False), check=False)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(B.BOARD), board)
    update_tables(moves)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--study", action="store_true", help="the ratsnest length and the moves that would shorten it")
    parser.add_argument("--apply", nargs="+", choices=sorted(GROUPS), help="move these groups (in this order)")
    parser.add_argument("--pcbnew-stage", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage is not None:
        stage(args.pcbnew_stage or None)
        return
    if not args.study and not args.apply:
        parser.error("nothing to do without --study or --apply <groups>")
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage"] + (args.apply or []))
    B.PROJECT.write_bytes(project)
    if result.returncode == 3 or args.study:
        sys.exit(0 if result.returncode in (0, 3) else result.returncode)
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
