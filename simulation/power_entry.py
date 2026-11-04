#!/usr/bin/env python3
"""S1: battery input, back-to-back P-FET switch with Miller soft start, TVS, regeneration at switch-off.

Values come from the schematic (kicad_values.get). Ideal or assumed parts are listed in common.ASSUMPTIONS:
battery = EMF + R_int + lead inductance; buck = constant-power load (1.56 W) enabled above its 9.1 V UVLO;
switch = 0.1 Ohm when closed; motors = R + L + back-EMF with the bridge FETs off (body diodes only).
"""

import sys

import numpy as np

import common
import kicad_values
import spice
from kicad_values import get

PHASE1 = {"R102": 10e3, "C101": 220e-9}

A = common.ASSUMPTIONS


def bus_caps():
    c10 = A["mlcc_10u_25v_at_12v"]["value"]
    return f"""
XC507 VBAT 0 ELCAP220U
C508 VBAT 0 {get('C508')}
C502 VBAT 0 {c10}
C505 VBAT 0 {c10}
C503 VBAT 0 {get('C503')}
C506 VBAT 0 {get('C506')}
C201 VBAT 0 {c10}
C202 VBAT 0 {c10}
C203 VBAT 0 {get('C203')}
R104 VBAT VSENSE {get('R104')}
R105 VSENSE 0 {get('R105')}
C103 VSENSE 0 {get('C103')}
Bbuck VBAT 0 I = {A['logic_power']['value']}/max(V(VBAT),1) * 0.5*(1+tanh((V(VBAT)-9.1)*20))
"""


def entry(battery, switch, r_int, phase1=False):
    gate_cap = "" if phase1 else f"C102 PP_G PP_S {get('C102')}\n"
    return gate_cap + f"""
VB BSRC 0 {battery}
RINT BSRC B1 {r_int}
LLEAD B1 BAT_P {A['battery_loop_l']['value']}
RFUSE BAT_P BAT_F {A['fuse_r']['value']}
M1 BAT_F PP_G PP_S AO4805
M2 VBAT PP_G PP_S AO4805
R101 PP_G PP_S {get('R101')}
D101 PP_G PP_S BZT52C15
R102 PP_G SW_ON {get('R102')}
VSWC CTL 0 {switch}
S1 SW_ON 0 CTL 0 SWMOD
.model SWMOD SW (Ron=0.1 Roff=1e9 Vt=0.5 Vh=0.1)
R103 PP_G PP_SS {get('R103')}
C101 PP_SS VBAT {get('C101')}
D102 0 VBAT SMBJ15A
"""


def motors(emf, drive):
    """Two motors on full bridges reduced to body diodes; `drive` closes HS-P/LS-N until 1 ms (stall current)."""
    text = ""
    for side in ("L", "R"):
        text += f"""
RM{side} M{side}P A{side} {A['motor_r']['value']}
LM{side} A{side} B{side} {A['motor_l']['value']}
VE{side} B{side} M{side}N {emf}
DH{side}P M{side}P VBAT DBODY
DL{side}P 0 M{side}P DBODY
DH{side}N M{side}N VBAT DBODY
DL{side}N 0 M{side}N DBODY
SH{side} VBAT M{side}P DRV 0 SWMOD
SL{side} M{side}N 0 DRV 0 SWMOD
"""
    return text + f"VDRV DRV 0 {drive}\n.model DBODY D (Is=1e-12 N=1 Rs=10m Tt=6n)\n"


def run_case(name, battery, switch, r_int, t_end, extra="", uic=False, step=1e-6, phase1=False):
    if phase1:
        kicad_values.PROPOSED.update(PHASE1)
    try:
        net = spice.include("devices.lib") + entry(battery, switch, r_int, phase1) + bus_caps() + extra
    finally:
        for ref in PHASE1:
            kicad_values.PROPOSED.pop(ref, None)
    name = f"{name}_{'phase1' if phase1 else 'current'}"
    analysis = f"save all @d102[id]\ntran {step} {t_end}{' uic' if uic else ''}"
    vectors = ["v(VBAT)", "i(VB)", "v(PP_G)", "v(PP_S)", "v(BAT_F)", "@d102[id]"]
    return spice.run(f"s1_{name}", net, vectors, analysis)


