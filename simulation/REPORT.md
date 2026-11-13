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

## S0: motor, voltage cap and current trip (`sizing.py`)

Re-run 2026-11-13 for the hardware the owner supplied (D-026, D-027): **MG310 1:20** gearmotors (7.4 V rated, Hall A/B
encoder) on a **WHEELTEC 102 mm U-bracket**, **65 mm wheels**, battery on the back (D-025). The earlier JGA25-370
gear sweep behind D-013/D-014 is superseded; it is in git history (commit 802eb5e).

**Scope.**
- **Model.** The firmware's planar pendulum model (`pendulum-dynamics.md`), plus:
  - rotor inertia reflected through the gearbox;
  - a voltage-driven brushed DC motor with coulomb gearbox friction;
  - **the firmware's average-voltage cap** (the MG310 is a 7.4 V motor on a 3S bus);
  - DRV8711 current clipping at I_trip;
  - a discrete 500 Hz LQR with a one-sample delay (REQ-RT-001, REQ-RT-004), designed for the capped range.
- **Ideal:** inductance (τ_e ≪ τ), backlash, wheel slip, sensor noise.
- **Sweep, 54 cases:** voltage cap 7.4 / 8.4 / 9.9 V × trip 1.0 / 1.5 / 2.0 A × gear efficiency 0.5 / 0.65 × VBAT
  12.6 / 11.1 / 9.9 V.

**Inputs and their sources.**
- The MG310 listing gives 1:20, 7.4 V, 0.4 kgf·cm at 400 rpm, 1.5 kgf·cm stall and ≤ 500 mA rated. Its stall current
  reads "≤ 2 mA"; the listed torques give 1.9 A at efficiency 0.6, so **2.0 A is an ASSUMPTION**.
- Derived constants:
  - no-load 545 rpm at the output (straight torque-speed line through the two listed points);
  - R = 7.4 V / 2.0 A = 3.70 Ω;
  - Ke = Kt = 6.09 mV·s/rad (I₀ 0.12 A ASSUMPTION);
  - gear efficiency 0.66 at stall and 0.71 at the rated point. 0.5 is used as the low corner.
- Rotor inertia 1.0e-6 kg·m², inductance 1 mH and 13 encoder pulses per motor revolution are **ASSUMPTIONS**; measure them at
  bring-up.
- Body parameters come from `mechanical/mass_budget.csv` (bracket, motors, battery on the back; pivot on the axle).

**Hand cross-checks.**
- Body: m = 0.387 kg, ℓ = 29.6 mm, J = 4.59e-04 kg·m².
  τ = √((J + mℓ²)/(m·g·ℓ)) = √((4.59e-04 + 0.387·0.0296²) / (0.387·9.81·0.0296)) =
  84 ms. The script prints 84 ms.
- Cruise voltage at 1.0 m/s = Ke·G·v/r + R·I₀ = 0.00609·20·1.0/0.0325 + 3.70·0.12 = 4.19 V. The script prints 4.19 V.
- TORQUE at 2.0 A = 256·20·0.05·2.0/2.75 = 186 (ISGAIN 20). The script prints 186.

### Findings

1. **The trip must be 2.0 A.** At every voltage cap, 1.0 A and 1.5 A trips recover only 12–17° worst case, short of
   the 2 × 10° target. **2.0 A recovers 21–22°**, which passes but with little margin.
2. **A 7.4 V cap is enough.** The cap barely changes recovery (22.3° at 7.4 V, 21.0° at 8.4 V, 20.9° at 9.9 V), and
   cruising at 1.0 m/s needs 4.2 V (57 % of the cap) and at 1.5 m/s 6.1 V. **The firmware limits the average motor
   voltage to 7.4 V** (duty ≤ 0.59 at 12.6 V): the motor stays at its rating, and stall current at the cap equals
   the trip.
3. **DRV8711 setting for Rsense = 50 mΩ:** I_trip 2.0 A → ISGAIN 20, TORQUE 186 (2.00 A). Rsense dissipates 0.2 W
   at the trip, within the 1 W 1206 part.
