#!/usr/bin/env python3
"""S2: one DRV8711 H-bridge at transistor level (CSD88537ND models) driving one motor in slow decay.

Forward effort e in slow decay (firmware BridgeMapping): AIN1 held high, AIN2 PWM, so half-bridge 1 switches
(HS1/LS1 complementary with dead time) and LS2 stays on. Centre-aligned 25 kHz (MotionActuationImpl.hpp:18),
DTIME 850 ns (Drv8711DriverConfiguration). DRV8711 gate drive = 10 V steps through R = 10 V / mean(IDRIVEP, IDRIVEN)
(SLVSC40 p.6, p.28), i.e. 133 Ohm for setting 00 and 33 Ohm for setting 11. Hot-loop inductance between the 100 nF cap and the FETs is a corner.
Ideal: battery stiff behind 60 mOhm; no current chopping (stall at duty <= 0.9 stays below the 1.3 A trip).
"""

import itertools
import sys

import numpy as np

import common
import kicad_values
import spice
from kicad_values import get

A = common.ASSUMPTIONS
PERIOD, DEAD = 40e-6, 850e-9


def netlist(duty, emf, i_source, i_sink, loop_l, schottky=False):
    on = duty * PERIOD
    hs_delay, hs_width = PERIOD / 2 - on / 2 + DEAD, max(on - 2 * DEAD, 10e-9)
    ls_delay, ls_width = PERIOD / 2 + on / 2 + DEAD, max(PERIOD - on - 2 * DEAD, 10e-9)
    c10 = A["mlcc_10u_25v_at_12v"]["value"]
    return spice.include("devices.lib") + f"""
VB BSRC 0 12.6
RB BSRC VBAT {A['battery_r_int']['nominal'] + A['fuse_r']['value'] + 0.03}
XC507 VBAT 0 ELCAP220U
C502 VBAT 0 {c10}
LBUS VBAT VHF 2n
RBUS VBAT VHF 10
C503 VHF 0 {get('C503')}
LLOOPH VHF VD {loop_l / 2}
RLOOPH VHF VD 10
LLOOPL SENSE_GND 0 {loop_l / 2}
RLOOPL SENSE_GND 0 10
.options itl4=200 reltol=1e-3 vntol=1e-5 abstol=1e-9
MH1 VD GH1 OUT1 CSD88537
ML1 OUT1 GL1 SENSE CSD88537
MH2 VD GH2 OUT2 CSD88537
ML2 OUT2 GL2 SENSE CSD88537
RSENSE SENSE SENSE_GND {get('R509')}
RM OUT1 MA {A['motor_r']['value']}
LM MA MB {A['motor_l']['value']}
VEMF MB OUT2 {emf}
VHCMD HC 0 PULSE(0 1 {hs_delay} 5n 5n {hs_width} {PERIOD})
VLCMD LC 0 PULSE(0 1 {ls_delay} 5n 5n {ls_width} {PERIOD})
EH1 GHD OUT1 HC 0 10
RH1 GHD GH1 {10 / ((i_source + i_sink) / 2):.1f}
EL1 GLD 0 LC 0 10
RL1 GLD GL1 {10 / ((i_source + i_sink) / 2):.1f}
VGH2 GH2 OUT2 0
VGL2 GL2 0 10
""" + ("DS1 SENSE_GND OUT1 SS34\nDS2 SENSE_GND OUT2 SS34\n" if schottky else "")


def run(duty, emf, i_source, i_sink, loop_l, tag, schottky=False):
    vectors = ["v(OUT1)", "v(VD)", "v(SENSE)", "i(VEMF)", "@mh1[id]", "@ml1[id]", "i(VB)", "v(GH1)", "v(GL1)",
               "@c.xc507.c1[i]", "@c502[i]", "@c503[i]"]
    save = "save " + " ".join(["v(OUT1)", "v(VD)", "v(SENSE)", "i(VEMF)", "@mh1[id]", "@ml1[id]", "i(VB)",
                               "v(GH1)", "v(GL1)", "@c.xc507.c1[i]", "@c502[i]", "@c503[i]"])
    analysis = f"{save}\ntran 2n 2.4m 2.0m 4n"
    return spice.run(f"s2_{tag}", netlist(duty, emf, i_source, i_sink, loop_l, schottky), vectors, analysis, timeout=1200)


def metrics(r, duty):
    t = r["x"]
    out, vd = r["v(OUT1)"], r["v(VD)"]
    i_motor = r["i(VEMF)"]
    i_h, i_l = r["@mh1[id]"], r["@ml1[id]"]
    p_h = np.abs((vd - out) * i_h)
    p_l = np.abs((out - r["v(SENSE)"]) * i_l)
    span = t[-1] - t[0]
    p_h_avg = np.trapezoid(p_h, t) / span
    p_l_avg = np.trapezoid(p_l, t) / span
    shoot = np.max(np.minimum(np.abs(i_h), np.abs(i_l)))
    dt = np.diff(t)
    keep = dt > 0
    rising = np.diff(out)[keep] / dt[keep]
    dt_all = np.diff(t, prepend=t[0])
    periods = (t[-1] - t[0]) / PERIOD
    freewheel = (out < -0.1) & (out > -3.0)
    return {
        "freewheel_plateau_V": float(np.median(out[freewheel])) if np.any(freewheel) else 0.0,
        "ns_below_minus_0V6_per_period": float(np.sum(dt_all[out < -0.6]) / periods * 1e9),
        "duty": duty, "i_motor_avg_A": float(np.mean(i_motor)), "i_ripple_pp_mA": float(np.ptp(i_motor) * 1e3),
        "out_overshoot_V": float(np.max(out) - np.mean(vd)), "out_undershoot_V": float(-np.min(out)),
        "vds_hs_max_V": float(np.max(vd - out)), "vds_ls_max_V": float(np.max(out - r["v(SENSE)"])),
        "dvdt_max_V_per_ns": float(np.max(np.abs(rising)) * 1e-9),
        "shoot_through_A": float(shoot), "p_hs_W": float(p_h_avg), "p_ls_W": float(p_l_avg),
        "package_tj_C": float(40 + (p_h_avg + p_l_avg) * 75),
        "c507_rms_A": float(np.sqrt(np.mean(r["@c.xc507.c1[i]"] ** 2))),
        "c502_rms_A": float(np.sqrt(np.mean(r["@c502[i]"] ** 2))),
        "c503_rms_A": float(np.sqrt(np.mean(r["@c503[i]"] ** 2))),
    }


