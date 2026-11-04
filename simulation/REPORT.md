# Simulation report

Reproduce: `python3 simulation/sizing.py` (S0). S1–S5 follow in Phase 2, once the schematic exists.

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
