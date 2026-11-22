#!/usr/bin/env python3
"""S5: VBAT measurement (ADC sampling + Monte Carlo accuracy) and encoder input edge timing.

Sources: DS11929 Rev 11 Table 73 (C_ADC 5 pF, R_AIN max), Table 79 (TUE 5 LSB, offset 2.5, gain 4.5 LSB),
VREFINT spread 7.5 mV over temperature; TLV755P accuracy +/-1.5 %; SN74LVC3G17 V_T+ 1.5-1.87 V,
V_T- 0.84-1.14 V at 3 V (SCES470D p.4); TPD4E05U06-Q1 0.5 pF (SLVSCO7A s7.5); design values from the schematic.
Ideal: ADC switch 1 kOhm; encoder cable lumped (0.5 uH, 100 pF per metre); encoder driver 50 Ohm (push-pull)
or a 10 Ohm open-collector transistor with the DNP 2.2k pull-up fitted.
"""

import sys

import numpy as np

import common
import spice
from kicad_values import get

LSB = 3.3 / 4096
SEED = 20261104


def adc_sampling(rate_hz):
    period = 1.0 / rate_hz
    ts = 247.5 / 32e6
    net = f"""
VB VBAT 0 12.6
R104 VBAT VS {get('R104')}
R105 VS 0 {get('R105')}
C103 VS 0 {get('C103')}
CPIN VS 0 4.7p
SSAMP VS VC SMP 0 SW1
SRST VC 0 RST 0 SW1
CADC VC 0 5p
VSMP SMP 0 PULSE(0 1 {period - ts} 1n 1n {ts} {period})
VRST RST 0 PULSE(0 1 {period - ts - 2e-6} 1n 1n 1e-6 {period})
.model SW1 SW (Ron=1k Roff=1e12 Vt=0.5 Vh=0.05)
"""
    r = spice.run(f"s5_adc_{rate_hz}", net, ["v(VS)", "v(VC)", "v(SMP)"], f"tran {ts / 20} {20 * period} {10 * period} {ts / 20}")
    ideal = 12.6 * get("R105") / (get("R104") + get("R105"))
    sampled = r["v(VC)"][np.where(np.diff((r["v(SMP)"] > 0.5).astype(int)) == -1)[0]]
    return {"ideal_V": ideal, "sampled_V": float(np.mean(sampled)), "error_LSB": float((np.mean(sampled) - ideal) / LSB)}


def monte_carlo(trials=20000):
    rng = np.random.default_rng(SEED)
    r1n, r2n = get("R104"), get("R105")
    pack = 9.9
    tcr_dt = 100e-6 * 20.0

    def measure(r1, r2, vdda_err, tue_lsb):
        v = pack * r2 / (r1 + r2)
        code = v / (3.3 * (1 + vdda_err)) * 4096 + tue_lsb
        return code * 3.3 / 4096 * (r1n + r2n) / r2n

    r1 = r1n * (1 + rng.uniform(-0.01, 0.01, trials))
    r2 = r2n * (1 + rng.uniform(-0.01, 0.01, trials))
    drift1 = 1 + rng.uniform(-tcr_dt, tcr_dt, trials)
    drift2 = 1 + rng.uniform(-tcr_dt, tcr_dt, trials)
    tue = rng.uniform(-5, 5, trials)
    raw = measure(r1 * drift1, r2 * drift2, rng.uniform(-0.015, 0.015, trials), tue)
    vrefint = measure(r1 * drift1, r2 * drift2, rng.uniform(-0.0075 / 1.212, 0.0075 / 1.212, trials), tue)
    calibrated = measure(r1n * drift1, r2n * drift2, rng.uniform(-0.0075 / 1.212, 0.0075 / 1.212, trials),
                         rng.uniform(-2.5, 2.5, trials))
    out = {}
    for name, values in (("raw", raw), ("vrefint", vrefint), ("per_board_calibrated", calibrated)):
        per_cell = (values - pack) / 3 * 1e3
        out[name] = {"sigma_mV_per_cell": float(np.std(per_cell)), "three_sigma_mV_per_cell": float(3 * np.std(per_cell)),
                     "worst_mV_per_cell": float(np.max(np.abs(per_cell)))}
    return out


def encoder(kind, freq):
    half = 0.5 / freq
    if kind == "push_pull":
        source = f"VSRC SRC 0 PULSE(0 5 1u 20n 20n {half - 20e-9} {1 / freq})\nRSRC SRC CBL 50\n"
    else:
        source = (f"VCTL CTL 0 PULSE(1 0 1u 20n 20n {half - 20e-9} {1 / freq})\nSOC CBL 0 CTL 0 SWOC\n"
                  ".model SWOC SW (Ron=10 Roff=1e9 Vt=0.5 Vh=0.05)\nRPU CBL VCC 2.2k\nVCC VCC 0 5\n")
    net = source + f"""
LCBL CBL CON 0.5u
CCBL CON 0 100p
CTVS CON 0 0.5p
R604 CON F {get('R604')}
C604 F 0 {get('C604')}
CIN F 0 4p
"""
    r = spice.run(f"s5_enc_{kind}_{int(freq / 1e3)}k", net, ["v(F)"], f"tran 2n {1e-6 + 4 / freq} 0 2n")
    t, v = r["x"], r["v(F)"]
    period = 1 / freq

    def crossing(level, rising, start):
        idx = np.where((t > start) & ((v >= level) if rising else (v <= level)))[0]
        return t[idx[0]] - start if len(idx) else np.inf

    edge_rise, edge_fall = 1e-6 + 2 * period, 1e-6 + 2 * period + half
    rise = [crossing(x, True, edge_rise) for x in (1.5, 1.87)]
    fall = [crossing(x, False, edge_fall) for x in (1.14, 0.84)]
    delays = rise + fall
    spread = max(delays) - min(delays)
    return {"rise_delay_ns": [float(d * 1e9) for d in rise], "fall_delay_ns": [float(d * 1e9) for d in fall],
            "worst_edge_skew_ns": float(spread * 1e9), "quarter_period_ns": period / 4 * 1e9,
            "phase_error_pct_of_quarter": float(spread / (period / 4) * 100)}


def main():
    results = {"adc_1kHz": adc_sampling(1000), "adc_100Hz": adc_sampling(100), "monte_carlo": monte_carlo()}
    for kind in ("push_pull", "open_collector"):
        for lines, freq in ((500, 52.5e3), (1000, 105e3)):
            results[f"encoder_{kind}_{lines}_lines"] = encoder(kind, freq)
    mc = results["monte_carlo"]
    checks = {
        "adc_sampling_error_below_half_lsb_at_100Hz": abs(results["adc_100Hz"]["error_LSB"]) < 0.5,
        "vbat_3sigma_below_50mV_per_cell_with_calibration": mc["per_board_calibrated"]["three_sigma_mV_per_cell"] < 50,
        "encoder_push_pull_1000_lines_phase_error_below_25pct": results["encoder_push_pull_1000_lines"]["phase_error_pct_of_quarter"] < 25,
        "encoder_open_collector_500_lines_phase_error_below_25pct": results["encoder_open_collector_500_lines"]["phase_error_pct_of_quarter"] < 25,
    }
    common.save("s5_analog", {"results": results, "checks": checks, "seed": SEED})
    for k, v in results.items():
        print(k, {a: (round(b, 3) if isinstance(b, float) else b) for a, b in v.items()} if k != "monte_carlo" else v)
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    return checks


if __name__ == "__main__":
    sys.exit(0 if all(main().values()) else 1)
