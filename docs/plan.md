# Hardware plan: e-inverted-pendulum chassis PCB (schematic → simulation → layout)

## Context

`embedded-pro/e-inverted-pendulum-hardware` is empty (no commits). The firmware
(`embedded-pro/e-inverted-pendulum`) already runs on a NUCLEO-WB55RG and defines what the board must do. One firmware fact replaces the stepper assumption: **one DRV8711, with its indexer bypassed, drives two brushed DC gearmotors**, one per H-bridge, from TIM1 CH1–CH4 PWM at 25 kHz with slow decay. Each wheel has a quadrature encoder. The IMU is an MPU9250 on SPI2 with a 1 kHz data-ready line. BLE runs on the STM32WB's radio.

Goal: one 4-layer PCB that is also the robot's structural body. It carries the motors, battery, electronics and antenna, is built and assembled at JLCPCB, and is designed with the `hardware-design` skills (`mcu-circuit-design`, `power-pcb-layout`, `circuit-simulation`, `rf-layout`, `analog-circuit-design`, `interface-layout`).

### Decisions locked with the user
| Topic | Decision | Why |
|---|---|---|
| MCU | **STM32WB55RGV6** (VFQFPN68, LCSC C401505, 225 in stock), replacing the CG | Same die and pins as the Nucleo, so the firmware pin map is reused 1:1. The CG (QFN48) has no PB10–15 or PC0–6: no SPI2, and all 27 GPIOs would be used. |
| Motors | 2 × 25 mm 12 V gearmotor (JGA25-370 class) with **ABZ encoder** (A, B, index Z) | Motor on a 2-pin XH; encoder on a 5-pin PH (VCC, GND, A, B, Z). Firmware encoder pins kept exactly. |
| Storage | **SPI NOR flash W25Q16JVSSIQ** (2 MB, C131025) on SPI1 next to the DRV8711 | Parameter store (REQ-TUNE-007), BLE bonds, telemetry log. SPI1 carries only occasional DRV8711 traffic, so it doesn't disturb the 1 kHz IMU traffic on SPI2. |
| Battery | 3S LiPo pack, 9.0–12.6 V, XT30, external balance charger | DRV8711 needs VM ≥ 8 V |
| IMU | **MPU-6500** (C50278) | Same accel/gyro die and registers as the MPU9250. Only WHO_AM_I changes (0x70). |
| Chassis | Single vertical plate, about 100 × 160 mm (final size from sizing) | Motors on L-brackets at the bottom edge, battery strapped to the back face, antenna on the top edge |
| Radio | Printed IFA + MLPF-WB55-01E3 IPD, DNP pi tuning network + DNP U.FL test port; no certification | Cheapest; VNA tuning in the final assembly |
| Fab | JLCPCB 4-layer 1.6 mm (JLC04161H-7628), 1 oz outer / 0.5 oz inner, top-side PCBA | Solid L2 GND under RF and motor hot loops |
| Debug | STDC14 (Samtec FTSH-107-01-L-DV-K, C5307809): SWD + NRST + USART1 VCP | No USB: TIM1_CH4 is only on PA11 = USB_DM |

## Architecture

```
3S LiPo ─XT30─ fuse ─ back-to-back PMOS (AO4805) ─┬─ TVS SMBJ15A ─ bulk 220µF+MLCC ── VM ── DRV8711 + 4×CSD88537ND ─┬─ Motor L (bridge A) + enc L
  (rev-pol + on/off + soft-start, slide switch)   │                                     Rsense 2×50 mΩ ───────────────┴─ Motor R (bridge B) + enc R
                                                  ├─ VBAT divider ─ ADC
                                                  └─ TPS62933 buck → 5V0 ─ TLV75533 LDO → 3V3 ─ STM32WB55RG (SMPS on, 10µH+10nH)
                                                                       │                         ├ SPI1 ─ DRV8711 + W25Q16 flash   ├ RF1 ─ MLPF ─ 50Ω ─ pi(DNP) ─ IFA
                                                                       └ encoder VCC (0Ω opt)    ├ SPI2 ─ MPU-6500    ├ HSE 32 MHz / LSE 32.768 kHz
                                                                         ABZ ×2 ─ ESD ─ LVC3G17 ─┤ (5 V-tolerant Schmitt buffers powered from 3V3)
                                                                                                 └ STDC14, LEDs, button, buzzer, Qwiic (I2C3)
```
Back-to-back PMOS is used rather than an ideal diode: regenerated motor energy must be able to flow back into the battery while the board is on. When the board is off, the TVS and bulk capacitors absorb it.