4. **The 2.0 A trip equals the JST PH contact rating (2 A).** Peaks are short (recovery bursts). The motor's 0.5 A
   continuous rating is enforced by the firmware I²t model (D-014's approach, kept).
5. **PWM ripple** at 25 kHz, D 0.5, 12.6 V with L = 1 mH: 126 mA p-p, 6 % of the trip (REQ-DRIVE-007).
6. **Encoder:** 13 pulses per motor revolution × 20 = 260 per wheel revolution, **1040 counts** with ×4 decoding. At the
   7.4 V cap the channel rate is about 2.4 kHz, far below the input filter corner (S5).
7. **Fall time constant τ = 84 ms**, about 42 updates per τ at 500 Hz.
8. **Static lean ≈ 17° toward the front.** The bracket puts the axle 18.8 mm behind the plate,
   so the plate, the parts and even the back-mounted battery (7 mm ahead of the axle) sit in front of it. With the
   battery on the front the lean would be 26°. The pitch setpoint and the fall limit are measured from this lean.
9. **No index channel.** The MG310 encoder is A/B only, so REQ-ODOM-005 (index-based reset) can't be met with
   this motor (D-028).

### Firmware constraints from S0

- `Drv8711DriverConfiguration`: Rsense 0.05 Ω, I_trip 2.0 A → ISGAIN 20, TORQUE 186; continuous rating 0.5 A by I²t.
- Average motor voltage capped at 7.4 V (duty ≤ 7.4 / VBAT).
- Gear ratio 20; wheel radius 0.0325 m; 1040 counts per wheel revolution (13 PPR ASSUMED; count at bring-up).
- Pitch setpoint about 17° toward the front (`docs/mechanical.md`); fall limit measured from it.
- Add reflected inertia to the plant model; J about the CoM (`docs/mechanical.md`).

### Model limits

Not simulated: gearbox backlash, wheel slip, sensor noise and estimator lag, motor inductance, battery sag (S1/S3
cover that). The motor constants come from a seller listing with a typo in the stall current. **Measure the
purchased motor** (stall current at 7.4 V, no-load speed and current, L, spin-down inertia, encoder PPR) and rerun.

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
| Switch-off with both MG310s stalled at full voltage (3.4 A each, no trip: pessimistic) | VBAT 12.84 V | VBAT 12.84 V; FET energy 2.1 mJ |
| Switch-off while pushed at 20 V back-EMF (above no-load speed) | VBAT 17.84 V | VBAT 17.84 V (TVS onset); FET 34 mJ |

Hand cross-check for the pushed case: 2 × (20 − 12.6 − 1.6) / 3.7 ≈ 3.1 A into the battery; simulated peak 2.9 A.
Regeneration needs the wheels above the motors' no-load speed (MG310: 545 rpm × 12.6 / 7.4 = 928 rpm, ≈ 3.2 m/s on
65 mm wheels), far outside the 1.5 m/s design limit, and even then the TVS keeps VBAT < 24 V. The FET energy
(34 mJ) is spread over the ~100 ms soft turn-off, about 0.3 W on average. The LCSC datasheet for C3040596 is
image-only, so the transient thermal rating is a bench check (thermocouple on Q101 during a pushed switch-off).
Re-run 2026-11-13 with the MG310 (D-027).

**Constraint:** turn-off is now slow (τ = 100k × 1.05 µF ≈ 105 ms); don't switch off while the motors are driven.

## S2: H-bridge switching (`bridge.py`)

**Scope.** One full bridge at transistor level (4 × CSD88537ND VDMOS), slow decay at 25 kHz centre-aligned,
850 ns dead time, DRV8711 gate drive as 10 V through R = 10 V / mean(IDRIVE source, sink); hot-loop
inductance 5 / 15 nH; MG310 (3.7 Ω, 1 mH, D-027) stalled at duty 0.5 and at the 7.4 V cap (duty 0.59), and running
at duty 0.59 with 5 V back-EMF.
Hand cross-checks: ripple at D 0.5 = V·T/(4L) = 126 mA (sim 124 mA); stall current at D 0.5 ≈ 1.70 A
(sim 1.52 A, dead time and FET resistance included).

