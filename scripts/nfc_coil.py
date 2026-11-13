#!/usr/bin/env python3
"""13.56 MHz printed loop antenna for the ST25DV04KC NFC tag (D-030): size it and write its footprint.

Target. The tag resonates its coil with the internal tuning capacitance C_TUN = 28.5 pF (DS13519 Rev 6, RF
characteristics table). f0 = 1 / (2 pi sqrt(L (C_TUN + C_PAR))). The coil is sized for f0 a little above 13.56 MHz
(TARGET_F0) so the DNP tuning capacitor across AC0-AC1 can pull it down, and metal nearby (battery, screws) only lowers
it further.

Inductance, two independent ways (they must agree within 5 %):
  - Greenhouse: the spiral is split into straight segments; L = sum of segment self-inductances
    (rectangular bar, 0.002 l [ln(2l/(w+t)) + 0.50049 + (w+t)/(3l)] uH, l in cm) plus the mutual inductance of every
    pair of parallel segments from the Neumann integral for parallel filaments (Greenhouse, IEEE Trans. PHP-10, 1974).
  - Modified Wheeler for a square spiral, L = K1 mu0 n^2 d_avg / (1 + K2 rho), K1 2.34, K2 2.75 (Mohan et al., IEEE
    JSSC 34(10), 1999), applied to the square of equal area. A cross-check only: the coil is rectangular.

Footprint (hardware/e-inverted-pendulum/e-inverted-pendulum.pretty/NFC_Coil_25x21mm.kicad_mod), built like KiCad's SWRA117D antenna:
  - pad 1 (AC0 end) at the outer start, pad 2 at the inner end (a via) and again outside the coil (a via);
  - the spiral is footprint copper on F.Cu, the underpass on B.Cu; net_tie_pad_groups "1,2" allows the coil to join
    pads 1 and 2.

Run: python3 scripts/nfc_coil.py -> footprint, simulation/results/nfc_coil.json
"""

import json
import math
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "schgen"))
from make_footprints import PRETTY, footprint, hidden, label, uid  # noqa: E402
from sexpr import Str, Sym, dump  # noqa: E402

MU0 = 4e-7 * math.pi
C_TUN = 28.5e-12
C_PAR = 1.0e-12
TARGET_F0 = 13.9e6
F_CARRIER = 13.56e6

COIL = {"width": 25.0, "height": 21.0, "trace": 0.15, "gap": 0.15, "copper_t": 0.035, "underpass_dz": 1.49}
NAME = "NFC_Coil_25x21mm"
LEAD = 1.0
INNER_STUB = 1.0
VIA = {"size": 0.6, "drill": 0.3}


def spiral(turns, width, height, pitch):
    points = [(0.0, 0.0)]
    for i in range(turns):
        left, right, top, bottom = i * pitch, width - i * pitch, i * pitch, height - i * pitch
        end = (i + 1) * pitch if i + 1 < turns else height / 2
        points += [(right, top), (right, bottom), (left, bottom), (left, end)]
    return points


def segments(turns):
    c = COIL
    pitch = c["trace"] + c["gap"]
    w, h = c["width"] - c["trace"], c["height"] - c["trace"]
    pts = spiral(turns, w, h, pitch)
    last = pts[-1]
    inner = (last[0] + INNER_STUB, last[1])
    segs = [((-LEAD, 0.0), (0.0, 0.0), 0.0)]
    segs += [(pts[i], pts[i + 1], 0.0) for i in range(len(pts) - 1)]
    segs.append((last, inner, 0.0))
    segs.append((inner, (-LEAD, inner[1]), c["underpass_dz"]))
    return segs, pts, inner


def self_inductance(length_mm):
    c = COIL
    l_cm, wt_cm = length_mm / 10.0, (c["trace"] + c["copper_t"]) / 10.0
    return 0.002 * l_cm * (math.log(2 * l_cm / wt_cm) + 0.50049 + wt_cm / (3 * l_cm)) * 1e-6


def _g(u, d):
    return u * math.asinh(u / d) - math.hypot(u, d)


def mutual(seg_a, seg_b):
    (a0, a1, za), (b0, b1, zb) = seg_a, seg_b
    if a0[1] == a1[1] and b0[1] == b1[1]:
        axis, fixed = 0, 1
    elif a0[0] == a1[0] and b0[0] == b1[0]:
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


def greenhouse(turns):
    segs, _, _ = segments(turns)
    total = sum(self_inductance(math.dist(a, b)) for a, b, _ in segs)
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            total += 2.0 * mutual(segs[i], segs[j])
    return total


def wheeler(turns):
    c = COIL
    side = math.sqrt(c["width"] * c["height"])
    d_out = side
    d_in = side - 2 * (turns * c["trace"] + (turns - 1) * c["gap"])
    d_avg, rho = (d_out + d_in) / 2, (d_out - d_in) / (d_out + d_in)
    return 2.34 * MU0 * turns ** 2 * d_avg * 1e-3 / (1 + 2.75 * rho)


def resonance(inductance, extra_c=0.0):
    return 1.0 / (2 * math.pi * math.sqrt(inductance * (C_TUN + C_PAR + extra_c)))


