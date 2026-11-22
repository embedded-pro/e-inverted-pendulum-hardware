#!/usr/bin/env python3
"""ANT14, the printed NFC coil copied from ST's X-NUCLEO-NFC01A1 (MB1163 rev C-01, D-039): inductance and resonance.

The coil comes from scripts/pcb/mb1163_nfc.json (scripts/nfc_reference.py): about 4 turns on F.Cu spiralling in, a
layer change, and 3.5 turns on B.Cu spiralling out, wound the same way, so the two spirals' fields add.

Inductance (Greenhouse, IEEE Trans. Parts, Hybrids and Packaging PHP-10(2), 1974): the coil is walked from pad 1 (AC0)
to pad 2 (AC1), which gives every segment its current direction. L = sum of segment self-inductances (rectangular bar,
0.002 l [ln(2l/(w+t)) + 0.50049 + (w+t)/(3l)] uH, l in cm) plus the mutual inductance of every pair of parallel
segments, B.Cu ones at the copper-to-copper distance, from the Neumann integral for parallel filaments. The short
diagonal leads only count for their self-inductance.

Method check: the Greenhouse code on a regular 4-turn spiral of ANT14's outline, track and gap, against the modified
Wheeler formula (Mohan et al., IEEE JSSC 34(10), 1999, K1 2.34, K2 2.75, square of equal area): they must agree within
5 %. (Wheeler needs a regular spiral; ANT14's own spirals have partial turns and diagonal leads.)

Resonance: the tag's internal C_TUN (M24SR64-Y, DocID023790 Rev 20: 25 pF typ, 22.5-27.5 pF in SO8) plus ST's C6 and
C8 (47 pF from AC1 and AC0 to GND, so 23.5 pF across the coil) plus 1 pF of pads and traces (ASSUMPTION).
f0 = 1 / (2 pi sqrt(L C)). Computed on ST's board (2-layer 1.6 mm) and on ours (JLC04161H-7628, scripts/pcb/board.py).

Run: python3 scripts/nfc_coil.py -> simulation/results/nfc_coil.json
"""

import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "pcb"))
from board import STACKUP  # noqa: E402

MU0 = 4e-7 * math.pi
C_TUN = (22.5e-12, 25.0e-12, 27.5e-12)
C_EXT = 47e-12 / 2
C_PAR = 1.0e-12
F_CARRIER = 13.56e6
COPPER_T = 0.035
TOL = 0.05


def copper_distance():
    """F.Cu to B.Cu, copper centre to copper centre, from our stack-up."""
    names = [row[0] for row in STACKUP]
    first, last = names.index("F.Cu"), names.index("B.Cu")
    rows = STACKUP[first:last + 1]
    return sum(row[2] for row in rows) - rows[0][2] / 2 - rows[-1][2] / 2


BOARDS = {
    "MB1163 (2-layer 1.6 mm FR-4)": 1.6 - COPPER_T,
    "ours (JLC04161H-7628, 4-layer 1.6 mm)": copper_distance(),
}


def walk(data):
    """The coil's segments in current order, AC0 to AC1, each as (start, end, layer, width)."""
    segments = [{"layer": s[0], "width": s[1], "a": (s[2], s[3]), "b": (s[4], s[5])} for s in data["coil"]["segments"]]
    changes = [tuple(c["at"]) for c in data["coil"]["layer_changes"]]
    pads = {p[0]: (p[1], p[2]) for p in data["antenna"]["pads"]}
    point, layer, used, path, switched = pads["1"], "F.Cu", set(), [], set()
    while math.dist(point, pads["2"]) > TOL or layer != "F.Cu":
        nxt = [(i, s) for i, s in enumerate(segments) if i not in used and s["layer"] == layer
               and min(math.dist(point, s["a"]), math.dist(point, s["b"])) < TOL]
        if not nxt:
            change = next((c for c in changes if math.dist(point, c) < TOL and c not in switched), None)
            if change is None:
                sys.exit(f"the coil breaks at {point} on {layer}")
            switched.add(change)
            layer = "B.Cu" if layer == "F.Cu" else "F.Cu"
            continue
        i, s = min(nxt, key=lambda item: min(math.dist(point, item[1]["a"]), math.dist(point, item[1]["b"])))
        used.add(i)
        start, end = (s["a"], s["b"]) if math.dist(point, s["a"]) <= math.dist(point, s["b"]) else (s["b"], s["a"])
        path.append((start, end, layer, s["width"]))
        point = end
    spare = [s for i, s in enumerate(segments) if i not in used]
    return path, spare