def metrics(r, t0=0.0):
    t = r["x"]
    i_bat = -r["i(VB)"]
    vgs = r["v(PP_G)"] - r["v(PP_S)"]
    p_fet2 = np.abs(r["v(VBAT)"] - r["v(PP_S)"]) * np.abs(i_bat)
    sel = t >= t0
    v = r["v(VBAT)"]
    v_end = v[-1]
    rise = t[sel][v[sel] >= 0.9 * v_end][0] - t[sel][v[sel] >= 0.1 * v_end][0] if v_end > 1 else None
    energy = np.trapezoid(p_fet2, t)
    return {"i_peak_A": float(np.max(np.abs(i_bat))), "vbat_end_V": float(v_end), "vbat_peak_V": float(np.max(v)),
            "rise_10_90_ms": None if rise is None else float(rise * 1e3), "vgs_min_V": float(np.min(vgs)),
            "vgs_max_V": float(np.max(vgs)), "fet2_peak_power_W": float(np.max(p_fet2)),
            "fet2_energy_mJ": float(energy * 1e3), "i2t_A2s": float(np.trapezoid(i_bat ** 2, t)),
            "tvs_peak_A": float(np.max(np.abs(r["@d102[id]"])))}


def cases(phase1):
    results, traces = {}, {}
    for corner, r_int in (("new", A["battery_r_int"]["nominal"]), ("aged", A["battery_r_int"]["worst"])):
        r = run_case(f"switch_on_{corner}", "12.6", "PWL(0 0 1m 0 1.001m 1)", r_int, "120m", phase1=phase1)
        results[f"switch_on_{corner}"] = metrics(r, 1e-3)
        traces[f"switch_on_{corner}"] = r
    r = run_case("hot_plug_on", "PWL(0 0 1m 0 1.001m 12.6)", "1", A["battery_r_int"]["nominal"], "120m", phase1=phase1)
    results["hot_plug_switch_on"] = metrics(r, 1e-3)
    traces["hot_plug_switch_on"] = r
    r = run_case("hot_plug_off", "PWL(0 0 1m 0 1.001m 12.6)", "0", A["battery_r_int"]["nominal"], "40m", phase1=phase1)
    results["hot_plug_switch_off"] = metrics(r, 1e-3)
    traces["hot_plug_switch_off"] = r
    for state, sw in (("on", "1"), ("off", "0")):
        r = run_case(f"reverse_{state}", "PWL(0 0 1m 0 1.001m -12.6)", sw, A["battery_r_int"]["nominal"], "20m", phase1=phase1)
        m = metrics(r, 1e-3)
        m["vbat_min_V"] = float(np.min(r["v(VBAT)"]))
        results[f"reverse_switch_{state}"] = m
    switch_off = "PWL(0 1 150m 1 150.001m 0)"
    for label, emf, drive in (("stall_dump", 0.0, "PWL(0 1 150m 1 150.001m 0)"), ("pushed_20V_emf", 20.0, "0")):
        r = run_case(f"regen_{label}", "12.6", switch_off, A["battery_r_int"]["nominal"], "400m",
                     extra=motors(emf, drive), step=5e-6, phase1=phase1)
        t = r["x"]
        after = t >= 150e-3
        m = metrics(r)
        m.update({"emf_V": emf, "vbat_peak_after_off_V": float(np.max(r["v(VBAT)"][after]))})
        p_fet2 = np.abs(r["v(VBAT)"] - r["v(PP_S)"]) * np.abs(r["i(VB)"])
        m["fet2_energy_after_off_mJ"] = float(np.trapezoid(p_fet2[after], t[after]) * 1e3)
        results[f"regen_{label}"] = m
        traces[f"regen_{label}"] = r
    checks = {
        "inrush_switch_on_below_4A": max(results[k]["i_peak_A"] for k in ("switch_on_new", "switch_on_aged")) < 4.0,
        "hot_plug_switch_on_below_10A": results["hot_plug_switch_on"]["i_peak_A"] < 10.0,
        "hot_plug_switch_off_vbat_stays_below_1V": results["hot_plug_switch_off"]["vbat_peak_V"] < 1.0,
        "inrush_i2t_below_fuse_melt": max(v["i2t_A2s"] for k, v in results.items() if "switch_on" in k or "hot_plug" in k) < 1.745,
        "vgs_within_20V": all(abs(v["vgs_min_V"]) < 20 and abs(v["vgs_max_V"]) < 20 for v in results.values()),
        "reverse_load_current_below_1mA": all(results[k]["vbat_min_V"] > -0.1 for k in ("reverse_switch_on", "reverse_switch_off")),
        "regen_vbat_below_24V": all(results[k]["vbat_peak_after_off_V"] < 24.0 for k in results if k.startswith("regen")),
    }
    return results, traces, checks


