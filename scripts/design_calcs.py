#!/usr/bin/env python3
"""Phase 1 design calculations: compute component values from datasheet equations.

Writes scripts/schgen/values.json (consumed by the schematic generator) and docs/design-calcs.md.
Every result carries its source. Resistor and capacitor picks are restricted to parts present in
bom/passives.json so each value maps to a stocked JLCPCB part.

Usage: python3 scripts/design_calcs.py
"""

import json
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PASSIVES = json.loads((ROOT / "bom" / "passives.json").read_text(encoding="utf-8"))


def ohms(text):
    scale = {"k": 1e3, "M": 1e6}
    return float(text[:-1]) * scale[text[-1]] if text[-1] in scale else float(text)


RESISTORS = sorted((ohms(k.split("_")[1]), k.split("_")[1]) for k in PASSIVES if k.startswith("R_") and k.endswith("0603"))


def nearest(value):
    return min(RESISTORS, key=lambda r: abs(math.log(r[0] / value)) if r[0] > 0 else 1e9)


rows, values = [], {}


def record(block, item, value, source):
    rows.append((block, item, value, source))


def buck():
    vfb, vin_min, vin_max, vout, fsw = 0.8, 8.5, 13.5, 5.0, 1.2e6
    rfbb = 10e3
    rfbt_ideal = (vout - vfb) / vfb * rfbb
    rfbt, rfbt_name = nearest(rfbt_ideal)
    vout_real = vfb * (1 + rfbt / rfbb)
    record("TPS62933F", "f_sw", "1.2 MHz (RT pin to GND)", "TPS62933 Table 7-1 / s9.3.5 (RT < 1 kOhm -> 1.2 MHz)")
    record("TPS62933F", "R_FBB / R_FBT", f"10k / {rfbt_name} -> V_OUT {vout_real:.3f} V "
           f"({0.784 * (1 + rfbt / rfbb):.2f}-{0.816 * (1 + rfbt / rfbb):.2f} V over V_FB tolerance)",
           "Eq. 1, R_FBB = 10 k recommended (s9.3.4); V_FB 784-816 mV (s8.5)")
    inductance = 4.7e-6
    ripple = {v: (v - vout) / (fsw * inductance) * vout / v for v in (9.0, 12.6)}
    record("TPS62933F", "L", f"4.7 uH Sunlord SWPA4030S4R7MT (I_sat 3.2 A, I_rms 2 A); ripple {ripple[9.0]:.2f} A at 9 V, "
           f"{ripple[12.6]:.2f} A at 12.6 V", "Eq. 16 range 2.1-6.2 uH; ripple >= 10 % of 3 A for slope "
           "compensation (s10.2.2.7); peak at 0.3 A load ~0.6 A << I_sat; below I_HS_LIMIT 5.8 A only in a hard short")
    record("TPS62933F", "C_OUT", "2 x 22 uF 25 V 0805 X5R (~22 uF effective at 5 V) + 100 nF",
           "Table 10-2: 20 uF typ effective at 1.2 MHz / 5 V")
    record("TPS62933F", "C_IN", "2 x 10 uF 25 V 0805 + 100 nF 50 V at the VIN pin", "s10.2.2.9, s11 layout")
    record("TPS62933F", "C_BST", "100 nF 16 V X7R", "s10.2.2.5")
    tss = 47e-9 * 0.8 / 5.5e-6
    record("TPS62933F", "C_SS", f"47 nF -> t_SS = {tss * 1e3:.1f} ms (>= 6.8 nF minimum)", "Eq. 6, I_SS 5.5 uA")
    ven_rise, ven_fall, ip, ih = 1.21, 1.17, 0.7e-6, 1.4e-6
    start_target, stop_target = 9.2, 8.5
    r1_ideal = (start_target * ven_fall / ven_rise - stop_target) / (ip * (1 - ven_fall / ven_rise) + ih)
    r2_ideal = r1_ideal * ven_fall / (stop_target - ven_fall + r1_ideal * (ip + ih))
    best = None
    for r1, n1 in RESISTORS:
        for r2, n2 in RESISTORS:
            if not (100e3 <= r1 <= 1e6 and 10e3 <= r2 <= 200e3):
                continue
            start = (ven_rise * (r1 + r2) - r1 * r2 * ip) / r2
            stop = (ven_fall * (r1 + r2) - r1 * r2 * (ip + ih)) / r2
            score = abs(start - start_target) + abs(stop - stop_target)
            if start - stop >= 0.5 and (best is None or score < best[0]):
                best = (score, n1, n2, start, stop, r1, r2)
    _, n1, n2, start, stop, r1, r2 = best
    ven_max = (vin_max * r2 + r1 * r2 * (ip + ih)) / (r1 + r2)
    record("TPS62933F", "EN UVLO divider", f"R1 {n1} / R2 {n2}: start {start:.2f} V, stop {stop:.2f} V, "
           f"V_EN at {vin_max} V = {ven_max:.2f} V (< 5.5 V)",
           f"Eq. 3-5 (ideal R1 {r1_ideal / 1e3:.0f}k, R2 {r2_ideal / 1e3:.1f}k); stop at ~2.8 V/cell protects the "
           "LiPo, hysteresis >= 0.5 V (s9.3.6)")
    values["buck"] = {"rfbt": rfbt_name, "rfbb": "10k", "en_r1": n1, "en_r2": n2}