### Pin map: the Nucleo map kept 1:1, plus additions (source of truth: `cubemx/*.ioc`)
| Function | Pins | Notes |
|---|---|---|
| Bridge A1/A2/B1/B2 | PA8/PA9/PA10/PA11, TIM1 CH1–4 | unchanged |
| DRV nFAULT | PA6 (TIM1_BKIN) + PC4 (EXTI4), same net | open-drain, 10 kΩ to 3V3 |
| DRV SPI1 / CS (active-high) / SLEEPn / RESET | PB3/PB4/PB5, PA4, PB8, PB9 | SDATO pull-up if open-drain (check SLVSC40). SCS has an internal pull-down, so the DRV8711 is deselected at reset. |
| **New:** flash on SPI1, CS (active-low) | PB3/PB4/PB5, PA15 | 10 kΩ pull-up on /CS; /WP and /HOLD pulled up. Mode 0 matches the DRV8711; firmware sets the prescaler per device. |
| IMU SPI2 / CS / DRDY | PB13/PB14/PB15, PB12, PC6 | |
| Enc L A/B/Z | PC0 (LPTIM1_IN1) / PC2 (LPTIM1_IN2) / PC5 | Exactly as `WheelEncodersStm.hpp:23-25` |
| Enc R A/B/Z | PA0 (TIM2_CH1) / PA1 (TIM2_CH2) / PC3 | Exactly as `WheelEncodersStm.hpp:27-29`; `invertPhaseA` handles the mirrored mounting |
| Index as EXTI | PC5 = EXTI5, PC3 = EXTI3 | Wired so the firmware can latch the index later (REQ-ODOM-005); unique against EXTI0/4/6 |
| Console USART1 → STDC14 VCP | PB6 TX / PB7 RX | SWO not available: PB3 = SPI1_SCK |
| **New:** VBAT_SENSE | PC1 (ADC1_IN2) | |
| **New:** buzzer, red fault LED, green LED | PA7 (TIM17_CH1), PB1, PB0 | |
| **New:** user button | PD0 (EXTI0; Nucleo SW2 pin) | EXTI numbers stay unique |
| **New:** Qwiic I2C3 | PB10/PB11 | |
| **New:** DRV nSTALL (optional) | PB2 | |
| BOOT0 | PH3: 10 kΩ pull-down + pad | |

Before the schematic is frozen, confirm in CubeMX that PB11, PD0, PB2 and PA15 are bonded on VFQFPN68, and that PA15 is free once JTAG is off (SWD only).

## BOM: key parts (JLCPCB stock checked 2026-11-04)
| Function | Part | LCSC | Stock |
|---|---|---|---|
| MCU | STM32WB55RGV6 | C401505 | 225 |
| RF IPD | MLPF-WB55-01E3 | C2651048 | 3.3k |
| HSE 32 MHz (ST-recommended, no load caps, HSETUNE) | NX2016SA-32M-EXS00A-CS06465 | C1986260 | 49.7k |
| LSE 32.768 kHz | NX3215SA family, C_L ≤ 7 pF (AN2867); choose the in-stock variant | C156244 etc. | 8–14k |
| SMPS L / series L / caps | LQM21FN100M80L (10 µH) / LQG15HS10NJ02D (10 nH) / CL05A475MP5NRNC | C162582 / C77103 / C23733 | ok |
| Motor driver | DRV8711DCPR | C60013 | 128 |
| Bridge FETs (×4 duals, one half-bridge each) | CSD88537ND, 60 V | C117439 | 14.8k |
| Sense resistors ×2 | WSL2512R0500FEA (50 mΩ, firmware default) | C413486 | 44.8k |
| IMU | MPU-6500 | C50278 | 3.6k |
| Buck 5 V | TPS62933DRLR (3.8–30 V) | C3200405 | 22k |
| LDO 3V3 | TLV75533PDBVR | C404027 | 95k |
| Power-path FET | AO4805 (dual P, 30 V) | C3040596 | 12k |
| TVS VBAT / Vgs clamp | SMBJ15A / BZT52C15 | C83846 / C2104 | 18k / 137k |
| Bulk cap | 220 µF 25–35 V polymer/electrolytic (EEEFK1V221P) | C178562 | 6.6k |
| Battery connector | XT30UPB-F | C108769 | 36k |
| Motor connectors ×2 | JST S2B-XH-A (side entry, 3 A) | C157931 | 70k |
| Encoder connectors ×2 | JST S5B-PH-K-S (side entry) | C157923 | 59k |
| Encoder buffers ×2 (A/B/Z each) | SN74LVC3G17DCTR (Schmitt, 5 V-tolerant inputs, I_off) | C18213 | 8.9k |
| Encoder ESD | TPD4E05U06DQAR | C138714 | 130k |
| SPI flash | W25Q16JVSSIQ, 2 MB, SOIC-8 208 mil (alternative: W25Q80DVSSIG, 1 MB, C98163, 29.7k, same footprint) | C131025 | 8.4k |
| Debug | FTSH-107-01-L-DV-K (STDC14) | C5307809 | 616 |
| Antenna test port (DNP) | BWU.FL-IPEX1 | C5137195 | 617k |
| Buzzer / button / switch / Qwiic | MLT-8530 / TS-1187A-B-A-B / SS-12D10L5 / SM04B-SRSS-TB | C94599 / C318884 / C319012 / C160404 | ok |