def self_inductance(length_mm, width_mm):
    l_cm, wt_cm = length_mm / 10.0, (width_mm + COPPER_T) / 10.0
    return 0.002 * l_cm * (math.log(2 * l_cm / wt_cm) + 0.50049 + wt_cm / (3 * l_cm)) * 1e-6


def _g(u, d):
    return u * math.asinh(u / d) - math.hypot(u, d)


def mutual(seg_a, seg_b):
    (a0, a1, za), (b0, b1, zb) = seg_a, seg_b
    if abs(a0[1] - a1[1]) < 1e-9 and abs(b0[1] - b1[1]) < 1e-9:
        axis, fixed = 0, 1
    elif abs(a0[0] - a1[0]) < 1e-9 and abs(b0[0] - b1[0]) < 1e-9:
        axis, fixed = 1, 0
    else:
        return 0.0
    d = math.hypot(a0[fixed] - b0[fixed], za - zb) * 1e-3
    if d == 0.0:
        return 0.0
    da, db = math.copysign(1, a1[axis] - a0[axis]), math.copysign(1, b1[axis] - b0[axis])
    p1, p2 = sorted((a0[axis] * 1e-3, a1[axis] * 1e-3))
    q1, q2 = sorted((b0[axis] * 1e-3, b1[axis] * 1e-3))
    m = MU0 / (4 * math.pi) * (_g(p2 - q1, d) - _g(p1 - q1, d) - _g(p2 - q2, d) + _g(p1 - q2, d))
    return da * db * m


def greenhouse(path, dz):
    segs = [(a, b, dz if layer == "B.Cu" else 0.0) for a, b, layer, _ in path]
    total = sum(self_inductance(math.dist(a, b), w) for a, b, _, w in path)
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            total += 2.0 * mutual(segs[i], segs[j])
    return total


def ideal_spiral(turns, width, height, trace, gap):
    """A regular rectangular spiral (copper outline width x height), as a current-ordered single-layer path."""
    pitch, w, h = trace + gap, width - trace, height - trace
    points = [(0.0, 0.0)]
    for i in range(turns):
        left, right, top, bottom = i * pitch, w - i * pitch, i * pitch, h - i * pitch
        end = (i + 1) * pitch if i + 1 < turns else h / 2
        points += [(right, top), (right, bottom), (left, bottom), (left, end)]
    return [(points[i], points[i + 1], "F.Cu", trace) for i in range(len(points) - 1)]


def wheeler(turns, width, height, trace, gap):
    """Modified Wheeler for a regular spiral, applied to the square of equal area."""
    side = math.sqrt(width * height)
    d_in = side - 2 * (turns * trace + (turns - 1) * gap)
    d_avg, rho = (side + d_in) / 2, (side - d_in) / (side + d_in)
    return 2.34 * MU0 * turns ** 2 * d_avg * 1e-3 / (1 + 2.75 * rho)


def f0(inductance, c_tun):
    return 1.0 / (2 * math.pi * math.sqrt(inductance * (c_tun + C_EXT + C_PAR)))


