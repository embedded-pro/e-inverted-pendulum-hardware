# Simulation report

Reproduce everything: `python3 simulation/fetch_models.py` (TI models, not committed) then
`python3 simulation/run_all.py`. Per-step results are in `results/*.json` and plots in `plots/`.
Values are read from `kicad/*.kicad_sch` (`kicad_values.py`); the Phase 1 values are kept as explicit
comparison variants so the before/after numbers stay reproducible.

## Phase 2 summary

| Step | Question | Result | Change made |
|---|---|---|---|
| S1 | Power entry: inrush, hot plug, reverse battery, regeneration | **2 failures found and fixed** | R102 10k→100k, C101 220n→47n, new C102 1 µF gate-source |
| S2 | H-bridge switching, phase-node limits, FET losses | **1 abs-max violation found and fixed** | SS34 clamps D501–D504; firmware IDRIVE 00 |
| S3 | Motor bus ripple, battery sag, UVLO margins | pass | firmware undervoltage disarm |
| S4 | 5V0 / 3V3 rails | pass (buck by equations: TI model won't run in ngspice) | — (bench item: buck load step) |
| S5 | VBAT ADC accuracy, encoder edges | pass with conditions | firmware per-board calibration; OC encoders ≤ 500 lines |

Device models: `models/devices.lib` (ours, from datasheets; cross-checked: CSD88537ND R_DS(on) 12.5 mΩ at
10 V vs 12.5 typ; AO4805 15.0 mΩ at −10 V vs ~15 typ, 25.6 mΩ at −4.5 V vs ≤ 26 max). TI models for S4 are
fetched by `fetch_models.py` (TI copyright, no redistribution grant). Assumptions are listed in `common.py`
(battery 60/150 mΩ, MLCC DC-bias derating, motor R/L, logic load 1.56 W).

## S0: motor, gear and current-limit sizing

**Scope.**
- **Model.** The firmware's planar pendulum model (`pendulum-dynamics.md`), plus:
  - rotor inertia reflected through the gearbox;
  - a voltage-driven brushed DC motor with coulomb gearbox friction;
  - DRV8711 current clipping at I_trip;
  - a discrete 500 Hz LQR with a one-sample delay (REQ-RT-001, REQ-RT-004).
- **Ideal:** inductance (τ_e ≪ τ), backlash, wheel slip, sensor noise.
- **Sweep, 160 cases:**
  - 2 motor windings;
  - 5 gear ratios;
  - gear efficiency 0.35 / 0.45;
  - I_trip = rated or stall current;
  - VBAT 12.6 / 11.1 / 9.9 V.

**Inputs and their sources.**
- Motor data comes from JGA25-370 seller listings: the 6000 rpm winding (1:21.3 → 280 rpm, 1:35 → 170 rpm, stall 1.3 A at 12 V) and the 4300 rpm JGA25-371 encoder variant (1:34 → 126 rpm, stall 1.0 A).
- Gear efficiency is derived from the listed stall torques.
- Rotor inertia (1.5e-6 kg·m²) and inductance (1–3 mH) are **ASSUMPTIONS**; measure them at bring-up.
- Body parameters come from `mechanical/mass_budget.csv`.

**Hand cross-checks.**
- τ = √((J + mℓ²)/(m·g·ℓ)) = √(1.76e-3 / 0.170) = 101.7 ms; the script prints 102 ms.
- Duty at 1.0 m/s, 1:9.6, 9.9 V = (0.01833·282 + 9.2·0.06)/9.9 = 0.58; the script prints 0.58.
- TORQUE = 256·40·0.05·1.3/2.75 = 242; the script prints 242.

### Findings

1. **Gear ratio: 1:9.6 (about 620 rpm output at 12 V) on the 6000 rpm winding.**
   - It recovers from 10° within 1 s at every corner and recovers from up to 29.4° worst case.
   - Cruising at 1.0 m/s needs 58 % duty at 9.9 V, leaving headroom to balance.
   - Ratios of 1:20.4 and above can't reach the firmware's 1.0 m/s command limit at all: duty would exceed 100 % at 9.9 V.
   - Fallback if only the 4300 rpm winding is available: 1:4.4 (27.7° recoverable, 39 % duty).
2. **REQ-DRIVE-005 as written makes the robot fail.**
   - With the hardware trip set to the motor's continuous rating (0.35–0.45 A), it can't recover 10° at 1:20.4 and above, and only recovers about 11° at 1:9.6.
   - Recommendation for the firmware: set the DRV8711 trip at about stall (1.3 A), a peak and protective limit, and enforce the continuous rating in firmware with an I²t / RMS thermal model.
3. **DRV8711 setting for Rsense = 50 mΩ** (the firmware default, kept): I_trip 1.30 A → ISGAIN 40, TORQUE 242, about 5 mA resolution. Rsense dissipates 85 mW, so a 1206 part is enough; the 2512 in the plan is oversized.
4. **PWM ripple** at 25 kHz, D = 0.5, 12.6 V: 63–84 mA p-p for L = 2.0–1.5 mH, under 7 % of I_trip (REQ-DRIVE-007 satisfied). Recheck after measuring L.
5. **Encoder channel frequency** at maximum motor speed (105 rev/s at 12.6 V):
   - 10.5 kHz (100 lines), 52.5 kHz (500 lines) or 105 kHz (1000 lines) per channel;
   - ×4 for the count rate.
   - The input RC corner and buffer must pass ≥ 2× this (S5).
   - If LPTIM1 is clocked from a low-frequency source, it can't count this fast; the firmware must clock it from PCLK or HSI16.
6. **Reflected rotor inertia matters.** At 1:9.6 it is equivalent to 0.24 kg on the axle, against a 0.42 kg body. The firmware's pendulum model (and its LQR) should include it.
7. **Fall time constant τ = 102 ms** (the firmware doc's example is 130 ms). A 500 Hz loop gives about 50 updates per τ, which is still comfortable.

### Proposed changes

| Item | As planned | Proposed | Why |
|---|---|---|---|
| Motor | JGA25-370 class, ratio open | JGA25-370, 12 V, 6000 rpm winding, **1:9.6 (~620 rpm)**, ABZ encoder | Finding 1 |
| Rsense | 50 mΩ 2512 | 50 mΩ **1206**, 1 %, ≥ 0.25 W | Finding 3 |
| I_trip (firmware) | "≤ continuous rating" | 1.3 A hardware trip + firmware I²t | Finding 2 |

### Firmware constraints from S0

- `Drv8711DriverConfiguration`: Rsense 0.05 Ω, I_trip 1.3 A → ISGAIN 40, TORQUE 242.
- Pitch setpoint offset of about 7° (static lean; `docs/mechanical.md`).
- Gear ratio 9.6. The encoder CPR at the wheel is 4 × lines × 9.6.
- LPTIM1 kernel clock fast enough for the encoder rate (finding 5).
- Add reflected inertia to the plant model; fix the J definition (`docs/mechanical.md`).

### Model limits

Not simulated: gearbox backlash (common on these gearboxes and harmful at small angles), wheel slip, sensor noise and estimator lag, motor inductance, battery sag (S1/S3 cover that). The motor constants come from seller listings. **Measure the purchased motor** (stall current at 12 V, no-load speed and current, L, spin-down inertia) and rerun.


## S1: power entry (`power_entry.py`)

**Scope.** Battery = EMF + R_int (60 / 150 mΩ) + 150 nH leads → fuse (35 mΩ) → AO4805 back-to-back pair with
its gate network → VBAT bulk (220 µF electrolytic with ESR/ESL, MLCCs derated for DC bias) → SMBJ15A; the
buck is a 1.56 W constant-power load above its 9.1 V UVLO; motors are R + L + back-EMF behind body diodes.

### Findings

1. **Hot plug with the switch ON gave a 44.6 A inrush spike** (Phase 1 values), above the AO4805's 40 A
   pulsed rating. The Miller soft-start only works when the gate starts at the source potential; on hot
   plug the FET1 body diode lifts the source to 12.6 V while C101 holds the gate at the still-empty VBAT.
2. **Hot plug with the switch OFF turned the FET on anyway**: VBAT jumped to 10.5 V (43 A peak), briefly
   powering the logic. Same coupling path.
3. **Fix (now in the schematic):** R102 10k → 100k, C101 220 nF → 47 nF, new C102 1 µF gate-source. On hot
   plug the capacitive divider holds V_GS at −0.545 V (hand: −12.6 × 47n/1047n = −0.57 V), below |V_th,min|.

| Case | Phase 1 values | Current schematic |
|---|---|---|
| Switch-on inrush (new / aged pack) | 1.24 / 1.22 A | **0.54 / 0.54 A** |
| Switch-on 10–90 % rise | 2.2 ms | 6.8 ms (hand: 0.08 mA / 47 nF ≈ 1.7 V/ms → ~7 ms) |
| Hot plug, switch on: peak current | **44.6 A** | **0.54 A** |
| Hot plug, switch off: VBAT peak | **10.5 V** | **0.002 V** |
| On-state V_GS at 12.6 V | −11.4 V | −5.5 V (R_DS(on) ≈ 20 mΩ) |
| Reverse battery (switch on / off): load current, V_GS | 0, ≤ 0.69 V | 0, ≈ 0 V |
| Switch-off with both motors stalled at 1.37 A | VBAT 12.66 V | VBAT 12.65 V; FET energy 2.1 mJ |
| Switch-off while pushed at 20 V back-EMF (above no-load speed) | VBAT 17.75 V | VBAT 17.75 V (TVS onset); FET 7 mJ |

Hand cross-check for the pushed case: 2 × (20 − 12.6 − 1.6) / 9.2 ≈ 1.26 A into the battery; simulated 1.15 A.
Regeneration needs the wheels above the motors' no-load speed (≈ 2.3 m/s at 12.6 V), outside the 1.5 m/s
design limit, and even then the TVS keeps VBAT < 24 V.

**Constraint:** turn-off is now slow (τ = 100k × 1.05 µF ≈ 105 ms); don't switch off while the motors are driven.

## S2: H-bridge switching (`bridge.py`)

**Scope.** One full bridge at transistor level (4 × CSD88537ND VDMOS), slow decay at 25 kHz centre-aligned,
850 ns dead time, DRV8711 gate drive as 10 V through R = 10 V / mean(IDRIVE source, sink); hot-loop
inductance 5 / 15 nH; stall at duty 0.5 / 0.9 and running at duty 0.9 with 9 V back-EMF.
Hand cross-checks: ripple at D 0.5 = V·T/(4L) = 84 mA (sim 83 mA); stall current at D 0.5 ≈ 0.67 A
(sim 0.62 A, dead time included).

### Findings

1. **The DRV8711 phase-pin absolute minimum (−0.6 V, SLVSC40 Abs Max) was violated for ~3 µs every PWM
   period**: during each dead time the motor current freewheels through the low-side body diode, holding
   the phase node at −0.73 V.
2. **Fix (now in the schematic):** SS34 Schottky (D501–D504, JLC basic C8678) from GND to each phase node.
   The freewheel plateau becomes **−0.36 V**; what remains is a 3 ns ringing spike to −0.67 V with a 5 nH
   hot loop (12 ns to −1.07 V at 15 nH) → **layout target: hot loop ≤ 5 nH** (Phase 3).
3. **Gate drive strength:** IDRIVE 00 (50/100 mA, the default) keeps switch-node overshoot ≤ 0.2 V; IDRIVE 11
   (200/400 mA) rings to +2.7…+5.5 V and puts 21.8 V on the low-side FET. **Firmware: keep IDRIVE at 00.**
4. **Losses are negligible:** ≤ 30 mW per FET package (Tj ≈ 42 °C at 40 °C ambient); no shoot-through in any
   case. The 60 V FETs are heavily oversized, which is fine.

## S3: motor bus (`bus.py`)

**Scope.** Both bridges reduced to their bus current (I_motor × square(duty), in phase on one timer),
battery 60 / 150 mΩ, the VBAT capacitor set, 1.56 W logic load.

| Case | Result | Limit |
|---|---|---|
| Electrolytic C507 ripple, both motors at 1.3 A, D 0.5 (braking transient) | 0.570 A rms | 0.57 A (600 mA × 0.95 at 25 kHz) |
| C507 ripple at the continuous current (0.45 A each, D 0.5) | **0.197 A rms** | 0.57 A |
| VBAT ripple p-p (1.3 A / 0.45 A) | 211 / 73 mV | — |
| Sag, aged pack at 9.9 V OCV, 2.6 A step | 9.28 V (hand 9.28 V) | logic UVLO stop 8.47 V |
| Sag, aged pack at 9.0 V OCV, 2.6 A step | 8.41 V (hand 8.38 V) | below 8.47 V: logic cuts off (intended) |

**Constraints for firmware:** enforce the continuous current with the I²t model (the bulk capacitor is sized
for it, not for sustained 1.3 A at D 0.5); raise an undervoltage fault and disarm below ~9.5 V under load so
the hardware cut-off at 8.47 V is never reached while balancing.

## S4: logic rails (`rails.py`)

**Model limit, stated first.** TI's only unencrypted buck model (TPS62933P, SLUM818) does not run in
ngspice-42: the time step collapses after ~10 µs whatever the integration method, shunt resistance or
STEADY_STATE setting. The board's TPS62933F has no unencrypted model at all. So the **buck is covered by the
datasheet design equations** (SLUSEA4 s10.2.2), and its load-step and loop behaviour is a **bench item**.
The **LDO is simulated with TI's TLV75533P transient model** (SBVM831), fed from a 5V0 that carries the buck's
switching ripple, an assumed 50 mV p-p of the 25 kHz motor-bus ripple and an assumed 150 mV dip on the
buzzer step.

| Item | Result | Target |
|---|---|---|
| 5V0 set point (R203/R204) | 4.984 V (4.88–5.08 V over V_FB tolerance) | ±2 % |
| Inductor ripple at 12.6 / 9.3 V | 0.53 / 0.41 A p-p (CCM above 0.27 A) | ≥ 10 % of 3 A (slope compensation) |
| 5V0 switching ripple (2 × 22 µF derated to 13 µF) | 2.9 mV p-p | < 10 mV |
| Soft start (C205 47 nF) | 6.8 ms | ≥ 1 ms |
| UVLO start / stop (R201/R202) | 9.11 / 8.47 V | hysteresis ≥ 0.5 V |
| 3V3 regulation at 60 mA | 3.312 V | ±1.5 % |
| 3V3 start-up overshoot | 0.3 mV, in regulation 4.6 ms after the 5V0 ramp starts | < 3 % |
| 3V3 dip: +50 mA step / 150 mV dip on 5V0 | 6.1 / 1.6 mV | < 100 mV |
| 3V3 ripple: switching / with 25 kHz line ripple | < 0.01 / 0.6 mV p-p | < 5 mV (AN5165 VDDRF window 5–15 mV) |

**Bench items:** 5V0 response to the buzzer step and to motor-bus transients (expected well under the assumed
150 mV); 5V0 ripple with the real inductor and layout; radio sensitivity with the STM32WB SMPS on and off
(rf-layout s5).


| Item | Result | Target |
|---|---|---|
| ADC charge-sharing error, VBAT sampled at 100 Hz / 1 kHz | −0.19 / −0.46 LSB | < 0.5 LSB |
| VBAT error, 3σ per cell, raw (1 % resistors, VDDA ±1.5 %, TUE 5 LSB) | 109 mV | 50 mV |
| … ratiometric with VREFINT | 75 mV | 50 mV |
| … with per-board calibration (one point at room temperature) | **38 mV** | 50 mV |
| Encoder push-pull, 1000 lines at max speed: worst edge skew | 212 ns = 8.9 % of a quarter period | < 25 % |
| Encoder open collector (2.2k fitted), 500 / 1000 lines | 21 % / **43 %** | < 25 % |

Hand cross-checks: charge sharing 2.68 V × 9.7 pF / 100 nF = 0.26 mV ≈ 0.32 LSB per isolated sample; open-collector
rise τ = 2.2k × 1.1 nF ≈ 2.4 µs → 1.5–1.87 V crossing at 0.86–1.12 µs (sim 0.91–1.19 µs).

**Constraints:** sample VBAT at ≤ 100 Hz; calibrate the VBAT channel per board at bring-up (store in flash);
open-collector encoders above 500 lines need the 1k pull-up / 220 pF option (D-016 default is push-pull).

## Changes made to the schematic in Phase 2

| Ref | Phase 1 | Now | Why |
|---|---|---|---|
| R102 | 10 k | 100 k | Miller current 0.08 mA → 1.7 V/ms soft start (S1) |
| C101 | 220 nF | 47 nF | same; smaller coupling on hot plug (S1) |
| C102 (new) | — | 1 µF X5R 50 V, gate–source | holds V_GS at −0.55 V on hot plug: FET stays off, no 44 A spike (S1) |
| D501–D504 (new) | — | SS34 (C8678), GND → each phase node | freewheel at −0.36 V instead of −0.73 V; DRV8711 phase pins ≥ −0.6 V (S2) |

References shifted on sheet 1: the ADC charge bucket is now C103. All checks (ERC, netlist, library, stock)
were rerun after the change.

## Constraints for firmware (collected)

- DRV8711: IDRIVEP/IDRIVEN = 00 (S2); TBLANK ≥ 1.2 µs; trip 1.3 A with an I²t model for the continuous rating (S0, S3).
- Undervoltage fault and disarm below ~9.5 V under load; never rely on the 8.47 V hardware cut-off (S3).
- VBAT sampled at ≤ 100 Hz, ratio 0.2126, per-board calibration stored in flash (S5).
- Power switch: turn-off takes ~100 ms; stop the motors before switching off (S1).

## Limits of the models

- Battery, lead inductance, MLCC derating, motor R/L and rotor inertia are assumptions (`common.py`, S0); measure them.
- Bridge gate drive is a resistive approximation of the DRV8711's current-source drive; hot-loop inductance is
  a corner (5 / 15 nH), not extracted from a layout. Re-run S2 with extracted parasitics after Phase 3.
- No DRV8711 current chopping in S2 (stall at duty ≤ 0.9 stays below the trip); chopping is a bench check.
- Buck dynamics not simulated (see S4). LDO HF rejection depends on TI's model and the assumed output capacitance.
- Encoder cable is lumped (1 m); no EMI or ESD simulation.