Stock risk: the MCU (225) and DRV8711 (128) are thin. Order them with the first PCBA run, or reserve them through JLC parts pre-order. `scripts/jlc_stock.py` re-checks every BOM line against the JLC API before each order.

## Hardware repo layout (`e-inverted-pendulum-hardware`, branch `claude/nice-ride-x9xyyl`)
```
README.md, CLAUDE.md (rules: skills to load, JLC constraints, no undocumented numbers)
.claude/settings.json            # hardware-skills marketplace, project scope (skills README)
docs/ requirements.md            # HW reqs traced to firmware REQ-IDs (DRIVE-005/007, SAFE-002/009, SYS-002/003, IMU-001/002, ODOM-001/003/005, RT-004)
      architecture.md power-map.md pinmap.md mechanical.md rf.md bringup.md decisions.md
cubemx/e-inverted-pendulum.ioc   # pin plan, validated by CubeMX
kicad/  *.kicad_pro, hierarchical *.kicad_sch, *.kicad_pcb, lib/ (symbols, footprints, 3D)
simulation/                      # exact layout from circuit-simulation §2
mechanical/                      # STEP: motor, bracket, wheel, battery; mass/CoM script
scripts/ jlc_stock.py, export_fab.sh, render_layers.py, route_metrics.py
fab/                             # generated Gerbers, drill, BOM/CPL in JLC format
.github/workflows/hardware.yml   # kicad-cli ERC/DRC, simulation run, fab artifact
```
Tooling to install in the container: KiCad 9 (`kicad-cli`), ngspice-47, Python with numpy/scipy/matplotlib/spicelib. None of these are present yet.

## Phase 0: requirements, sizing, mechanics (gate: user review)
1. Bootstrap the repo as above. Commit this plan as `docs/plan.md` and the decision table as `docs/decisions.md`.
2. `docs/requirements.md`: one row per firmware REQ that constrains the hardware, plus the open items this board closes: VBAT ADC (safety-supervisor.md undervoltage), Rsense/Itrip "board facts" (motion-actuation.md:111-116), and the IMU axis map.
3. **S0 sizing (Python, `simulation/sizing.py`)**:
   - Inputs: the pendulum model from `documentation/theory/pendulum-dynamics.md`, with m, ℓ and J from a CAD mass budget; JGA25-370 Kt, R, L and gear options; VBAT 9.0–12.6 V.
   - Outputs:
     - gear ratio;
     - torque margin ≥ 2× for recovery from 10° at 9 V;
     - Itrip ≤ the motor's continuous rating and ≤ 3 A (the XH connector's rating);
     - Rsense, ISGAIN and TORQUE values;
     - PWM ripple at 25 kHz versus τ_e (REQ-DRIVE-007);
     - encoder CPR and maximum edge rate (ABZ lines × 4 × gear × peak motor speed), checked against the LPTIM1 encoder-mode input limit for its kernel clock and against TIM2.
4. Mechanics (`docs/mechanical.md`):
   - plate outline and bracket hole pattern (NPTH, copper keep-out);
   - battery strap slots;
   - wheel clearance;
   - bumpers on both faces near the top, so a fall never lands on the antenna edge;
   - CoM/inertia exported to the firmware.
