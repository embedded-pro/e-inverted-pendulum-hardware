#!/usr/bin/env python3
"""S3: motor bus (VBAT) with both bridges switching in phase, battery sag, logic UVLO margin.

Bridges are reduced to their bus current: in slow decay the bus carries the motor current only during the
drive phase (S2), so each bridge draws I_motor x square(duty) at 25 kHz, both in phase (one timer, TIM1).
Battery = OCV + R_int + lead L; fuse and the two AO4805 FETs (~20 mOhm each at -6 V) in series; buck = 1.56 W.
"""

import sys

import numpy as np

import common
import spice
from kicad_values import get

A = common.ASSUMPTIONS
PERIOD = 40e-6


def netlist(ocv, r_int, duty, i_motor, step_at=None):
    c10 = A["mlcc_10u_25v_at_12v"]["value"]
    on = duty * PERIOD
    if step_at is None:
        load = f"PULSE(0 {2 * i_motor} {PERIOD / 2 - on / 2} 100n 100n {on} {PERIOD})"
    else:
        load = f"PWL(0 0 {step_at} 0 {step_at + 1e-6} {2 * i_motor})"
    return spice.include("devices.lib") + f"""
VB BSRC 0 {ocv}
RINT BSRC B1 {r_int}
LLEAD B1 B2 {A['battery_loop_l']['value']}
RPATH B2 VBAT {A['fuse_r']['value'] + 2 * 0.020}
XC507 VBAT 0 ELCAP220U
C508 VBAT 0 {get('C508')}
C502 VBAT 0 {c10}
C505 VBAT 0 {c10}
C503 VBAT 0 {get('C503')}
C506 VBAT 0 {get('C506')}
C201 VBAT 0 {c10}
C202 VBAT 0 {c10}
C203 VBAT 0 {get('C203')}
IBRIDGES VBAT 0 {load}
Bbuck VBAT 0 I = {A['logic_power']['value']}/max(V(VBAT),1) * 0.5*(1+tanh((V(VBAT)-8.47)*20))
"""


def main():
    results, traces = {}, {}
    for duty, current in ((0.5, 2.0), (0.59, 2.0), (0.5, 0.5)):
        r = spice.run(f"s3_ripple_d{int(duty * 100)}_{int(current * 100)}", netlist(12.6, A["battery_r_int"]["nominal"], duty, current),
                      ["v(VBAT)", "@c.xc507.c1[i]", "@c502[i]", "@c201[i]"],
                      "save v(VBAT) @c.xc507.c1[i] @c502[i] @c201[i]\ntran 20n 3m 2m", timeout=600)
        results[f"ripple_D{duty}_I{current}"] = {
            "vbat_ripple_pp_mV": float(np.ptp(r["v(VBAT)"]) * 1e3),
            "c507_rms_A": float(np.sqrt(np.mean(r["@c.xc507.c1[i]"] ** 2))),
            "c502_rms_A": float(np.sqrt(np.mean(r["@c502[i]"] ** 2))),
            "c201_rms_A": float(np.sqrt(np.mean(r["@c201[i]"] ** 2))),
        }
        traces[f"ripple_D{duty}_I{current}"] = r
    for ocv in (9.9, 9.0):
        r = spice.run(f"s3_sag_{ocv}", netlist(ocv, A["battery_r_int"]["worst"], 1.0, 2.0, step_at=1e-3),
                      ["v(VBAT)"], "tran 1u 6m", timeout=600)
        results[f"sag_ocv_{ocv}V_aged"] = {"vbat_min_V": float(np.min(r["v(VBAT)"])),
                                           "hand_V": ocv - (4.0 + 1.56 / ocv) * (A["battery_r_int"]["worst"] + A["fuse_r"]["value"] + 0.04)}
        traces[f"sag_{ocv}"] = r
    limit = 0.600 * 0.95
    checks = {
        "c507_ripple_within_rating_at_continuous_current": results["ripple_D0.5_I0.5"]["c507_rms_A"] < limit,
        "vbat_ripple_below_500mV": all(v["vbat_ripple_pp_mV"] < 500 for k, v in results.items() if k.startswith("ripple")),
        "logic_stays_up_at_9V9_aged": results["sag_ocv_9.9V_aged"]["vbat_min_V"] > 8.47 + 0.3,
        "drv8711_above_uvlo_at_9V0_aged": results["sag_ocv_9.0V_aged"]["vbat_min_V"] > 8.0,
        "logic_cuts_off_at_empty_pack_under_load": results["sag_ocv_9.0V_aged"]["vbat_min_V"] < 8.47,
    }
    common.save("s3_bus", {"results": results, "checks": checks,
                            "notes": {"c507_limit_A": limit, "uvlo_logic_stop_V": 8.47, "drv8711_uvlo_rising_max_V": 8.0}})
    fig, axes = common.figure(2, "S3 motor bus: both bridges at the 2.0 A trip in phase / sag with aged battery")
    for key in ("ripple_D0.5_I2.0", "ripple_D0.59_I2.0", "ripple_D0.5_I0.5"):
        r = traces[key]
        axes[0].plot((r["x"] - r["x"][0]) * 1e6, r["v(VBAT)"], label=key)
    axes[0].set_xlabel("time (us)")
    axes[0].set_ylabel("VBAT (V)")
    axes[0].legend(fontsize=7)
    for key in ("sag_9.9", "sag_9.0"):
        r = traces[key]
        axes[1].plot(r["x"] * 1e3, r["v(VBAT)"], label=f"OCV {key.split('_')[1]} V, 150 mOhm")
    axes[1].axhline(8.47, ls=":", c="grey")
    axes[1].set_xlabel("time (ms)")
    axes[1].set_ylabel("VBAT (V)")
    axes[1].legend(fontsize=7)
    common.finish(fig, "s3_bus")
    for k, v in results.items():
        print(k, {a: round(b, 3) for a, b in v.items()})
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return checks


if __name__ == "__main__":
    sys.exit(0 if all(main().values()) else 1)