def write_footprint(turns):
    segs, pts, inner = segments(turns)
    c = COIL
    ox, oy = c["width"] / 2, c["height"] / 2

    def at(point):
        return round(point[0] - ox + c["trace"] / 2, 4), round(point[1] - oy + c["trace"] / 2, 4)

    items = []
    for index, (a, b, dz) in enumerate(segs):
        layer = "B.Cu" if dz else "F.Cu"
        (x0, y0), (x1, y1) = at(a), at(b)
        items.append([Sym("fp_line"), [Sym("start"), x0, y0], [Sym("end"), x1, y1],
                      [Sym("stroke"), [Sym("width"), c["trace"]], [Sym("type"), Sym("solid")]],
                      [Sym("layer"), Str(layer)], [Sym("uuid"), uid(NAME, "seg", index)]])
    start = at((-LEAD, 0.0))
    inner_xy, outer_xy = at(inner), at((-LEAD, inner[1]))
    pads = [
        [Sym("pad"), Str("1"), Sym("smd"), Sym("rect"), [Sym("at"), *start], [Sym("size"), 0.5, 0.5],
         [Sym("layers"), Str("F.Cu"), Str("F.Mask")], [Sym("uuid"), uid(NAME, "pad1")]],
    ]
    for tag, xy in (("inner", inner_xy), ("outer", outer_xy)):
        pads.append([Sym("pad"), Str("2"), Sym("thru_hole"), Sym("circle"), [Sym("at"), *xy],
                     [Sym("size"), VIA["size"], VIA["size"]], [Sym("drill"), VIA["drill"]],
                     [Sym("layers"), Str("*.Cu")], [Sym("remove_unused_layers"), Sym("no")],
                     [Sym("uuid"), uid(NAME, "pad2", tag)]])
    half_w, half_h = c["width"] / 2, c["height"] / 2
    node = footprint(
        NAME,
        f"13.56 MHz printed loop for ST25DV04KC: {turns} turns, {c['width']} x {c['height']} mm, "
        f"{c['trace']}/{c['gap']} mm, F.Cu spiral with a B.Cu underpass (scripts/nfc_coil.py, docs/nfc.md)",
        "smd", (-half_w, -half_h, half_w, half_h), (-half_w - LEAD - 0.6, -half_h - 0.5, half_w + 0.5, half_h + 0.5),
        pads, items + [label("NFC", 0, 0, "F.Fab", NAME, "label")], silk=False)
    attr = next(i for i in node if isinstance(i, list) and i and i[0] == Sym("attr"))
    attr[1:] = [Sym("smd"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom")]
    node.insert(node.index(attr) + 1, [Sym("net_tie_pad_groups"), Str("1,2")])
    path = PRETTY / f"{NAME}.kicad_mod"
    path.write_text(dump(node) + "\n", encoding="utf-8")
    subprocess.run(["kicad-cli", "fp", "upgrade", "--force", str(PRETTY)], check=True, capture_output=True)
    return path


def main():
    candidates = []
    for turns in range(4, 16):
        segs, _, _ = segments(turns)
        inner_x = segs[-1][0][0]
        if inner_x + VIA["size"] / 2 + 1.0 > COIL["width"] - COIL["trace"] - (turns - 1) * (COIL["trace"] + COIL["gap"]):
            break
        l_gh, l_wh = greenhouse(turns), wheeler(turns)
        candidates.append({"turns": turns, "L_greenhouse_uH": l_gh * 1e6, "L_wheeler_uH": l_wh * 1e6,
                           "agreement_pct": 100.0 * (l_wh - l_gh) / l_gh, "f0_MHz": resonance(l_gh) / 1e6})
    best = min(candidates, key=lambda c: abs(c["f0_MHz"] * 1e6 - TARGET_F0))
    l_best = best["L_greenhouse_uH"] * 1e-6
    trim = 1.0 / ((2 * math.pi * F_CARRIER) ** 2 * l_best) - C_TUN - C_PAR
    best["trim_cap_to_13p56_pF"] = trim * 1e12
    best["f0_with_trim_MHz"] = resonance(l_best, trim) / 1e6
    print(f"{'turns':>5} {'L GH (uH)':>9} {'L MW (uH)':>9} {'diff %':>7} {'f0 (MHz)':>8}")
    for c in candidates:
        print(f"{c['turns']:5d} {c['L_greenhouse_uH']:9.3f} {c['L_wheeler_uH']:9.3f} {c['agreement_pct']:7.1f} {c['f0_MHz']:8.2f}")
    print(f"chosen {best['turns']} turns: L {best['L_greenhouse_uH']:.2f} uH, f0 {best['f0_MHz']:.2f} MHz with "
          f"C_TUN {C_TUN * 1e12:.1f} pF + {C_PAR * 1e12:.1f} pF parasitic (ASSUMPTION); "
          f"trim to 13.56 MHz with {best['trim_cap_to_13p56_pF']:.1f} pF across AC0-AC1")
    path = write_footprint(best["turns"])
    result = {"coil": COIL, "target_f0_MHz": TARGET_F0 / 1e6, "c_tun_pF": C_TUN * 1e12, "c_parasitic_pF": C_PAR * 1e12,
              "candidates": candidates, "chosen": best, "footprint": str(path.relative_to(ROOT)),
              "sources": {"c_tun": "DS13519 Rev 6, RF characteristics: CTUN 28.5 pF typ at 13.56 MHz",
                          "c_parasitic": "ASSUMPTION 1 pF coil + pad capacitance",
                          "greenhouse": "H. M. Greenhouse, IEEE Trans. Parts, Hybrids, and Packaging PHP-10(2), 1974",
                          "wheeler": "S. S. Mohan et al., IEEE JSSC 34(10), 1999, modified Wheeler K1 2.34, K2 2.75"}}
    (ROOT / "simulation" / "results" / "nfc_coil.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    ok = abs(best["agreement_pct"]) <= 5.0 and abs(best["f0_MHz"] * 1e6 / TARGET_F0 - 1) <= 0.03
    print("PASS" if ok else "FAIL", f"agreement {best['agreement_pct']:.1f} %, f0 within 3 % of {TARGET_F0 / 1e6} MHz")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