5. CubeMX `.ioc` with the pin map above, clocks (HSE 32 MHz, LSE, SMPS 4 MHz) and conflict check.

## Phase 1: schematic (KiCad hierarchical, one sheet per block)
Rules come from `mcu-circuit-design` §2–§12 and `analog-circuit-design`; the datasheets win.

1. **Power entry**:
   - XT30, then an SMD fuse (about 7.5 A), then AO4805 back-to-back with:
     - gates pulled to source by 100 kΩ;
     - the slide switch pulling the gates down through 10 kΩ;
     - BZT52C15 V_GS clamp;
     - gate RC for soft-start.
   - SMBJ15A clamp: VRWM 15 V is above 12.6 V; V_C 24.4 V is below the 30 V buck, 60 V DRV and 60 V FET ratings.
   - Bulk: 220 µF + 4 × 10 µF/25 V. Check the MLCC DC-bias derating.
   - VBAT divider 100 k/27 k (2.68 V at 12.6 V) after the switch, with a 100 nF C0G/X7R charge-bucket capacitor at the ADC pin.
2. **Logic power**:
   - TPS62933 to 5V0. Use the FPWM variant if it is stocked; set fsw ≥ 1.2 MHz; follow the datasheet's layout and component guidance.
   - TLV75533 to 3V3.
   - Power budget about 120 mA on 3V3; LDO loss about 0.25 W.
3. **MCU**, decoupling per DS11929 Fig. 16:
   - VDD: n × 100 nF + 4.7 µF.
   - VDDA: 10 nF + 1 µF, with VREF+ tied per the package.
   - VDDRF: 100 nF + 100 pF.
   - VDDSMPS/VFBSMPS: 4.7 µF each.
   - SMPS inductor: 10 µH + 10 nH in series.
   - VBAT and VDDUSB tied to VDD with 100 nF.
   - NRST: 100 nF.
   - AT0/AT1 per the datasheet.
   - HSE with no external capacitors.
   - LSE with load capacitors from the C_L formula (stated stray convention).
4. **RF**:
   - Copy the RF1 → MLPF-WB55-01E3 section from ST AN5165.
   - 50 Ω GCPW to a DNP U.FL, then a pi network (0 Ω series, shunts DNP), then the IFA feed.
   - Use a published IFA designed for 1.6 mm FR-4 (e.g. the 1.6 mm variant in Silicon Labs AN1088) and copy its geometry exactly.
5. **Motor drive**, per the DRV8711 datasheet (SLVSC40) and the BOOST-DRV8711 reference:
   - VM decoupling;
   - VCP 1 µF to VM; CP1–CP2 100 nF (VM-rated); VINT 1 µF; V5 bypass;
   - 0 Ω gate-resistor footprints;
   - 4 × CSD88537ND;
   - 2 × 50 mΩ Rsense with Kelvin ISENP/ISENN;
   - nFAULT and nSTALL pull-ups to 3V3;
   - DNP RC snubber footprints on each output.
6. **ABZ encoders and motor connectors**:
   - XH 2-pin for motor power and PH 5-pin (VCC, GND, A, B, Z) for each encoder. Confirm the pinout against the purchased encoder's cable.
   - Encoder VCC defaults to 5V0 (typical for optical/magnetic ABZ), with a 0 Ω option for 3V3. Add a local 100 nF + 10 µF and a PTC or series R so a shorted cable can't drop the rail.
   - Signal path per channel, from the connector inwards:
     1. TPD4E05U06 ESD at the connector, pass-through routing (`interface-layout` §2);
     2. DNP pull-up to encoder VCC, fitted if the outputs are open-collector;
     3. 100 Ω series + 1 nF (fc well above the S0 maximum edge rate);
     4. SN74LVC3G17 powered from 3V3, then the MCU pin.
   - Why the buffer: during power-up, 5V0 comes up before 3V3, and FT pins take ≤ 3.6 V while VDD = 0 (AN4899). The LVC3G17's I_off and 5 V-tolerant inputs remove that back-powering path and add Schmitt hysteresis on long motor cables.
6b. **SPI flash**:
   - W25Q16JVSSIQ on SPI1 with /CS on PA15 (10 kΩ pull-up) and /WP and /HOLD pulled up to 3V3; 100 nF at VCC.
   - 33 Ω series on SCK at the MCU, because SPI1 now has three loads (DRV8711, flash, test pad).
   - Place it near the MCU, away from the DRV8711 power stage.
