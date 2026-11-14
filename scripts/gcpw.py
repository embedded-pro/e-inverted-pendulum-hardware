#!/usr/bin/env python3
"""50 ohm grounded coplanar waveguide (GCPW) for the RF path, valid on JLC04161H-7628 and on Seeed's 4-layer (D-034).

Model: conformal mapping for coplanar waveguide with a lower ground plane (Wadell, Transmission
Line Design Handbook, 1991, s3.4; Simons, Coplanar Waveguide Circuits, 2001, s2.4), with the
conductor-thickness correction of Gupta et al. (Microstrip Lines and Slotlines, 2nd ed., s7.3):
the strip widens and the gap narrows by delta = (1.25 t / pi) (1 + ln(4 pi w / t)), and the air
part of the field grows with t / gap. Solder mask is ignored (it lowers Z0 by about 1-2 ohm).

Self-check: ST's MLPF-WB55-01E3 output line (DS12804 Fig. 13: 450 um strip, 106.4 um gaps, on
the Fig. 14 stack-up of 1507 um FR-4 and 48 um copper) must come out near 50 ohm.

Portable choice: with the gap fixed at the RF class clearance (0.15 mm), the width is the one on a 0.01 mm grid that
minimises the worst |Z0 - 50| over both fabs' stack-ups (Seeed publishes a Dk range, so all of it is covered).

Run: python3 scripts/gcpw.py  -> table on stdout and simulation/results/gcpw.json
"""

import json
import math
import pathlib

from scipy.optimize import brentq
from scipy.special import ellipk

ROOT = pathlib.Path(__file__).resolve().parent.parent

JLC04161H_7628 = {
    "name": "JLC04161H-7628 L1 over L2",
    "h_mm": 0.2104, "t_mm": 0.035, "er": 4.4,
    "source": "JLCPCB stack-up JLC04161H-7628: 7628 prepreg 0.2104 mm, Dk 4.4; 1 oz outer copper (D-008)",
}
SEEED_4L = {
    "name": "Seeed Fusion standard 4-layer, L1 over L2",
    "h_mm": 0.200, "t_mm": 0.035, "er_range": (4.2, 4.45, 4.7),
    "source": "Seeed KB 'What is the stack up of 4/6/8 layers boards?': prepreg 0.2 mm, fixed; Fusion PCB "
              "specification: FR-4 Dk 4.2-4.7, outer copper 0.035 mm (1 oz)",
}
GAP_MM = 0.15
ST_MLPF_REFERENCE = {
    "name": "DS12804 Fig. 14 reference (2-layer)",
    "h_mm": 1.507, "t_mm": 0.048, "er": 4.4,
    "source": "DS12804 Rev 2 Fig. 13 and Fig. 14; FR-4 Dk 4.4 ASSUMPTION",
}


def k_ratio(k):
    return ellipk(k * k) / ellipk(1.0 - k * k)


def gcpw(w_mm, s_mm, h_mm, t_mm, er):
    if t_mm > 0.0:
        delta = 1.25 * t_mm / math.pi * (1.0 + math.log(4.0 * math.pi * w_mm / t_mm))
        w_e, s_e = w_mm + delta, s_mm - delta / 2.0
    else:
        w_e, s_e = w_mm, s_mm
    k1 = w_e / (w_e + 2.0 * s_e)
    k3 = math.tanh(math.pi * w_e / (4.0 * h_mm)) / math.tanh(math.pi * (w_e + 2.0 * s_e) / (4.0 * h_mm))
    r1, r3 = k_ratio(k1), k_ratio(k3)
    e_eff = (r1 + er * r3) / (r1 + r3)
    if t_mm > 0.0:
        e_eff -= (e_eff - 1.0) * (0.7 * t_mm / s_mm) / (r1 + r3 + 0.7 * t_mm / s_mm)
    z0 = 60.0 * math.pi / math.sqrt(e_eff) / (r1 + r3)
    return z0, e_eff


def width_for(z_target, s_mm, stack):
    return brentq(lambda w: gcpw(w, s_mm, stack["h_mm"], stack["t_mm"], stack["er"])[0] - z_target, 0.05, 3.0)


def microstrip_w(z_target, stack):
    h, er = stack["h_mm"], stack["er"]
    a = z_target / 60.0 * math.sqrt((er + 1) / 2) + (er - 1) / (er + 1) * (0.23 + 0.11 / er)
    return h * 8.0 * math.exp(a) / (math.exp(2 * a) - 2.0)