def main():
    drives = {"IDRIVE 00 (50/100 mA)": (0.05, 0.10), "IDRIVE 11 (200/400 mA)": (0.20, 0.40)}
    loops = {"loop 5 nH": 5e-9, "loop 15 nH": 15e-9}
    points = {"stall D0.5": (0.5, 0.0), "stall D0.9": (0.9, 0.0), "running D0.9 E9V": (0.9, 9.0)}
    assert all(kicad_values.values()[f"D50{i}"]["raw"] == "SS34" for i in range(1, 5)), "SS34 clamps missing"
    variants = {"phase1 (no clamps)": False, "current (SS34 D501-D504)": True}
    results, traces = {}, {}
    for (vname, schottky), (dname, (isrc, isnk)), (lname, loop), (pname, (duty, emf)) in itertools.product(
            variants.items(), drives.items(), loops.items(), points.items()):
        tag = f"{vname.split()[0]}_{dname.split()[1]}_{round(loop * 1e9)}nH_{pname.replace(' ', '_').replace('.', 'p')}"
        r = run(duty, emf, isrc, isnk, loop, tag, schottky)
        key = f"{vname} | {dname} | {lname} | {pname}"
        results[key] = metrics(r, duty)
        traces[key] = r
        m = results[key]
        print(f"{key:66} I={m['i_motor_avg_A']:.2f}A ripple={m['i_ripple_pp_mA']:.0f}mA over={m['out_overshoot_V']:.2f}V "
              f"under={m['out_undershoot_V']:.2f}V plateau={m['freewheel_plateau_V']:.2f}V "
              f"below-0.6V={m['ns_below_minus_0V6_per_period']:.0f}ns P={m['p_hs_W'] + m['p_ls_W']:.3f}W Tj={m['package_tj_C']:.0f}C "
              f"shoot={m['shoot_through_A']:.2f}A")
    recommended = {k: m for k, m in results.items() if k.startswith("current") and "IDRIVE 00" in k}
    checks = {
        "no_shoot_through": all(m["shoot_through_A"] < 0.2 for m in results.values()),
        "phase_node_plateau_above_minus_0V6_recommended": all(m["freewheel_plateau_V"] > -0.6 for m in recommended.values()),
        "phase_node_spike_below_20ns_at_5nH_recommended": all(m["ns_below_minus_0V6_per_period"] < 20
                                                              for k, m in recommended.items() if "5 nH" in k),
        "switch_node_overshoot_below_20pct_recommended": all(m["out_overshoot_V"] < 0.2 * 12.6 for m in recommended.values()),
        "vds_below_80pct_rating": all(max(m["vds_hs_max_V"], m["vds_ls_max_V"]) < 48 for m in results.values()),
        "fet_tj_below_100C": all(m["package_tj_C"] < 100 for m in results.values()),
        "ripple_below_150mA_pp": all(m["i_ripple_pp_mA"] < 150 for m in results.values()),
    }
    common.save("s2_bridge", {"results": results, "checks": checks, "recommended": "IDRIVE 00 (firmware) with the SS34 clamps D501-D504 now in the schematic",
                               "assumptions": {k: A[k] for k in ("motor_r", "motor_l", "mlcc_10u_25v_at_12v")}})
    plot(traces)
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return checks


def plot(traces):
    fig, axes = common.figure(3, "S2 HS turn-off + dead time, stall D0.9, 5 nH: no clamps vs SS34, IDRIVE 00 vs 11")
    for key, r in traces.items():
        if "stall D0.9" not in key or "15 nH" in key:
            continue
        t = (r["x"] - r["x"][0]) * 1e6
        sel = (t > 36.9) & (t < 38.4)
        axes[0].plot(t[sel], r["v(OUT1)"][sel], label=key.replace(" | stall D0.9", "").replace(" | loop 5 nH", ""))
        axes[1].plot(t[sel], r["v(GH1)"][sel] - r["v(OUT1)"][sel])
        axes[2].plot(t[sel], r["@mh1[id]"][sel])
    axes[0].axhline(-0.6, ls=":", c="grey")
    axes[0].set_ylabel("switch node (V)")
    axes[1].set_ylabel("HS V_GS (V)")
    axes[2].set_ylabel("HS I_D (A)")
    axes[2].set_xlabel("time in period (us)")
    axes[0].legend(fontsize=6)
    common.finish(fig, "s2_edges")


if __name__ == "__main__":
    sys.exit(0 if all(main().values()) else 1)