7. **IMU**: MPU-6500 per its datasheet (REGOUT cap, VDDIO, decoupling) and SPI2, with the data-ready line on PC6.
8. **UI and expansion**:
   - STDC14 pinout per ST UM2448;
   - LEDs, user button (100 Ω + RC), BOOT0 pad;
   - buzzer: NPN + flyback diode;
   - Qwiic port with ESD and 2.2 kΩ pull-ups (SLVA689A calculation).

Gate:
- ERC clean;
- the `mcu-circuit-design` §12 and `analog-circuit-design` §10 checklists completed in `docs/`;
- `jlc_stock.py` all green for 5 boards;
- user review.

## Phase 2: simulation (`circuit-simulation` skill: values read from `*.kicad_sch`, `PROPOSED` override dict, one command → `results/`, `plots/`, `REPORT.md`)

| ID | Circuit / question | Pass criterion |
|---|---|---|
| S1 | Power entry: battery (12.6 V, 30 mΩ, cable L) → fuse → AO4805 → bulk. Hot-plug inrush, switch-on, **reverse battery**, **switch-off while regenerating** | Inrush within FET SOA and fuse I²t; reverse leakage < 1 mA and \|V_GS\| < 20 V; VM peak < 24 V with TVS energy within rating |
| S2 | H-bridge + motor: CSD88537ND vendor models; DRV8711 as IDRIVE current sources + 850 ns dead time; motor R/L/back-EMF; 25 kHz centre-aligned slow decay; Itrip chop (TOFF/TBLANK); full-speed reversal | No shoot-through; switch-node overshoot < 20 % of VM; current ripple per S0; FET T_j < 100 °C; bulk-cap ripple current within rating |
| S3 | Bus coupling: VM ripple and 12.6 → 9 V sag into the buck input; input-filter vs negative input impedance (Middlebrook) if a filter is added | No buck UVLO or LDO dropout; filter peak below the buck's input impedance |
| S4 | Logic rails: 5V0 load step, line step from S2; LDO PSRR at fsw; 3V3 ripple; start-up vs BOR | 3V3 ripple at VDDRF inside AN5165 limits (5–15 mVpp); monotonic ramp |
| S5 | Analog: VBAT divider + bucket + ADC sample model, settling to ½ LSB; Monte Carlo (resistor tolerance + VDDA/VREFINT). Encoder channel: cable RC + ESD capacitance + 100 Ω/1 nF + LVC3G17 thresholds, at the max edge rate, with and without OC pull-ups. Power-up with 5V0 ahead of 3V3. | Settles within the sampling time; under-voltage threshold within ±50 mV/cell at 3σ; A/B quadrature phase error < 25 % of a quarter period at max speed; no current into MCU pins while 3V3 = 0 |

- Vendor models: TI PSpice for the CSD88537ND, TPS62933 and TLV755, an AOS model for the AO4805, a Littelfuse model for the SMBJ.
- Encrypted models: use an averaged or behavioural model instead and say so in the report (skill §4).
- RF has no SPICE step. After the VNA measurement, scikit-rf computes the pi-network values.
- Gate: every check passes as drawn, or the `PROPOSED` changes are moved into the schematic. REPORT.md includes the firmware constraints, e.g. the Itrip/TORQUE values and the minimum VBAT for arming.

## Phase 3: PCB layout (`power-pcb-layout` working agreement: the user places the anchors, I follow)

**Stack-up.**

| Layer | Use |
|---|---|
| L1 | Parts, RF GCPW, short power pours |
| L2 | Solid GND, never cut |
| L3 | VM/VBAT pours, 5V0/3V3 pours, slow signals |
| L4 | Signals + GND fill |

- 50 Ω GCPW width and gap from the JLC impedance calculator for the 0.21 mm 7628 prepreg.
- Inner copper weight stated on the fab order.

**Floorplan of the vertical plate, top to bottom.**
1. Antenna on the top edge with a keep-out on all layers, plus the MLPF and RF path.
2. MCU, crystals, STDC14, LEDs, button, buzzer.
3. Battery zone on the back face, ≥ 25 mm below the antenna keep-out, with logic power on the front.
4. IMU on the vertical centreline, about 30 mm above the axle and ≥ 15 mm from switch nodes. Its axes are aligned to the body frame; the mapping is written in `docs/pinmap.md` for the firmware.
5. Bottom band: DRV8711, FETs, Rsense and bulk caps in the centre; XT30 and switch; XH motor and PH encoder connectors, with the encoder buffers and ESD next to them, plus bracket holes at the left and right corners. Encoder traces stay off the bridge switch-node copper on every layer.