def ldo():
    record("TLV75533P", "C_IN / C_OUT", "1 uF 50 V X5R / 2.2 uF 25 V X5R (>= 0.47 uF effective)",
           "SBVS320A s6.3, s8.1.1")
    drop = (5.0 - 3.3) * 0.115
    record("TLV75533P", "dissipation", f"{drop:.2f} W at 115 mA -> +{drop * 231.1:.0f} C (R_thJA 231 C/W)",
           "s6.4; load from docs/architecture.md")


def lse():
    cl, stray = 6.0, 2.5
    each = 2 * (cl - stray)
    record("LSE", "load caps", f"2 x 6.8 pF C0G (computed {each:.1f} pF for C_L 6 pF, stray {stray} pF)",
           "AN2867 C_L formula (mcu-circuit-design s4); ST characterises LSE with 2 x 6.8 pF (DS11929 Table 41 n3)")
    record("LSE", "drive", "LSEDRV = 10 (firmware): g_m,crit ~0.67 uA/V vs 1.70 uA/V -> margin ~2.5",
           "DS11929 Table 54; NX3215SA C0 1.5 pF max, ESR 70 kOhm")
    values["lse_cap"] = {"key": "6.8p_0402_50V_C0G", "source": "LSE load: AN2867, DS11929 Table 41 note 3"}
    record("HSE", "crystal", "NX2016SA-32MHZ-EXS00A-CS06654, no external caps (HSETUNE)",
           "DS11929 Table 5 note 1 reference part; Table 52 C_L 6-8 pF, ESR <= 100 Ohm")


def vbat_divider():
    r1, r2 = 100e3, 27e3
    ratio = r2 / (r1 + r2)
    thevenin = r1 * r2 / (r1 + r2)
    worst = r1 / (r1 + r2) * 0.02
    record("VBAT sense", "divider", f"100k / 27k: ratio {ratio:.4f}, 12.6 V -> {12.6 * ratio:.3f} V, "
           f"13.5 V -> {13.5 * ratio:.2f} V", "headroom below VDDA 3.3 V")
    record("VBAT sense", "source impedance", f"{thevenin / 1e3:.1f} kOhm (< 50 kOhm R_AIN max), "
           "100 nF bucket >> 20 x 5 pF C_ADC, tau 2.1 ms", "DS11929 Table 73; analog-circuit-design s6")
    record("VBAT sense", "ratio error", f"+/-{worst * 100:.2f} % worst case with 1 % parts "
           f"(+/-{12.6 * worst / 3 * 1000:.0f} mV per cell); calibrate per board + VREFINT", "sensitivity of R2/(R1+R2)")


def power_path():
    r_pullup, r_switch, c_miller, c_gs = 100e3, 100e3, 47e-9, 1e-6
    for vbat in (9.0, 13.5):
        vgs = vbat * r_pullup / (r_pullup + r_switch)
        record("Power path", f"V_GS at {vbat} V", f"-{vgs:.1f} V (AO4805 R_DS(on) <= 26 mOhm at -4.5 V; limit +/-20 V; "
               "BZT52C15 clamps transients)", "100k gate-source / 100k to GND through the switch (S1)")
    plateau = 2.3
    i_gate = (12.6 - plateau) / r_switch - plateau / r_pullup
    slew = i_gate / c_miller
    c_load = 220e-6 + 6 * 10e-6
    record("Power path", "soft start", f"47 nF + 1k gate-to-VBAT (Miller): I_G ~{i_gate * 1e3:.2f} mA -> ~{slew / 1e3:.1f} V/ms, "
           f"inrush ~{c_load * slew:.2f} A for ~{12.6 / slew * 1e3:.0f} ms",
           "S1: 0.54 A peak, 6.8 ms 10-90 % rise (was 44.6 A on hot plug with the Phase 1 values)")
    record("Power path", "hot plug, switch off", f"1 uF gate-source cap: V_GS step = -12.6 x 47n/(47n+1u) = "
           f"{-12.6 * c_miller / (c_miller + c_gs):.2f} V (< |V_th,min| 1.0 V), FET stays off",
           "S1: VBAT stays at 0.002 V (was 10.5 V with the Phase 1 values)")
    record("Power path", "turn-off", f"tau = 100k x (1 uF + 47 nF) = {r_pullup * (c_gs + c_miller) * 1e3:.0f} ms; "
           "don't switch off while the motors are driven", "S1 regen cases: FET energy <= 7 mJ")
    record("Power path", "TVS", "SMBJ15A after the FETs: V_RWM 15 V > 13.5 V, V_C 24.4 V < 30 V (AO4805), 32 V (TPS62933)",
           "Littelfuse SMBJ p.2; must not sit before the reverse-polarity FETs")