### Findings

1. **The DRV8711 phase-pin absolute minimum (−0.6 V, SLVSC40 Abs Max) was violated for ~3 µs every PWM
   period**: during each dead time the motor current freewheels through the low-side body diode, holding
   the phase node at −0.73 V.
2. **Fix (now in the schematic):** SS34 Schottky (D501–D504, JLC basic C8678) from GND to each phase node.
   The freewheel plateau becomes **−0.36 V**; what remains is a 3 ns ringing spike to −0.67 V with a 5 nH
   hot loop (12 ns to −1.07 V at 15 nH) → **layout target: hot loop ≤ 5 nH** (Phase 3).
3. **Gate drive strength:** IDRIVE 00 (50/100 mA, the default) keeps switch-node overshoot ≤ 0.2 V; IDRIVE 11
   (200/400 mA) rings to +2.7…+5.5 V and puts 21.8 V on the low-side FET. **Firmware: keep IDRIVE at 00.**
4. **Losses are negligible:** Tj ≈ 44 °C at 40 °C ambient at the 2 A MG310 stall; no shoot-through in any
   case. The 60 V FETs are heavily oversized, which is fine. The SS34 clamps hold the plateau at −0.39 V at 1.8 A.

## S3: motor bus (`bus.py`)

**Scope.** Both bridges reduced to their bus current (I_motor × square(duty), in phase on one timer),
battery 60 / 150 mΩ, the VBAT capacitor set, 1.56 W logic load.

| Case | Result | Limit |
|---|---|---|
| Electrolytic C507 ripple, both motors at the 2.0 A trip, D 0.5 (recovery burst) | 0.878 A rms | 0.57 A (600 mA × 0.95 at 25 kHz): **exceeded during bursts only** |
| C507 ripple at the continuous current (0.5 A each, D 0.5) | **0.219 A rms** | 0.57 A |
| VBAT ripple p-p (2.0 A / 0.5 A) | 324 / 81 mV | — |
| Sag, aged pack at 9.9 V OCV, 4.0 A step | 8.96 V (hand 8.97 V) | logic UVLO stop 8.47 V |
| Sag, aged pack at 9.0 V OCV, 4.0 A step | 8.10 V (hand 8.06 V) | below 8.47 V: logic cuts off (intended); DRV8711 still above 8.0 V |

**Constraints for firmware:** enforce the continuous current with the I²t model (the bulk capacitor is sized
for it, not for sustained 2 A at D 0.5: electrolytic ripple heating is a thermal, time-averaged limit); raise an undervoltage fault and disarm below ~9.5 V under load so
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

- DRV8711: IDRIVEP/IDRIVEN = 00 (S2); TBLANK ≥ 1.2 µs; trip 2.0 A (ISGAIN 20, TORQUE 186) with an I²t model for the 0.5 A continuous rating (S0, S3).
- Average motor voltage capped at 7.4 V; gear 20; wheel r 0.0325 m; 1040 counts per wheel revolution; no index (S0).
- Undervoltage fault and disarm below ~9.5 V under load; never rely on the 8.47 V hardware cut-off (S3).
- VBAT sampled at ≤ 100 Hz, ratio 0.2126, per-board calibration stored in flash (S5).
- Power switch: turn-off takes ~100 ms; stop the motors before switching off (S1).

## Limits of the models

- Battery, lead inductance, MLCC derating, motor R/L and rotor inertia are assumptions (`common.py`, S0); measure them.
- Bridge gate drive is a resistive approximation of the DRV8711's current-source drive; hot-loop inductance is
  a corner (5 / 15 nH), not extracted from a layout. Re-run S2 with extracted parasitics after Phase 3.
- No DRV8711 current chopping in S2 (stall at the 7.4 V cap reaches the 2.0 A trip, not above it); chopping is a bench check.
- Buck dynamics not simulated (see S4). LDO HF rejection depends on TI's model and the assumed output capacitance.
- Encoder cable is lumped (1 m); no EMI or ESD simulation.