**Anchors the user places.** XT30, switch, XH/PH connectors, bracket and strap holes, antenna, MCU, IMU, STDC14, buttons, LEDs, bumpers.

**Rules.**
- Power map table and net classes (`docs/power-map.md`), derived per skill §2.
- Hot loops: bulk/HF cap → HS → LS → Rsense → cap GND, smallest possible over L2.
- Gate traces paired with their return.
- Kelvin taps from the inner pad edges of Rsense.
- DRV8711 PowerPAD via array.
- RF per the `rf-layout` checklist §12:
  - no vias or stubs on the RF line;
  - via fence at 1–1.3 mm;
  - ≥ 2 ground vias per shunt part;
  - SMPS inductor at the pins, oriented away from RF;
  - HSE away from the SMPS.
- ESD at connectors per `interface-layout` §2.

**Delivery.** Phased, with per-layer renders after each phase: support placement → power copper → critical routes → remaining routes → fills and DRC.

**Gate.**
- DRC clean with schematic parity;
- quality-bar metrics (`route_metrics.py`);
- `power-pcb-layout` §7 and `rf-layout` §12 checklists;
- JLC DFM: min track/space and 0.3 mm vias.

## Phase 4: fab and bring-up
- `export_fab.sh`: Gerbers, drill, and BOM/CPL in JLC format via `kicad-cli`. Check rotations in JLC's viewer. Order 5 PCBs, 2–3 assembled.
- `docs/bringup.md`, in order:
  1. Bench supply 12 V at 100 mA, then the rails.
  2. SWD connect; HSE and LSE start.
  3. HSE trim with a counter per AN5042, stored in OTP.
  4. BLE advertising and RSSI.
  5. MPU-6500 WHO_AM_I and DRV8711 register read-back (REQ-SYS-003).
  6. Motors at low Itrip.
  7. Encoder sign (REQ-ODOM-003) and one index pulse per revolution on PC5/PC3.
  8. Flash JEDEC ID read and an erase/program/verify cycle.
  9. VNA tuning of the pi network with battery and motors fitted.
  10. Thermal soak.
  11. Tri-state on tilt > 35° (REQ-SAFE-002).

## Firmware follow-ups (separate task in `e-inverted-pendulum`; no pin changes)
- New board preset and PlatformImpl, copied from `targets/platform_implementations/st/`, with:
  - clock config: SMPS on, HSE trim, LSE;
  - IMU WHO_AM_I accepting 0x70 (MPU-6500);
  - IMU axis map for vertical mounting.
- VBAT ADC and the under-voltage fault.
- Rsense and Itrip from S0.
- Encoder CPR, gear ratio and wheel radius.
- Index latch on EXTI3/EXTI5 to close REQ-ODOM-005; the hardware wires it.
- SPI1 shared by the DRV8711 and the flash: per-device prescaler and CS polarity; parameter store and bonds in flash (REQ-TUNE-007).
- Buzzer, LED and button pins; IWDG.

## Verification
- `kicad-cli sch erc` and `kicad-cli pcb drc --schematic-parity`, both with zero errors, in CI.
- `python -m simulation.run_all` regenerates every number in `simulation/REPORT.md`; all checks pass.
- `scripts/jlc_stock.py kicad/*.kicad_sch` reports every LCSC part in stock for the build quantity.
- CubeMX opens the `.ioc` with no pin conflicts.
- Per-layer SVG renders reviewed at each layout phase.
- Bring-up checklist results recorded in `docs/bringup.md`.

## Remaining open points (non-blocking defaults; confirmed at the Phase 0 gate)
1. Gearbox ratio: chosen by the S0 sizing.
2. Wheel: 65–68 mm (firmware uses r = 0.034 m).
3. Battery capacity and size: default 3S 1000 mAh, about 75 × 35 × 25 mm. This sets the strap slots and CoM.
4. Encoder part, line count and output type (push-pull or open-collector): set by the purchased encoder. Defaults are 5V0 supply, OC pull-ups DNP, and CPR taken from S0.
5. LSE crystal variant: in stock with C_L ≤ 7 pF.
6. Rsense: stays 50 mΩ unless S0 or S2 says otherwise.