def main():
    drawn, drawn_traces, drawn_checks = cases(True)
    proposed, proposed_traces, proposed_checks = cases(False)
    common.save("s1_power_entry", {"phase1_values": {"values": PHASE1, "note": "no C102 gate-source cap",
                                                     "results": drawn, "checks": drawn_checks},
                                    "current": {"results": proposed, "checks": proposed_checks},
                                    "assumptions": {k: A[k] for k in ("battery_r_int", "battery_loop_l", "fuse_r", "mlcc_10u_25v_at_12v", "logic_power", "motor_r", "motor_l")}})
    plot(drawn_traces, proposed_traces)
    print(f"{'case':28} {'metric':24} {'phase 1':>10} {'current':>10}")
    for case in drawn:
        for key in ("i_peak_A", "vbat_peak_V", "rise_10_90_ms", "vgs_min_V", "fet2_peak_power_W", "vbat_peak_after_off_V", "fet2_energy_after_off_mJ"):
            if key in drawn[case] and drawn[case][key] is not None:
                p = proposed[case].get(key)
                shown = "-" if p is None else f"{p:.3f}"
                print(f"{case:28} {key:24} {drawn[case][key]:10.3f} {shown:>10}")
    for k in drawn_checks:
        print(f"{k:45} phase1={'PASS' if drawn_checks[k] else 'FAIL'} current={'PASS' if proposed_checks[k] else 'FAIL'}")
    return proposed_checks


def plot(drawn, proposed):
    fig, axes = common.figure(3, "S1 power entry: Phase 1 values (solid) vs current schematic (dashed)")
    for name, color in (("switch_on_new", "C0"), ("hot_plug_switch_on", "C1"), ("hot_plug_switch_off", "C2")):
        for traces, style in ((drawn, "-"), (proposed, "--")):
            r = traces[name]
            t = r["x"] * 1e3
            axes[0].plot(t, r["v(VBAT)"], style, color=color, label=f"{name} ({'phase 1' if style == '-' else 'current'})")
            axes[1].plot(t, -r["i(VB)"], style, color=color)
            axes[2].plot(t, r["v(PP_G)"] - r["v(PP_S)"], style, color=color)
    axes[0].set_ylabel("VBAT (V)")
    axes[1].set_ylabel("battery current (A)")
    axes[1].set_yscale("symlog", linthresh=1)
    axes[2].set_ylabel("V_GS (V)")
    axes[2].set_xlabel("time (ms)")
    axes[0].legend(fontsize=6)
    common.finish(fig, "s1_switch_on")
    fig, axes = common.figure(2, "S1 switch-off at 150 ms: stalled motors (1.37 A) and pushed robot (20 V EMF)")
    for name, color in (("regen_stall_dump", "C0"), ("regen_pushed_20V_emf", "C3")):
        for traces, style in ((drawn, "-"), (proposed, "--")):
            r = traces[name]
            axes[0].plot(r["x"] * 1e3, r["v(VBAT)"], style, color=color, label=f"{name} ({'phase 1' if style == '-' else 'current'})")
            axes[1].plot(r["x"] * 1e3, -r["@d102[id]"], style, color=color)
    axes[0].axhline(24, ls=":", c="grey")
    axes[0].set_ylabel("VBAT (V)")
    axes[1].set_ylabel("TVS current (A)")
    axes[1].set_xlabel("time (ms)")
    axes[0].legend(fontsize=6)
    common.finish(fig, "s1_regen")


if __name__ == "__main__":
    sys.exit(0 if all(main().values()) else 1)