def main():
    data = json.loads((ROOT / "scripts" / "pcb" / "mb1163_nfc.json").read_text(encoding="utf-8"))
    path, spare = walk(data)
    x0, y0, x1, y1 = data["coil"]["bbox"]
    trace = max(w for _, _, _, w in path)
    check = (4, x1 - x0, y1 - y0, trace, trace)
    l_top, l_wheeler = greenhouse(ideal_spiral(*check), 0.0), wheeler(*check)
    agreement = 100.0 * (l_wheeler - l_top) / l_top
    results = {}
    for name, dz in BOARDS.items():
        inductance = greenhouse(path, dz)
        results[name] = {"copper_distance_mm": round(dz, 4), "L_uH": round(inductance * 1e6, 4),
                         "f0_MHz": round(f0(inductance, C_TUN[1]) / 1e6, 3),
                         "f0_range_MHz": [round(f0(inductance, c) / 1e6, 3) for c in (C_TUN[2], C_TUN[0])]}
    st, ours = results.values()
    shift = 100.0 * (ours["f0_MHz"] / st["f0_MHz"] - 1)
    l_ours = ours["L_uH"] * 1e-6
    trim = 1.0 / ((2 * math.pi * F_CARRIER) ** 2 * l_ours) - (C_TUN[1] + C_EXT + C_PAR)
    print(f"ANT14: {len(path)} segments walked AC0 -> AC1 ({len(spare)} overlapping duplicate(s) left out)")
    print(f"method check, a regular 4-turn {check[1]:.1f} x {check[2]:.1f} mm spiral, {trace} / {trace} mm: Greenhouse "
          f"{l_top * 1e6:.3f} uH, modified Wheeler {l_wheeler * 1e6:.3f} uH ({agreement:+.1f} %)")
    for name, r in results.items():
        print(f"{name}: copper {r['copper_distance_mm']:.3f} mm apart, L {r['L_uH']:.3f} uH, f0 {r['f0_MHz']:.2f} MHz "
              f"({r['f0_range_MHz'][0]:.2f}-{r['f0_range_MHz'][1]:.2f} over C_TUN 27.5-22.5 pF)")
    print(f"ours vs ST's: f0 {shift:+.2f} %; C across the coil = C_TUN 25 + C6/C8 in series 23.5 + 1 pF (ASSUMPTION)")
    print(f"to put f0 on 13.56 MHz: +{trim * 1e12:.1f} pF across the coil (C2 position), or {2 * trim * 1e12:.1f} pF on "
          f"each of C7 / C9 (both not fitted, as on ST's board): fit only after a measurement")
    result = {"source": "scripts/pcb/mb1163_nfc.json (MB1163 rev C-01, ANT14)", "boards": results,
              "f0_shift_pct": round(shift, 3), "trim_to_13p56_pF": {"across_coil_C2": round(trim * 1e12, 2),
                                                                   "each_of_C7_C9": round(2 * trim * 1e12, 2)}, "c_tun_pF": [c * 1e12 for c in C_TUN], "c_ext_pF": C_EXT * 1e12,
              "c_parasitic_pF": C_PAR * 1e12, "method_check": {"spiral": "regular, 4 turns, ANT14 outline / track / gap", "L_greenhouse_uH": round(l_top * 1e6, 4),
                                                               "L_wheeler_uH": round(l_wheeler * 1e6, 4),
                                                               "agreement_pct": round(agreement, 2)},
              "sources": {"c_tun": "DocID023790 Rev 20 (M24SR64-Y), CTUN in SO8: 22.5 / 25 / 27.5 pF at 13.56 MHz",
                          "c_ext": "MB1163 C-01 schematic: C6 / C8 47 pF from AC1 / AC0 to GND",
                          "c_parasitic": "ASSUMPTION 1 pF pads and traces",
                          "greenhouse": "H. M. Greenhouse, IEEE Trans. Parts, Hybrids, and Packaging PHP-10(2), 1974",
                          "wheeler": "S. S. Mohan et al., IEEE JSSC 34(10), 1999, modified Wheeler K1 2.34, K2 2.75"}}
    (ROOT / "simulation" / "results" / "nfc_coil.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    ok = abs(agreement) <= 5.0 and abs(shift) <= 2.0 and len(spare) <= 1
    print("PASS" if ok else "FAIL", f"method agreement {agreement:+.1f} % (limit 5 %), stack-up shift {shift:+.2f} % (limit 2 %)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
