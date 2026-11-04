#!/usr/bin/env python3
"""S4: 5V0 buck (TPS62933F, datasheet equations) and 3V3 LDO (TI TLV75533P transient model).

Model limit: TI's only unencrypted buck model (TPS62933P, SLUM818) does not run in ngspice-42 (time step
collapses at ~10 us even with Gear, rshunt and STEADY_STATE). The buck is therefore covered by the datasheet
design equations (SLUSEA4 s10.2.2), and its loop transient response is a bench item. The LDO is simulated with
TI's model (SBVM831), fed by a 5V0 source that carries:
  - the buck switching ripple from the equations below;
  - the 25 kHz motor-bus ripple from S3, attenuated to an ASSUMED 50 mV p-p at 5V0 (about -12 dB, pessimistic
    for a current-mode buck below its crossover);
  - an ASSUMED 150 mV dip when the buzzer (+96 mA) starts.
Run `python3 fetch_models.py` first.
"""

import sys

import numpy as np

import common
import spice
from kicad_values import get

A = common.ASSUMPTIONS
TI = spice.MODELS / "ti"
FSW = 1.2e6


def buck_equations(vin):
    vout = 0.8 * (1 + get("R203") / get("R204"))
    inductance = get("L201")
    c_out = 2 * A["mlcc_22u_25v_at_5v"]["value"]
    ripple_i = (vin - vout) / (FSW * inductance) * vout / vin
    ripple_v = ripple_i / (8 * FSW * c_out) + ripple_i * 0.0015
    r1, r2 = get("R201"), get("R202")
    start = (1.21 * (r1 + r2) - r1 * r2 * 0.7e-6) / r2
    stop = (1.17 * (r1 + r2) - r1 * r2 * 2.1e-6) / r2
    return {"vin_V": vin, "vout_V": vout, "inductor_ripple_pp_A": ripple_i, "output_ripple_pp_mV": ripple_v * 1e3,
            "soft_start_ms": get("C205") * 0.8 / 5.5e-6 * 1e3, "uvlo_start_V": start, "uvlo_stop_V": stop,
            "ccm_above_load_A": ripple_i / 2}


def ldo_netlist(v5, ripple_mv):
    return f""".include "{TI / 'TLV75533P_TRANS_ns.lib'}"
V5DC V5A 0 PWL(0 0 {6.8e-3} {v5})
VSW V5B V5A PULSE({-ripple_mv / 2000} {ripple_mv / 2000} 0 {0.5 / FSW} {0.5 / FSW} 1n {1 / FSW})
VLINE V5C V5B SIN(0 0.025 25k 12m)
VDIP V5 V5C PWL(0 0 9m 0 9.001m -0.15 9.2m 0)
C209 V5 0 {get('C209')}
X2 V5 0 V5 V3 NC TLV75533P_TRANS
C210 V3 0 1.8u
CDEC V3 CDECE 8u
RDECE CDECE 0 10m
R3LOAD V3 0 {3.3 / 0.06}
I3STEP V3 0 PULSE(0 0.05 10m 1u 1u 1m 1)
"""


def main():
    buck = {f"vin_{v}V": buck_equations(v) for v in (12.6, 9.3)}
    ripple = max(b["output_ripple_pp_mV"] for b in buck.values())
    r = spice.run("s4_ldo", ldo_netlist(buck["vin_12.6V"]["vout_V"], ripple), ["v(V3)", "v(V5)"],
                  "tran 20n 13m 0 20n", pspice=True, timeout=1200)
    t, v3, v5 = r["x"], r["v(V3)"], r["v(V5)"]

    def win(a, b, v=v3):
        return v[(t >= a) & (t < b)]

    steady = win(8.0e-3, 8.9e-3)
    ldo = {
        "v3_mean_V": float(np.mean(steady)), "v3_ripple_pp_mV": float(np.ptp(steady) * 1e3),
        "v3_startup_overshoot_mV": float((np.max(v3[t < 8e-3]) - np.mean(steady)) * 1e3),
        "v3_in_regulation_ms": float(t[np.where(v3 > 0.97 * 3.3)[0][0]] * 1e3),
        "v3_dip_on_5v0_dip_mV": float((np.mean(steady) - np.min(win(9.0e-3, 9.5e-3))) * 1e3),
        "v3_step_dip_mV": float((np.mean(steady) - np.min(win(10.0e-3, 11.0e-3))) * 1e3),
        "v3_ripple_with_25kHz_line_pp_mV": float(np.ptp(win(12.2e-3, 13e-3)) * 1e3),
        "v5_line_ripple_pp_mV": float(np.ptp(win(12.2e-3, 13e-3, v5)) * 1e3),
    }
    checks = {
        "v5_setpoint_within_2pct": abs(buck["vin_12.6V"]["vout_V"] - 5.0) < 0.1,
        "v5_switching_ripple_below_10mVpp": ripple < 10,
        "buck_uvlo_hysteresis_ge_0V5": buck["vin_12.6V"]["uvlo_start_V"] - buck["vin_12.6V"]["uvlo_stop_V"] >= 0.5,
        "v3_within_1p5pct": abs(ldo["v3_mean_V"] - 3.3) < 0.05,
        "v3_ripple_below_5mVpp": ldo["v3_ripple_pp_mV"] < 5 and ldo["v3_ripple_with_25kHz_line_pp_mV"] < 5,
        "v3_startup_overshoot_below_3pct": ldo["v3_startup_overshoot_mV"] < 100,
        "v3_step_dip_below_3pct": ldo["v3_step_dip_mV"] < 100 and ldo["v3_dip_on_5v0_dip_mV"] < 100,
    }
    common.save("s4_rails", {"buck_equations": buck, "ldo_simulation": ldo, "checks": checks,
                              "assumptions": {"5v0_line_ripple": "25 kHz, 50 mV p-p (ASSUMPTION)",
                                              "5v0_step_dip": "150 mV on the +96 mA buzzer step (ASSUMPTION)",
                                              "c_out": A["mlcc_22u_25v_at_5v"]}})
    fig, axes = common.figure(2, "S4: 5V0 source (soft start, 1.2 MHz ripple, dip at 9 ms, 25 kHz from 12 ms) and 3V3")
    axes[0].plot(t * 1e3, v5)
    axes[0].set_ylabel("5V0 (V)")
    axes[1].plot(t * 1e3, v3)
    axes[1].set_ylabel("3V3 (V)")
    axes[1].set_xlabel("time (ms)")
    axes[1].set_ylim(3.0, 3.45)
    common.finish(fig, "s4_rails")
    for k, v in buck.items():
        print(k, {a: round(b, 4) for a, b in v.items()})
    print("ldo", {a: round(b, 3) for a, b in ldo.items()})
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return checks


if __name__ == "__main__":
    sys.exit(0 if all(main().values()) else 1)