def drive():
    record("DRV8711", "VM", "10 nF 50 V + 220 uF 35 V bulk; per bridge 10 uF 25 V 0805 + 100 nF 50 V at the half-bridges",
           "SLVSC40 Critical Components p.4; power-pcb-layout s3.1 hot loop")
    record("DRV8711", "VCP / CP1-CP2", "1 uF 50 V X5R VCP-to-VM / 100 nF 50 V X7R (>= VM + 12 V = 25.5 V)",
           "SLVSC40 p.3-4")
    record("DRV8711", "V5 / VINT / BEMF", "100 nF / 1 uF / 1 nF C0G to GND", "SLVSC40 p.3-4")
    record("DRV8711", "pull-ups", "nFAULT, nSTALL 10k; SDATO (open-drain, shared MISO) 2.2k -> tau ~66 ns with 30 pF",
           "SLVSC40 p.3; SPI <= 4 MHz (p.8)")
    record("DRV8711", "SLEEPn", "10k pull-down: no internal pull, keeps the driver asleep while the MCU is in reset",
           "SLVSC40 p.3; AINx/BINx/RESET/SCS have internal pull-downs")
    record("DRV8711", "low-side clamps", "SS34 Schottky from GND to each phase node: freewheel at -0.36 V instead of the "
           "-0.73 V body diode", "S2; DRV8711 phase pins abs max -0.6 V (SLVSC40 Abs Max)")
    record("DRV8711", "Rsense", "50 mOhm 1206 1 W 75 ppm/C; 2.0 A trip -> 0.2 W; ISGAIN 20, TORQUE 186",
           "D-027; S0 (simulation/REPORT.md); Eq. 1 p.11")
    record("DRV8711", "ISENSE filter", "0 Ohm fitted in each leg, 1 nF DNP across (fit 27-33 Ohm + 1 nF if noisy: RC 50-60 ns)",
           "SLVSC40 p.16 Fig. 6 (symmetric, <= 500 Ohm, matched 1 %)")
    record("DRV8711", "firmware", "IDRIVE 00 (50/100 mA, default); TBLANK >= 1.2 us (sense amp settling); "
           "SCLK <= 4 MHz; SCS active-high GPIO",
           "SLVSC40 p.7-8")


def interfaces():
    fc = 1 / (2 * math.pi * 100 * 1e-9)
    record("Encoders", "input RC", f"100 Ohm + 1 nF -> f_c {fc / 1e6:.2f} MHz (> 2 x 105 kHz max channel rate), "
           "rise 220 ns", "S0 encoder rate; analog-circuit-design s5")
    record("Encoders", "OC pull-ups (DNP)", "2.2k to encoder VCC: OK to ~500 lines at full speed; for 1000-line OC "
           "encoders fit 1k and reduce C to 220 pF", "tau = R x (1 nF + cable)")
    record("Encoders", "buffer", "SN74LVC3G17 at 3V3: V_T+ <= 1.87 V, inputs 5.5 V tolerant with I_off",
           "SCES470D p.3-4")
    r_max = 300e-9 / (0.8473 * 100e-12)
    r_min = (3.3 - 0.4) / 3e-3
    record("Qwiic I2C", "pull-ups", f"2.2k (window {r_min:.0f}-{r_max:.0f} Ohm, Fast mode, C_b 100 pF)", "SLVA689A")
    record("LEDs", "series R", "red 680 Ohm (V_F 1.88 V at 2 mA), green 470 Ohm (V_F 2.45 V at 2 mA)",
           "KT-0603R/G IF-VF curve p.5")
    record("Buzzer", "drive", "+5V -> 33 Ohm -> MLT-8530 (16 Ohm) -> MMBT3904; peak ~96 mA (rated 95 mA max); "
           "470 Ohm base, 1N4148WS across the coil", "MLT-8530 p.3 recommended driver")
    record("Button", "debounce", "10k pull-up, 100 Ohm series, 100 nF at the MCU (tau 1 ms)", "mcu-circuit-design s11")


def main():
    buck()
    ldo()
    lse()
    vbat_divider()
    power_path()
    drive()
    interfaces()
    values["vdda_ferrite"] = {"lcsc": "C80165"}
    values["tact_footprint"] = "e-inverted-pendulum:SW_Push_TS-1187A_5.1x5.1mm"
    values["stdc14_footprint"] = "Connector_PinHeader_1.27mm:PinHeader_2x07_P1.27mm_Vertical_SMD"
    (ROOT / "scripts" / "schgen" / "values.json").write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    lines = ["# Design calculations (Phase 1)", "",
             "Generated by `python3 scripts/design_calcs.py`. Values feed `scripts/schgen/values.json` and the schematic "
             "generator; do not edit by hand.", "", "| Block | Item | Value | Source |", "|---|---|---|---|"]
    lines += [f"| {b} | {i} | {v} | {s} |" for b, i, v, s in rows]
    (ROOT / "docs" / "design-calcs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for b, i, v, _ in rows:
        print(f"{b:12} {i:22} {v}")


if __name__ == "__main__":
    main()