def main():
    results = {"model": __doc__.split("\n\n")[1].replace("\n", " "), "stack": JLC04161H_7628}
    z_ref, _ = gcpw(0.450, 0.1064, **{k: ST_MLPF_REFERENCE[k] for k in ("h_mm", "t_mm", "er")})
    z_in, _ = gcpw(0.200, 0.104, **{k: ST_MLPF_REFERENCE[k] for k in ("h_mm", "t_mm", "er")})
    z_in_ours, e_in_ours = gcpw(0.200, 0.104, **{k: JLC04161H_7628[k] for k in ("h_mm", "t_mm", "er")})
    results["self_check"] = {
        "st_out_450_106": z_ref, "st_in_200_104": z_in,
        "st_in_200_104_on_jlc": z_in_ours, "pass": abs(z_ref - 50.0) <= 3.0,
    }
    print(f"self-check, DS12804 Fig. 13 on its own stack-up: OUT 450/106.4 um -> {z_ref:.1f} ohm, "
          f"IN 200/104 um -> {z_in:.1f} ohm")
    print(f"IN 200/104 um copied onto {JLC04161H_7628['name']}: {z_in_ours:.1f} ohm (e_eff {e_in_ours:.2f})")

    rows = []
    print(f"\n50 ohm on {JLC04161H_7628['name']} (h {JLC04161H_7628['h_mm']} mm, er {JLC04161H_7628['er']}, "
          f"t {JLC04161H_7628['t_mm']} mm)")
    print(f"{'gap mm':>7} {'width mm':>9} {'e_eff':>6} {'lambda_g mm':>11}")
    for gap in (0.127, 0.15, 0.175, 0.2):
        w = width_for(50.0, gap, JLC04161H_7628)
        _, e_eff = gcpw(w, gap, JLC04161H_7628["h_mm"], JLC04161H_7628["t_mm"], JLC04161H_7628["er"])
        lam = 299.792458 / 2.45 / math.sqrt(e_eff)
        rows.append({"gap_mm": gap, "width_mm": w, "e_eff": e_eff, "lambda_g_mm": lam})
        print(f"{gap:7.3f} {w:9.3f} {e_eff:6.2f} {lam:11.1f}")
    results["table"] = rows
    fabs = [(JLC04161H_7628["name"], JLC04161H_7628["h_mm"], JLC04161H_7628["er"])]
    fabs += [(f"{SEEED_4L['name']}, Dk {er}", SEEED_4L["h_mm"], er) for er in SEEED_4L["er_range"]]

    def spread(width):
        return [gcpw(width, GAP_MM, h, JLC04161H_7628["t_mm"], er)[0] for _, h, er in fabs]
    widths = [round(0.20 + 0.01 * i, 2) for i in range(16)]
    best = min(widths, key=lambda w: max(abs(z - 50.0) for z in spread(w)))
    chosen = {"gap_mm": GAP_MM, "width_mm": best, "per_fab": {n: z for (n, _, _), z in zip(fabs, spread(best))},
              "jlc_only_width_mm": round(width_for(50.0, GAP_MM, JLC04161H_7628), 2)}
    print(f"\nportable width (gap {GAP_MM} mm), Z0 in ohm per case: " + "; ".join(n for n, _, _ in fabs))
    for w in (chosen["jlc_only_width_mm"], best):
        print(f"  {w:.2f} mm: " + ", ".join(f"{z:.1f}" for z in spread(w)))
    z_chosen, e_chosen = gcpw(best, GAP_MM, JLC04161H_7628["h_mm"], JLC04161H_7628["t_mm"], JLC04161H_7628["er"])
    z_lo = min(gcpw(best + 0.03, GAP_MM - 0.03, h * 0.9, JLC04161H_7628["t_mm"], er * 1.05)[0] for _, h, er in fabs)
    z_hi = max(gcpw(best - 0.03, GAP_MM + 0.03, h * 1.1, JLC04161H_7628["t_mm"], er * 0.95)[0] for _, h, er in fabs)
    chosen.update({"z0": z_chosen, "e_eff": e_chosen,
                   "corners": "both fabs, plus width +/-0.03 mm, gap -/+0.03 mm, h -/+10 %, er +/-5 % "
                              "(ASSUMPTION fab tolerances)",
                   "z0_low_corner": z_lo, "z0_high_corner": z_hi, "seeed_stack": SEEED_4L,
                   "microstrip_limit_width_mm": microstrip_w(50.0, JLC04161H_7628)})
    results["chosen"] = chosen
    gamma = max(abs(z - 50.0) / (z + 50.0) for z in (z_lo, z_hi))
    chosen["worst_return_loss_db"] = -20.0 * math.log10(gamma)
    worst = max(abs(z - 50.0) for z in chosen["per_fab"].values())
    print(f"\nchosen: width {best} mm, gap {GAP_MM} mm -> {z_chosen:.1f} ohm on JLC, worst {worst:.1f} ohm off 50 "
          f"across both fabs; tolerance corners {z_lo:.1f}-{z_hi:.1f} ohm (return loss >= "
          f"{chosen['worst_return_loss_db']:.0f} dB)")
    print(f"microstrip limit (Hammerstad) for the same stack-up: {chosen['microstrip_limit_width_mm']:.3f} mm")

    out = ROOT / "simulation" / "results" / "gcpw.json"
    out.write_text(json.dumps(results, indent=2, default=float) + "\n", encoding="utf-8")
    return 0 if results["self_check"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
