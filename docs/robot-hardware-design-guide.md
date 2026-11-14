# Self-Balancing Robot Hardware Design Guide (PCB as Chassis)

> This guide is a **component-agnostic** body of knowledge for designing and reviewing a battery-powered motor-control robot whose PCB is also its structural body. Such a board has:
> - a multi-cell lithium battery input with a power switch, reverse-polarity, inrush and surge protection;
> - logic rails from a buck converter followed by a low-noise LDO;
> - a wireless MCU with an on-chip 2.4 GHz radio, a match/filter network and a printed antenna;
> - a gate driver with external MOSFET half-bridges and shunt current sensing, driving brushed DC gearmotors;
> - wheel encoders and other inputs that arrive on cables next to motor leads;
> - an IMU that measures the body's attitude;
> - non-volatile memory, an expansion bus and an NFC tag with a printed coil;
> - mounting points that carry the motors, the battery and the impact of falls.
>
> It records what a senior power, RF and mechatronics engineer checks when designing these blocks, protecting them and laying them out.
>
> Treat this guide as an **interface**, not an implementation. It describes functional blocks and the parameters that constrain them. A board is one implementation. Its binding contract is `docs/requirements.md`, where every row traces to a firmware `REQ-*` or a decision; its intent is `docs/decisions.md`. When this guide and the requirements disagree, the **requirements win**. When a decision deliberately departs from a rule here and says why, a review records an **accepted deviation**, not a defect.
>
> This board's choices appear as examples ("e.g. D-027"). They illustrate a rule; they are not the rule.
>
> **Sources.** Every number carries a source: a key in brackets (§17), a datasheet section, or a file in this repository (`simulation/REPORT.md` S1, `docs/design-calcs.md`). *(derived)* marks arithmetic on sourced inputs. Numbers without a source are marked **ASSUMPTION** or *rule of thumb* and collected in §16.
>
> **Design parameters.** A board's requirements fix their values. They are used throughout:
>
> | Symbol | Meaning | This board (example) |
> |---|---|---|
> | $V_{bat}$ | Battery range, empty to full | 9.0–12.6 V, 3S LiPo (D-003) |
> | $V_{abs}$ | Highest input the board must survive (mis-set charger, transients) | 13.5 V (HW-PWR-001) |
> | $V_C$ | Input TVS clamp voltage at its rated pulse current | 24.4 V (`docs/design-calcs.md`) |
> | $V_{bus,min}$ | Lowest bus voltage every load accepts | 8.0 V, driver VM minimum (HW-PWR-002) |
> | $I_{trip}$ | Per-motor peak current limit | 2.0 A (D-027) |
> | $I_{cont}$ | Motor continuous rating | 0.5 A (D-027) |
> | $I_{bus,pk}$ | Peak battery current | ≈ 4.2 A (`docs/architecture.md`) |
> | $f_{PWM}$ | Bridge PWM frequency | 25 kHz (HW-DRV-007) |
> | $f_{sw}$ | Logic buck switching frequency | 1.2 MHz (D-018) |
> | $f_{enc}$ | Maximum encoder channel frequency | ≈ 2.4 kHz (S0) |
> | $N_{layer}$, $h_{12}$ | Copper layers; L1-to-L2 dielectric | 4; 0.21 mm (D-008) |

---

## Table of contents

1. [System overview & requirements traceability](#1-system-overview--requirements-traceability)
2. [Battery input: switch, reverse polarity, inrush, surge](#2-battery-input-switch-reverse-polarity-inrush-surge)
3. [Logic rails: buck + LDO](#3-logic-rails-buck--ldo)
4. [MCU support](#4-mcu-support)
5. [2.4 GHz RF](#5-24-ghz-rf)
6. [H-bridge gate drive & current sense](#6-h-bridge-gate-drive--current-sense)
7. [Encoders & external-cable inputs](#7-encoders--external-cable-inputs)
8. [IMU placement & mechanical coupling](#8-imu-placement--mechanical-coupling)
9. [NFC coil design & tuning](#9-nfc-coil-design--tuning)
10. [Memory & expansion buses](#10-memory--expansion-buses)
11. [PCB as chassis: mechanics](#11-pcb-as-chassis-mechanics)
12. [Thermal design](#12-thermal-design)
13. [Layout & stack-up](#13-layout--stack-up)
14. [KiCad & JLCPCB practicalities](#14-kicad--jlcpcb-practicalities)
15. [Go/no-go checklist](#15-gono-go-checklist)
16. [Open items: assumptions & rules of thumb](#16-open-items-assumptions--rules-of-thumb)
17. [References](#17-references)

---

## 1. System overview & requirements traceability

A balancing robot board has four jobs:
- turn a battery that can be plugged in backwards, hot, or into a spinning motor into **clean, protected rails**;
- deliver **controlled torque** to two motors and tell the firmware how hard it is pushing;
- **sense the body**: attitude, wheel position, battery state;
- **survive being a chassis**: carry the motors and battery, take falls, and keep the radio working next to all of it.

```
 BATTERY ─ conn ─ fuse ─ rev-pol FET ─ switch FET ─┬─ TVS + bulk ═ VM ═ gate driver ═ 4 half-bridges ═ motor L / motor R
                     (gate RC: soft start)         │                  ▲ fault ─► timer break   └ shunts ─ Kelvin ┘    │
                                                   ├─ divider ─► ADC                                              cable
                                                   └─ buck (EN = UVLO) ─ 5V ─┬─ LDO ─ 3V3 ─ MCU + radio ─ match/filter ─ 50 Ω ─ pi ─ antenna
                                                                             └─ limited encoder supply ───────────► cable
 encoders ◄─ cable ─ ESD ─ RC ─ Schmitt buffer (3V3) ─► timer inputs        SPI: driver, flash, IMU    I²C: EEPROM, NFC tag + coil, expansion
 MECHANICS: the plate carries the motor bracket, the battery and the bumpers; antenna at the edge farthest from motors and switchers
```

The **power entry** decides whether a reversed plug or a fall costs a fuse or a board. The **bridge** sets torque, heat and bus noise. The **radio, IMU and encoders** decide whether the robot connects and balances. The **mechanics** decide whether it survives its first week.

### 1.1 Traceability

- **Every hardware requirement traces** to a firmware `REQ-*`, a firmware file and line, or a decision (CLAUDE.md §2). A requirement without a trace is a wish. One without a verification method is untested.
- **Verification method per row:** R (design review), S (simulation step), B (bring-up test) (`docs/requirements.md`). A review closes R items, cites the S step for S items, and lists B items as open until bring-up.
- **One pin map,** machine-checked against the package, the alternate functions and the firmware (`pin-data/pinmap.csv`, `scripts/check_pinmap.py`):
  - every pin bonded on the chosen package (e.g. D-001: the 48-pin package lacks SPI2);
  - every alternate function exists on its pin;
  - one signal per pin, except deliberate shared nets (e.g. the driver fault on a timer break and an EXTI pin);
  - unique EXTI line numbers: on STM32, EXTI line *n* is shared by pin *n* of every port [RM0434].
- **Hardware that relies on firmware is incomplete until the constraint is written down**: trip settings, voltage caps, sampling rates, "stop the motors before switching off" (`docs/firmware-interface.md`, REPORT "Constraints for firmware").
- **Superseded decisions stay in the table**, marked with their replacement (e.g. D-013 → D-027). Review against the decision in force.

### 1.2 Phase gates

Gates and their criteria are in `docs/plan.md`; the user signs off each one. This guide's sections map to them:

| Gate | Must hold (`docs/plan.md`) | Sections |
|---|---|---|
| Phase 0: requirements, sizing, mechanics | Requirements traced; S0 sizing; mechanical concept and mass budget | §1, §6.1, §11 |
| Phase 1: schematic | ERC clean; `mcu-circuit-design` §12 and `analog-circuit-design` §10 checklists done; `jlc_stock.py` green for 5 boards | §2–§10, §14.1 |
| Phase 2: simulation | Every S-check passes as drawn, or the `PROPOSED` changes are in the schematic; firmware constraints in REPORT | §2, §3, §6, §7 |
| Phase 3: layout | DRC clean with schematic parity; quality-bar metrics; `power-pcb-layout` §7 and `rf-layout` §12 checklists; JLC DFM | §5, §6, §8, §9, §11–§14 |
| Phase 4: fab & bring-up | Fab outputs, CPL rotations checked; bring-up steps recorded | §14.2, §14.3 |

---

## 2. Battery input: switch, reverse polarity, inrush, surge

### 2.1 Order of parts

- **Connector → fuse → reverse-polarity element → switch → TVS + bulk → loads.**
- **The TVS sits after the reverse-polarity element.** A unidirectional TVS ahead of it conducts forward into a reversed pack and blows the fuse at best (e.g. D102 note on the power-entry sheet). Put it first only if a fuse-blowing crowbar is the intended reverse protection.
- **Always-on loads sit after the switch.** A 127 kΩ battery divider at 12.6 V draws 99 µA *(derived)*, ten times a 10 µA off-state budget (HW-PWR-007).

### 2.2 Reverse polarity and the power switch

- **Options, in order of increasing efficiency:** series diode, high-side P-FET, low-side N-FET [SLVA139]. The FETs drop only $I \cdot R_{DS(on)}$.
- **Regeneration decides the topology.** A series diode or ideal-diode controller conducts one way. Energy that a decelerating or back-driven motor returns then has nowhere to go but the bulk capacitance, and the bus pumps (§6.7). Back-to-back P-FETs (common source) block a reversed pack, switch the load and **conduct both ways when on** (e.g. D-011).
- **$V_{GS}$ at both ends of the battery range.**
  - At $V_{bat,min}$ the gate drive must reach the $R_{DS(on)}$ specification point.
  - At $V_{abs}$ it must stay inside $V_{GS}$ abs max, with a gate-source Zener as the transient backstop.
  - E.g. a 100 k/100 k divider gives −4.5 V at 9.0 V (AO4805 ≤ 26 mΩ at −4.5 V) and −6.8 V at 13.5 V against ±20 V (`docs/design-calcs.md`).
- **Switch the gate, not the current.** A slide switch on the gate line needs no contact rating for motor current (e.g. SW101).
- **Off-state drain** = FET $I_{DSS}$ + Zener $I_R$ + everything ahead of the switch. Compare it with the budget (e.g. ≤ 1.1 µA vs 10 µA, `docs/checklists/phase1.md`, HW-PWR-007).

### 2.3 Soft start and hot plug

- **Inrush.** A fully-on FET charging the bulk capacitance from a low-impedance pack is limited only by pack, lead and FET resistance. Check the peak against the FET's pulse rating and SOA and the fuse's $I^2t$ (S1 pass criterion, `docs/plan.md`).
- **Miller soft start.** A gate-drain capacitor with a gate resistor sets $dV/dt ≈ I_G / C_{GD,ext}$ and the inrush to $C_{bulk} \cdot dV/dt$. E.g. 0.08 mA into 47 nF ≈ 1.7 V/ms → ≈ 0.5 A for ≈ 7 ms (`docs/design-calcs.md`, S1).
- **Hot plug is a different case from switch-on.** Plugging in the pack steps the input FET's source to $V_{bat}$ through its body diode while the gate capacitor still holds the gate at the empty bus. The gate-drain capacitor couples the edge into $V_{GS}$ and turns the FET on.
  - S1 found a 44.6 A spike, above the AO4805's 40 A pulse rating, and the logic powering up with the switch **off** (`simulation/REPORT.md` S1).
  - Fix: a gate-source capacitor that forms a divider with the Miller capacitor, so the step $V_{bat} \cdot C_{GD}/(C_{GD}+C_{GS})$ stays below $|V_{th,min}|$ (e.g. −0.57 V vs 1.0 V, D-021).
  - Simulate hot plug with the lead inductance and pack resistance, with the switch both on and off.
- **Soft start makes turn-off slow** (e.g. τ = 100 kΩ × 1.05 µF ≈ 105 ms). Switching off under motor load dissipates in the FET during the ramp. Size it (S1: ≤ 34 mJ) and tell the firmware to stop the motors first (`docs/firmware-interface.md`).

### 2.4 Surge clamp

- **Standoff** $V_{RWM} ≥ V_{abs}$.
- **Every part on the bus must survive the clamp voltage $V_C$,** not only the standoff: buck VIN, driver VM, half-bridge and power-path $V_{DS}$, bulk electrolytic and MLCC ratings. E.g. SMBJ15A: $V_{RWM}$ 15 V > 13.5 V; $V_C$ 24.4 V < 30 V (`docs/design-calcs.md`).
- SMBJ-class parts clamp at about 1.6 × $V_{RWM}$ at rated pulse current (SMBJ15A: 24.4 / 15 [LF-SMBJ]). Treat the ratio as a *rule of thumb* for other families and read the part's own table.
- **Energy.** The TVS absorbs what the bulk cannot during regeneration with the switch off or the fuse open (§6.7). Compare with its pulse rating at the real pulse width.

### 2.5 Fusing

- A fuse is a **fire backstop**. Electronic limits act first: the driver trip, the firmware I²t model, the logic UVLO.
- **Derate the continuous current** per the fuse datasheet (e.g. 1.2 A continuous within the 1206FA family's 75 % derating, `docs/architecture.md`). Check recovery bursts on the time-current curve (e.g. 105 % for ≪ 1 s is held ≥ 4 h; 250 % opens within 5 s).
- **Breaking capacity ≥ the prospective short-circuit current** $V_{bat,max} / (R_{int} + R_{leads})$. LiPo packs have low internal resistance, so this check matters: e.g. 12.6 V / 60 mΩ ≈ 210 A *(derived)* against 300 A at 24 V (`bom/parts.csv`). The 60 mΩ pack resistance is an **ASSUMPTION** (`simulation/common.py`).
- **Voltage rating** ≥ $V_{abs}$.

### 2.6 Under-voltage and battery monitoring

- **The board protects the pack** when there is no BMS (D-003: external balance charger, no BMS):
  - a hardware UVLO, e.g. the buck's EN divider: start 9.11 V, stop 8.47 V ≈ 2.8 V/cell, hysteresis ≥ 0.5 V (D-019, [SLUSEA4] §9.3.6);
  - a firmware undervoltage disarm set **above** it (e.g. ≈ 9.5 V under load, S3). The firmware must act while balancing; a hardware cut-off mid-balance drops the robot.
- **Sag.** $V_{bus} = V_{OCV} − I_{bus,pk}(R_{int} + R_{path})$ for the oldest, coldest pack. Check it against every load's minimum and the UVLO (S3: 9.0 V OCV, 4 A step → 8.10 V, above the 8.0 V driver minimum, below the logic UVLO).
- **Divider to the ADC:**
  - $V_{abs}$ maps below the ADC reference (e.g. 13.5 V → 2.87 V < 3.3 V);
  - source impedance below the ADC's $R_{AIN,max}$ (e.g. 21.3 kΩ < 50 kΩ, DS11929 Table 73);
  - charge-bucket capacitor ≥ 20 × the ADC sampling capacitance, C0G or X7R [SBAS788A];
  - settling to ½ LSB takes $(N+1)\ln 2 \cdot τ$, ≈ 9 τ at 12 bits [SBAA173A];
  - fault current into the pin limited by the top resistor (≤ 5 mA unless the datasheet says otherwise [MT-036]);
  - an error budget with resistor tolerance, reference and ADC TUE. 1 % resistors alone give ±1.57 % here, so ±50 mV/cell needs per-board calibration (S5: 109 mV raw → 38 mV calibrated, HW-PWR-006).

---

## 3. Logic rails: buck + LDO

- **Topology.** A buck takes the large step from the battery efficiently. An LDO after it removes the buck's switching ripple and the motor bus's ripple before the radio supply. ST's VDDRF ripple limit is 5–15 mV p-p depending on frequency [AN5165].
- **Input range.** Buck VIN recommended maximum ≥ $V_{abs}$; absolute maximum ≥ $V_C$ (§2.4). UVLO through EN above the pack-protection point (§2.6).
- **Fixed frequency near a radio.** Forced PWM (FCCM) keeps the spurs at known frequencies at every load; PFM at light load moves them with the load (e.g. D-018). Every clock below 83.5 MHz has harmonics inside 2400–2483.5 MHz [rf-layout §6] *(derived)*, so layout and placement set the spur level, not the frequency choice alone.
- **Inductor.** Ripple ratio per the converter's guidance (e.g. ≥ 10 % of the rated current for slope compensation [SLUSEA4] §10.2.2.7). Check $I_{sat}$ against the peak, and state what a hard short does.
- **Capacitors.** Use the **effective** capacitance at the DC bias (e.g. 2 × 22 µF 0805 → ≈ 13 µF at 5 V, S4), and check it against the datasheet's minimum for loop stability.
- **Buck dynamics.** If the vendor model does not run, verify with the datasheet's design equations and make the load step a bench item. Never invent compensation values for a model (D-023).
- **LDO:**
  - dropout at the lowest intermediate-rail voltage;
  - dissipation $(V_{in} − V_{out}) \cdot I$ and $T_J = T_A + P \cdot R_{θJA}$ (e.g. 0.20 W → +45 °C at 231 °C/W [SBVS320A] §6.4);
  - output capacitor type and minimum effective value per the datasheet;
  - PSRR at $f_{sw}$ and at $f_{PWM}$ (S4: 3V3 ripple < 1 mV p-p).
- **Sequencing and back-powering.** An intermediate 5 V rail rises before the MCU's 3.3 V. Anything it powers that drives MCU pins (encoders, expansion) can back-power the MCU. STM32 FT pins accept ≤ 3.6 V while VDD = 0, and no positive injection [AN4899]. Fix it at the interface (§7.3).
- **Power budget.** One table per rail, with datasheet maxima; replace every **ASSUMPTION** before freezing (e.g. `docs/architecture.md`). Include the expansion allowance, the buzzer and LED peaks and the radio's TX current.
- **Branches that leave the board** (encoder supply, expansion power) go through a current limit (PTC, resistor or load switch), so a shorted cable cannot pull the logic rail down (e.g. F601, 100 mA PTC).
- **Layout.** Follow the regulator datasheet's layout section exactly: input capacitor at the VIN/GND pins, minimal switch node, FB divider at the IC with the sense taken at the output capacitor, nothing under the switch node on any layer [power-pcb-layout §3.1, §3.3].

---

## 4. MCU support

### 4.1 Supplies and decoupling

- **100 nF per VDD pin plus ≥ 4.7 µF bulk** [AN4488], or exactly the datasheet's figure (e.g. DS11929 Fig. 16).
- **Analog supply and reference:** ferrite + 1 µF + 10–100 nF [AN4488]. A ferrite loses up to 90 % of its inductance at 50 % of rated current: design to about 20 % of rated current and damp the bead–capacitor resonance [ADI-FB].
- **On-chip SMPS:** inductors and capacitor exactly per the datasheet (e.g. 10 µH + 10 nH series + 4.7 µF, DS11929 Table 6). The VDDSMPS capacitor's ESL must be < 2.0 nH on QFN [AN5165]. Precision ADC reads may need SMPS bypass (`docs/firmware-interface.md`).
- **Backup domain without a battery:** VBAT to VDD with 100 nF [AN4488].
- **Placement:** each capacitor on the IC's side, next to its pin, with its own via; smallest value nearest the pin [power-pcb-layout §3.9]. Radio-supply capacitors never share a ground via [SWRA640].

### 4.2 Clocks

- **Load capacitors:** $C_L = C_1 C_2/(C_1 + C_2) + C_{stray}$; state the stray convention [AN2867].
- **Oscillation margin** $g_m / g_{m,crit}$ > 5 for the HSE and > 3 for the LSE; drive level ≤ the crystal's rating [AN2867].
- **32 kHz crystals:** low $C_L$ (≤ 7 pF) [AN2867].
- **BLE budgets:** ±50 ppm on the RF clock (initial + temperature + ageing + pulling) and ±500 ppm on the sleep clock [rf-layout §6].
- **Pick the crystal from the vendor's reference list** with a $C_L$ the on-chip trim is centred on (e.g. D-017: the first choice failed DS11929 Table 52 with $C_L$ 10 pF and ±30 ppm).
- **On-chip trim** (STM32WB HSETUNE ≈ 1 ppm/step): trim a sample of boards, apply the median, store it in OTP. Measure with a counter better than 0.1 ppm, not an oscilloscope [AN5042].
- **Layout:** crystal at the pins, short symmetric loop, no vias on the clock traces, ground straight to L2, away from the SMPS and the RF path, no GPIO nearby [AN5165][ESP-PCB].

### 4.3 Reset, boot and debug

- **NRST:** STM32 has an internal pull-up; add only the 100 nF the vendor recommends [AN4488], and bring reset to the debug header.
- **BOOT pin never floats** (10 kΩ pull-down [AN4488]); bootloader entry reachable from a button or pad.
- **Debug:** the vendor's standard connector (e.g. STDC14: SWD + virtual COM port [UM2448]). Record what pin sharing costs: e.g. no SWO because PB3 is SPI1_SCK; JTAG off because PA15 is a chip select (`docs/pinmap.md`).
- **An SMD debug connector's land pattern comes from the connector maker's drawing,** not a generic header footprint (Phase 1 open item).
- **Interfaces against timers.** Check alternate-function conflicts before adding an interface: e.g. no USB, because the bridge timer's fourth channel exists only on USB_DM (D-009).

### 4.4 Pins and the safe state

- **Unused pins** in analog mode, set by firmware [AN4899].
- **Off-board pins:** series R or RC, a clamp at the connector, and injection inside the limits: −5 mA per pin, about 25 mA total, no positive injection on FT pins [AN4899] (§7).
- **The reset state is a design input.** During reset and until firmware configures them, MCU outputs are high-impedance. Every actuator control needs a defined level from an internal or external pull, chosen so the hardware is safe:

  | Signal | Safe level at reset and brown-out | Board example |
  |---|---|---|
  | Bridge inputs | low: outputs off | Driver's internal pull-downs on AIN/BIN [SLVSC40] |
  | Driver sleep / enable | asleep | SLEEPn 10 k pull-down (no internal pull) |
  | Each SPI chip select | deselected | Active-high SCS internal pull-down; flash /CS and IMU nCS pull-ups |
  | Buzzer, LED data and other loads | off / idle | LED data 10 k pull-down at the level shifter input (D-035) |
  | Driver fault → timer break | armed in hardware | nFAULT on TIM1_BKIN and EXTI4 (HW-DRV-003) |

- **Hardware fault path.** The driver's fault output reaches a timer break input, so all bridge inputs tri-state with no firmware involved (HW-DRV-003).
- **Coils** (buzzer, relays): flyback diode [mcu-circuit-design §11]. Check peak drive against the part's rating.
- **Addressable LEDs** (WS2812-class):
  - their data V_IH scales with their supply (0.55–0.7 × VDD), so a 3.3 V GPIO driving a 5 V LED has little or no margin; use a 5 V buffer with a TTL-level input (e.g. D-035: 2.75 V needed vs 2.9 V V_OH; SN74AHCT1G125);
  - keep the data line low in reset with a pull-down at the buffer input, and terminate at the source;
  - one 100 nF per LED at its VDD pin (part datasheet);
  - size the supply for every LED at full white (e.g. 12 × 36 mA = 432 mA); brightness limits are a firmware choice, not a protection.
- **Buttons:** 100 Ω series plus an input RC [mcu-circuit-design §11].

---

## 5. 2.4 GHz RF

### 5.1 Match and filter

- **The chip-side network is both match and harmonic filter.** Use the vendor's, e.g. the MLPF IPD for STM32WB [AN5165]. Pick the IPD variant for the MCU's package; asymmetric IPDs carry a **direction mark** and fail if fitted backwards [AN5165].
- **The trace from the RF pin to the network is part of the match.** Copy its geometry exactly (e.g. 200 µm wide, 104 µm gaps, 1.5 mm long, DS12804 Fig. 13) [AN930.2][AN5165].
- **Shunt parts:** ≥ 2 ground vias each, straight to L2 [AN5165][AN5948]. Top pour 0.3–0.6 mm from the match [AN928.2].
- **Parts:** C0G, self-resonance ≥ 2 × the operating frequency [AN91445]. A change of case size or vendor retunes the network [NWP-017].

### 5.2 The 50 Ω line

- **50 Ω wherever the line is longer than λ/16** [AN928.2]: about 7.7 mm in free space at 2.45 GHz *(derived)*.
- **Grounded coplanar waveguide** is preferred: gap smaller than the substrate height, ground pour wider than the gap, width and gap constant [AN91445]. Keep L1–L2 ≤ 0.8 mm [AN928.2].
- **Recalculate for the stack-up.** A reference board's width is 50 Ω only on its own stack-up: DS12804's 450 µm line on a 1.5 mm 2-layer board is about 30 Ω over a 0.21 mm prepreg (`docs/rf.md`). Confirm with the fab's calculator and order impedance control.
- **No vias, stubs, branches or test points** on the line; 135° or curved bends; nothing on L2 under it but ground [ESP-PCB][AN91445][AN5165].
- **Via fence at 1.0–1.3 mm pitch** along the line and board edges [AN928.2][AN5165][AN91445].

### 5.3 Antenna

- **Copy a published design exactly,** for the same thickness and εr. Thicker board → shorten it; thinner → lengthen it [SWRA117][AN1088].
- **Place it at the edge or corner farthest from motors, cables and switchers** [AN91445], with a **keep-out on all layers**: no copper, parts, screws or silkscreen [AN91445]. No ground under the antenna unless its maker shows it [AN5165][AN1088].
- **IFA edge distances:** shorting arm ≥ 1.0 mm and radiating trace ≥ 0.5 mm from the board edge [AN1088].
- **The ground plane is half the antenna.** A *rule of thumb* is ≥ λ/4 (about 3 cm) of ground [EZ-GND]; a robot plate exceeds it easily.
- **Near field:**
  - no metal near it: screws, bumpers, the battery, the bracket, motor cans;
  - a battery behind the antenna acts as ground [AN5165];
  - cables must not cross it [AN91445].

  Published clearances are 4–5 mm for chip and module antennas [AN91445][AN6305]. For a PCB IFA, about 5 mm is an **ASSUMPTION** that the VNA tuning confirms.
- **Falls.** Bumpers keep the antenna edge from being the first contact (HW-MEC-004); use non-metallic hardware near the antenna and the NFC coil.
- **Tuning footprint:** a pi at the feed, 0 Ω series fitted, shunts DNP; fit at most two parts in the end [AN1088]. Target SWR ≤ 2 across 2400–2483.5 MHz [NWP-017].
- **Tune in the final assembly,** with battery, motors and wheels fitted: surroundings move the resonance (a plastic enclosure lowers it by 100–200 MHz [AN91445]).
- **Conducted test port:** a DNP U.FL off a 0 Ω whose pad sits on the line, so the stub is the pad alone; all layers clear under the U.FL [ESP-PCB].

### 5.4 Coexistence with switchers and motors

- **On-chip SMPS** is the most common sensitivity killer: a poor layout costs > 5 dB; diagnose by switching it off [SWRA640]. Inductor at the pins, small loop, oriented orthogonal to the RF line [AN5165].
- **Board switchers and motor leads** go as far from the antenna as the floorplan allows; the noisiest zone sits at the opposite edge (e.g. D-029: antenna at the top edge, bridges at the bottom, buck ≈ 50 mm away, `docs/rf.md`).
- **Clock harmonics:** a 32 MHz crystal lands on 2432 and 2464 MHz [rf-layout §6]. Keep the crystal loop tight and away from the antenna.
- **Brushed motors** radiate broadband commutation noise through their leads. Provide DNP suppression footprints at the motor connector (*rule of thumb*; e.g. the DNP RC on the motor sheet).
- **GPIOs never under** the RF line, the antenna or the crystal [AN928.2].
- **Certification.** If the board is not certified, say so (e.g. D-007). If it will be, plan a pre-compliance scan: the 2nd and 3rd harmonics fall in restricted bands [CFR-15.205].

---

## 6. H-bridge gate drive & current sense

### 6.1 Topology and decay

- **Gate driver + external half-bridges** scale current independently of the driver IC. An integrated-FET driver is simpler where its $R_{DS(on)}$ and thermal limits suffice.
- **PWM with slow decay** (both low sides on during the off time) gives torque close to proportional to duty and low ripple. Fast decay returns energy to the bus every period (§6.7).
- **Ripple:** $ΔI_{pp} = V_{bus} D (1 − D) / (L \cdot f_{PWM})$, largest at D = 0.5: e.g. 12.6 V, 1 mH, 25 kHz → 126 mA (S0, S2). Keep the PWM period well below $τ_e = L/R$ (HW-DRV-007), and $f_{PWM}$ above the audible band.
- **Low-voltage motors on a higher bus:** firmware caps the average duty (e.g. a 7.4 V motor on 3S, duty ≤ 7.4 / $V_{bat}$, D-027). The hardware still sees the full bus on every edge.
- **Size the trip and the motor from the plant, not from the motor label** (S0: trips of 1.0–1.5 A recover only 12–18° of tilt; 2.0 A recovers 21.6–23°).

### 6.2 FET selection

- $V_{DS}$ ≥ $V_C$ plus the switch-node overshoot (S2 criterion: overshoot < 20 % of VM).
- $V_{GS}$ abs max above the driver's gate voltage; $R_{DS(on)}$ specified at that gate voltage.
- Total gate charge × $f_{PWM}$ × number of FETs within the driver's gate-supply budget.
- **Dual-FET packages** (one half-bridge each) keep the phase node short.
- **Body diode** carries the dead-time current; its $V_f$ sets the phase node's negative swing (§6.3).

### 6.3 Dead time and freewheeling

- **Dead time** ≥ turn-off delay + fall time at the configured gate current, with margin. Verify no shoot-through across corners in simulation (S2: 850 ns, none found).
- **The phase node goes negative.** During dead time the motor current freewheels through the low-side body diode, so the phase node sits at −$V_f$. Check it against the driver's phase-pin absolute minimum: S2 found −0.73 V for ≈ 3 µs every period against −0.6 V ([SLVSC40] Abs Max).
  - Fix: a Schottky from GND to each phase node, at the pins (e.g. SS34 → −0.36 V, D-022), or FETs with an integrated Schottky, or a driver rated for the swing.
  - Ringing adds to the plateau: S2 shows −0.67 V for 3 ns with a 5 nH hot loop and −1.07 V for 12 ns at 15 nH. Layout target ≤ 5 nH; rerun with extracted parasitics after layout (S2).

### 6.4 Gate drive: charge pump, bootstrap, gate resistors

- **The high-side gate needs a supply above the bus.**
  - **Charge pump:** allows 100 % duty. Its flying and storage capacitors are rated ≥ VM + 12 V (e.g. 25.5 V at 13.5 V, [SLVSC40] p.3–4). Its current budget limits $Q_g \cdot f_{PWM}$.
  - **Bootstrap:** the low side must conduct every period to recharge it, so duty stays below 100 %. $C_{BOOT} ≥ Q_{G,total} / ΔV_{BOOT}$ [SLUA887]. Capacitor next to BOOT/SW, diode next to the VCC capacitor [power-pcb-layout §3.2].
- **Gate current sets the edge rate:** switching time ≈ $Q_{gd} / I_G$ [SLUP169]. Faster edges cut switching loss but ring: S2 measured ≤ 0.2 V overshoot at the lowest drive strength and +2.7…+5.5 V at the highest, with 21.8 V on the low-side FET. At 25 kHz the switching loss is small, so drive gently (D-022).
- **Gate resistor footprints at the FET** (0 Ω by default) for edge-rate trim; the gate loop routed as a pair with its return: the phase node for the high side, source/GND for the low side [power-pcb-layout §3.2].
- **Gate hold-off when unpowered:** if the driver does not hold the gates low with its supply off, add a gate-source pull-down at the FET.

### 6.5 Current sense

- **Low-side shunt** between each bridge's low-side sources and GND. The sense amplifier gain and the DAC set the trip: e.g. TORQUE = 256 × ISGAIN × R × $I_{trip}$ / 2.75 V = 186 at 2.0 A, 50 mΩ, ISGAIN 20 ([SLVSC40] Eq. 1; REPORT S0). Choose R so the trip spans from below the rated current to stall inside the DAC's range (HW-DRV-006).
- **Shunt rating:** $I_{trip}^2 R$ (e.g. 0.2 W in a 1 W part), pulse rating, tempco. Sense voltage at the trip within the amplifier's input range (2 A × 50 mΩ = 0.1 V *(derived)*).
- **Kelvin connection:** taps from the inner pad edges, routed as a tight pair, filter at the amplifier, no load current in them [power-pcb-layout §3.6]. Keep the Kelvin net distinct from GND in the schematic with a net tie (e.g. NT501/NT502).
- **Sense filter:** symmetric, ≤ 500 Ω, matched 1 % ([SLVSC40] Fig. 6). Fit-later footprints (0 Ω fitted, capacitor DNP) cost nothing.
- **Blanking time** ≥ the sense settling after each edge (e.g. TBLANK ≥ 1.2 µs, `docs/design-calcs.md`).
- **The trip is a peak (chopping) limit.** The motor's continuous rating is thermal and needs an I²t model in firmware (D-014, D-027).

### 6.6 Hot loop and bus capacitors

- **Hot loop:** bus HF capacitor → high-side FET → low-side FET → shunt → capacitor GND. Make it the smallest physical loop, with solid L2 directly under it [power-pcb-layout §3.1]. The 100 nF–1 µF HF capacitor sits closest; the bulk comes after.
- **Bulk ripple current:** at most $I_{C,rms} = I_{bus}\sqrt{D(1−D)}$ if the capacitors take all of it [SLTA055]. MLCCs and the pack share it, so simulate the split (S3). Compare with the electrolytic's rating at $f_{PWM}$ and temperature. E.g. S3: 0.88 A rms during recovery bursts against a 0.57 A rating, accepted as a time-averaged thermal limit enforced by the firmware's I²t model.
- **Bridges on one timer switch in phase,** so their bus currents add. Phase-shifting the two bridges lowers the bulk ripple (*rule of thumb*; simulate before relying on it).
- **MLCC DC-bias derating** at the bus voltage.

### 6.7 Regeneration and bus pumping

- **When energy comes back.** Whenever a motor's back-EMF exceeds the average voltage the bridge applies (deceleration, a commanded reversal, the robot pushed or rolling downhill), a synchronous bridge returns current to the bus.
- **Where it goes.** Into the pack if the input path conducts both ways (§2.2). Otherwise into the bulk capacitance, $V_2 = \sqrt{V_1^2 + 2E/C}$ *(derived from $E = ½CV^2$)*, then into the TVS.
- **Worst case: switched off, fuse open or connector bouncing while the wheels turn.** The body diodes rectify the back-EMF onto the bus (HW-PWR-004). S1: pushed at 20 V back-EMF → VBAT 17.84 V (TVS onset) and 34 mJ in the power-path FET; this needs ≈ 3.2 m/s here, above the design speed.
- **Pass criteria:** peak bus voltage below the lowest absolute maximum on the bus (HW-PWR-004: < 24 V); TVS energy inside its rating.
- **A full pack absorbing regeneration** is briefly pushed above its charge voltage. Short bursts are normal; sustained regeneration needs a firmware limit or a brake chopper (*rule of thumb*).

### 6.8 Protection and safe state

- **Driver protections** (over-current via $V_{DS}$ monitoring, UVLO, over-temperature) set over SPI; the fault pin to the timer break (§4.4).
- **Motor connector rated for $I_{trip}$ continuously** (HW-DRV-009). E.g. a 2 A PH contact equals the 2.0 A trip (D-028): no margin, so the firmware I²t model also protects the connector.
- **Motor outputs leave the board** but the bridge clamps them: body diodes to the bus and GND, the bus TVS takes the energy. No separate ESD part is usual; record it as a waiver (`docs/checklists/phase1.md`).
- **FET junction temperature** < 100 °C at the worst continuous current and 40 °C ambient (HW-DRV-008; S2: ≈ 44 °C).

---

## 7. Encoders & external-cable inputs

### 7.1 Protection at the connector

- **ESD part at the connector**, signal routed connector → TVS pin → IC (pass-through), **no via between connector and TVS**, a ground via right at the TVS ground pin into the solid plane. 0.25 nH of extra path adds about 10 V at 4 × 10¹⁰ A/s [SLVA680].
- **Level:** pick an IEC 61000-4-2 level (contact 2/4/6/8 kV) [mcu-circuit-design §7]. TVS working voltage ≥ the signal swing, clamp below the protected pin's limit, capacitance within the edge budget (e.g. ≈ 0.5 pF/channel, `docs/checklists/phase1.md`).
- **Keep the connector-to-TVS area free** of unprotected traces, and don't run them parallel to protected ones [SLVA680].

### 7.2 Filtering and thresholds

- **Series R** 50–150 Ω on cable lines [mcu-circuit-design §6]; **RC** 100 Ω–1 kΩ with 1 nF–0.1 µF [AN4747].
- **Corner frequency** well above the maximum channel rate (≥ 2 × margin, HW-SNS-004). Quadrature phase error from RC and threshold skew < 25 % of a quarter period at maximum speed (S5 criterion, `docs/plan.md`).
- **Schmitt-trigger inputs.** Hysteresis rejects slow and noisy edges from long cables next to motor leads. Check the thresholds at the buffer's supply (e.g. $V_{T+}$ ≤ 1.87 V at 3.3 V [SCES470D]).
- **Open-collector encoders:** the pull-up and the total capacitance set the rise, $τ = R(C_{filter} + C_{cable})$, which limits the line count (S5: 2.2 kΩ with 1.1 nF → τ ≈ 2.4 µs; 21 % phase error at 500 lines, 43 % at 1000).
- **Unused buffer inputs tied to a level;** floating CMOS inputs draw current and oscillate [SCBA004] (e.g. the third buffer input grounded, D-028).

### 7.3 Back-powering

- The encoder supply is often 5 V and rises before the MCU rail (§3). A push-pull encoder output then drives MCU pins while VDD = 0.
- **Fix:** a buffer powered from the MCU rail, with 5 V-tolerant inputs and $I_{off}$ (partial power-down) (e.g. D-012), or a series resistor that keeps the injection inside the MCU's unpowered limits [AN4899].
- **Verify:** no current into MCU pins while 3V3 = 0 (S5 criterion).

### 7.4 Supply on the cable

- **Current-limited** (PTC, resistor or switch), with local decoupling at the connector.
- **Voltage selectable** through 0 Ω options when the encoder type is not fixed (e.g. D-016).
- Budget per encoder from its datasheet (e.g. 10 mA per Hall board, an **ASSUMPTION** in `docs/architecture.md`).

### 7.5 Cables, connectors and timers

- **Confirm the pinout against the purchased cable,** pin 1 to pin 1 (`docs/layout.md` open item); keyed housings.
- **Motor power and encoder in one connector:** the motor pins' copper stays away from the encoder traces **on every layer** (`docs/power-map.md`).
- **Timer limits:** the ×4 count rate within the timer's input filter and kernel clock (reference manual), e.g. LPTIM in encoder mode.
- **Missing index channel:** wire the pin to a defined level and report the requirement the motor cannot meet (D-028).

---

## 8. IMU placement & mechanical coupling

- **What the accelerometer reads.** At distance $r$ above the axle it measures gravity plus the tangential $r\ddot{θ}$ and centripetal $r\dot{θ}^2$ terms (and the base acceleration). Near the axle minimises them; far from it needs compensation in firmware (`docs/mechanical.md`). E.g. D-029 puts the IMU beside the MCU, about 90 mm above the axle, and the firmware subtracts $r\ddot{θ}$.
- **Publish its position and axis map** in body coordinates (x forward, y left, z up; HW-SNS-002). Silkscreen the package axes.
- **Rigid, stress-free mounting:**
  - on the plate itself, not on a tab, slot edge or near a screw that bends the board;
  - no large insertion components (buttons, connectors, shield cans) within 6 mm of the MEMS gyro [PS-MPU-6000A];
  - no active traces directly under the package on adjacent layers [PS-MPU-6000A].
- **Drive-frequency coupling.** That InvenSense family drives its gyro proof masses at 27–33 kHz (±3 kHz) [PS-MPU-6000A]. A 25 kHz motor PWM and its mechanical whine sit next to that band: keep bridge and motor copper away, and check the drive frequencies of the part actually fitted (§16).
- **Vibration.** Motors and gearboxes shake the plate. Mount the IMU on the stiffest region, away from the bracket's free edges; set the IMU's digital low-pass filter and sample rate in firmware so vibration does not alias.
- **Shock.** Falls are part of normal use. Check the part's shock rating (MPU-6500: 10,000 g) and set the accelerometer range (±2 to ±16 g) for the firmware's needs [PS-MPU-6500A].
- **Heat.** Gyro bias drifts with temperature; keep the IMU away from the LDO, buck, FETs, shunts and buzzer.
- **Magnetometer, if fitted:** away from motor magnets, the steel bracket and the battery current loop.
- **Electrical:**
  - decoupling and regulator capacitors exactly per the datasheet;
  - chip select held inactive through reset, so the part stays in SPI mode, and its I²C interface disabled in firmware (`docs/firmware-interface.md`);
  - a dedicated SPI bus for the latency-critical burst (D-005);
  - data-ready on a unique EXTI line.
- **Quiet zone:** keep switch nodes and motor copper away (this board's plan uses ≥ 15 mm, `docs/plan.md`; *rule of thumb*).

---

## 9. NFC coil design & tuning

- **Resonance:** $f_0 = 1 / (2π\sqrt{L (C_{TUN} + C_{par})})$. The tag provides $C_{TUN}$ (e.g. 28.5 pF typical, DS13519 RF characteristics), so the coil's inductance is the design variable (e.g. 4.25 µH → 14.2 MHz with 1 pF parasitic, `scripts/nfc_coil.py`).
- **Design slightly high.** Added capacitance and nearby metal only pull the resonance down. A DNP C0G trim capacitor across the coil terminals brings it to 13.56 MHz after measurement (`docs/nfc.md`) [AN2866].
- **Inductance by two methods:** a segment sum [Greenhouse] and the modified Wheeler formula [Mohan], including the underpass. Agreement within a few percent is the sanity check (e.g. −0.2 %).
- **Geometry:** the largest area the board allows; track and gap at the fab's design values; one underpass on the far layer; the terminals on the tag's side.
- **Metal is the enemy.** Copper pours, ground planes, the battery and screws inside, under or near the coil carry eddy currents that lower $L$ and $Q$:
  - keep-out on all layers inside and around the coil (this board: 1 mm, **ASSUMPTION**);
  - metal ≥ 5 mm from it (this board, **ASSUMPTION**);
  - a ferrite sheet where metal cannot be avoided [AN11276].
- **Placement:** at an edge or corner a phone can reach; away from the 2.4 GHz antenna keep-out (this board: ≥ 5 mm); non-metallic hardware nearby (`docs/mechanical.md`).
- **Tag connections:** the tag right at the coil terminals, the two antenna traces short and paired; unused energy-harvest output per the datasheet; the GPO (open drain) pulled up to a unique EXTI pin (e.g. D-030).
- **Verify** with a loop probe and VNA for $f_0$, then a phone read-range test on the assembled robot (HW-IF-004, B).

---

## 10. Memory & expansion buses

### 10.1 I²C

- **Pull-ups:** $R_{min} = (V_{CC} − 0.4\,V)/3\,mA$, $R_{max} = t_r / (0.8473 \cdot C_b)$, with $t_r$ = 1000 / 300 / 120 ns (Standard / Fast / Fast+) and $C_b$ ≤ 400 pF [SLVA689A]. E.g. 2.2 kΩ inside a 967–3541 Ω window at 100 pF.
- **Estimate $C_b$ including the off-board part:** cable and external device (`docs/nfc.md`: 85 pF from **ASSUMPTION**s of ≈ 10 pF per pin, ≈ 1 pF/cm and 30 pF per Qwiic device).
- **Expansion modules often carry their own pull-ups.** The parallel combination must stay ≥ $R_{min}$; check each module's schematic.
- **Address plan:** a table of every on-board address, including devices that take several (e.g. EEPROM 0x50, NFC tag 0x53 and 0x57, `docs/nfc.md`). Avoid the reserved 0x00–0x07 and 0x78–0x7F [UM10204], and publish the addresses external devices must avoid.
- **EEPROM:** write-control pin at a defined level; page size and write-cycle time in firmware (e.g. 32-byte pages, 5 ms, `docs/firmware-interface.md`).
- **Expansion connector:** standard pinout (Qwiic: 1 GND, 2 3.3 V, 3 SDA, 4 SCL [QWIIC]); ESD at the connector; a power allowance in the budget. Plugging a module onto a live 3.3 V rail dips it through the module's capacitance; budget it or add a series limit (*rule of thumb*).

### 10.2 SPI sharing

- **Every chip select held inactive through power-up** by a pull to its inactive level: pull-up for active-low, pull-down for active-high (e.g. flash /CS held at VCC through power-up, [W25Q16JV] power-up timing).
- **Shared MISO:** open-drain outputs need a pull-up sized for the clock (e.g. 2.2 kΩ with 30 pF → τ ≈ 66 ns, SPI ≤ 4 MHz, `docs/design-calcs.md`); every other device tri-states when deselected.
- **Mode and maximum clock per device,** applied by a per-device prescaler in firmware (e.g. driver ≤ 4 MHz, flash ≤ 133 MHz, `docs/firmware-interface.md`).
- **Source termination** on SCK, 0–33 Ω at the MCU [mcu-circuit-design §9]; short stubs.
- **Keep latency-critical sensors off a bus shared with slow devices** (D-005).
- **Flash:** /WP and /HOLD at defined levels; wait the power-up delay before the first write (e.g. 5 ms, `docs/firmware-interface.md`).

---

## 11. PCB as chassis: mechanics

- **Map the load paths:** motor torque reaction and wheel loads through the bracket, the battery's mass, the impact of falls. Bolt them into areas with no parts and no copper a clamped steel face can short (e.g. the bottom strip: no parts, no B.Cu, D-026).
- **Mechanical keep-outs are DRC rule areas,** not notes: antenna band, NFC coil, bracket strip, battery footprint (e.g. no THT pins through the battery side, D-025; `docs/layout.md`). A rule area survives edits; a note does not.
- **Fastener holes:**
  - NPTH for chassis fasteners unless a ground bond is intended;
  - outer-layer copper keep-out ≥ the washer or head diameter (ISO 7089: 7 mm for M3, 5 mm for M2 [ISO-7089]);
  - hole-to-copper clearance so threads cannot cut into copper (this board's project rule: 0.5 mm, **ASSUMPTION**).
- **Metal chassis parts and ground.** Decide whether the bracket is isolated or bonded at one point beside the connector/TVS ground [interface-layout §2]. Never let it touch copper by accident: solder mask is not insulation under clamping force and vibration (*rule of thumb*).
- **One assembled side.** Single-side PCBA puts every SMD part on one face (e.g. D-015/D-025). The other face carries the bracket and the battery, so THT pins and clinched leads there need clearance from both.
- **Board flex cracks MLCCs.** Keep large-case MLCCs away from screw holes, connectors and the bracket edge, and orient them with the long axis along the likely bend line [MLCC-FLEX].
- **Vibration and heavy parts.** Place tall or heavy parts (electrolytics, inductors, connectors) near supports; stake them if needed. SMD connectors need mechanical hold-downs (*rule of thumb*).
- **Connector strain relief and access:**
  - cables that move with the wheels need a latch or a tie point;
  - plug from an edge that stays reachable with the battery, bracket and wheels fitted;
  - mating force on an SMD header goes into the board, so place it near a support;
  - the battery connector is through-hole for retention (e.g. XT30).
- **Falls:** bumpers on both faces at the top (HW-MEC-004); the battery cradle has a lip that takes a backward fall (`docs/mechanical.md`).
- **Mass and centre of mass are design outputs.** The plate is the pendulum body. Keep a mass budget (`mechanical/mass_budget.csv`), rerun sizing (S0) when the battery or heavy parts move, and feed the static lean to the firmware (e.g. ≈ 18°).
- **One mechanical origin** (e.g. the axle on the centreline) shared by the docs, the placement and the firmware: IMU position, wheel radius, track width.
- **Board thickness is also an RF parameter.** Changing it retunes the antenna (D-008 rejected 2.0 mm for that reason).

---

## 12. Thermal design

- **List every heat source:**
  - FETs: $I_{rms}^2 R_{DS(on)}(T_J)$ plus switching loss;
  - shunts, LDO, buck;
  - the TVS and the power-path FET during events;
  - electrolytic ripple heating;
  - the buzzer driver.
- **Junction temperature:** $T_J = T_A + P \cdot R_{θJA}$, with $R_{θJA}$ from the datasheet's copper-area curves, never the 25 °C rating [power-pcb-layout §3.7]. Take $R_{DS(on)}$ at temperature from the datasheet's normalised curve.
- **Exposed pads:** the datasheet's via pattern; otherwise 0.3 mm vias at 1.0–1.2 mm pitch, solid to the planes [power-pcb-layout §3.7].
- **Electrolytic capacitors:** life halves for every 10 °C rise [ELCAP-LIFE], and ripple current heats them (§6.6).
- **The battery lies against the board.** Keep the LDO, buck, FETs and shunts out from under it, and stay inside the pack's temperature rating (pack datasheet).
- **Sensitive parts** (crystals, IMU, references, electrolytics) away from hot ones [power-pcb-layout §3.7].
- **Verify at bring-up** with a thermocouple: a thermal soak and a switch-off while the wheels are pushed (`docs/plan.md` Phase 4; S1 bench item).

---

## 13. Layout & stack-up

### 13.1 Stack-up

- **4 layers:** L1 parts, RF and short power pours; L2 solid GND, never cut; L3 power pours and slow signals; L4 signals and GND fill (D-008, `docs/plan.md`).
- **The L1–L2 dielectric** sets both the 50 Ω width and the hot-loop inductance; thin helps both (≤ 0.8 mm for RF [AN928.2]).
- **State the inner copper weight** on the order; many fabs default to 0.5 oz inner [power-pcb-layout §3.5].

### 13.2 Priority order

1. **Mechanical anchors and rule areas.** The owner places the anchors and they are never moved (D-032, [power-pcb-layout §1]).
2. **Antenna and RF path** (§5).
3. **Hot loops:** bridges, buck, on-chip SMPS. Switch nodes minimal, nothing under them on any layer [power-pcb-layout §3.1].
4. **Kelvin pairs and gate loops** (§6.4, §6.5).
5. **Crystals** (§4.2).
6. **High-current copper:**
   - pours, not tracks, sized with IPC-2221: $I = k \cdot ΔT^{0.44} \cdot A^{0.725}$, A in mil², k = 0.048 external, 0.024 internal [IPC-2221]. E.g. 4.2 A at ΔT 10 °C needs 2.17 mm outer at 1 oz and 11.3 mm inner at 0.5 oz (`docs/power-map.md`);
   - ≥ I / 1 A vias (0.3 mm drill) at every layer change [power-pcb-layout §3.5];
   - no necks at pad entries or between pours.
7. **Connector ESD pass-through;** encoder traces away from motor copper on every layer (§7).
8. **IMU quiet zone and NFC keep-out** (§8, §9).
9. **Remaining signals;** GND stitching about every 5 mm along plane edges [power-pcb-layout §4] and 1–1.3 mm along the RF line.
10. **Test points** on the rails, PWM inputs, fault line, SPI, encoder outputs and the battery-sense node.

### 13.3 Rules

- **Clearance:** ≤ 30 V needs 0.1 mm external, uncoated [IPC-2221] Table 6-1; the fab's design values govern (e.g. 0.15 mm).
- **Return paths:** never route a signal over a gap in its reference plane [power-pcb-layout §3.4].
- **Quality bar:** 45° corners only; routed length / Manhattan ≤ 1.3 for most nets, flag > 1.6; ≤ 2 vias per connection; no slivers under 0.5 mm [power-pcb-layout §5].
- **Look at every copper layer** rendered on its own, plus each side [power-pcb-layout §6.4].

---

## 14. KiCad & JLCPCB practicalities

### 14.1 Parts

- **LCSC number on every BOM line;** basic parts before extended (extended parts add a per-part setup fee; check JLCPCB's current pricing).
- **Stock for the build quantity,** re-checked before each order and before a schematic freeze (`scripts/jlc_stock.py`). Reserve or pre-order thin-stock parts (e.g. the MCU and the driver, `docs/plan.md`).
- **The footprint matches the LCSC part's package exactly** (CLAUDE.md). Check:
  - package-variant suffixes and exposed-pad size;
  - pin 1, polarity marks (diodes, TVS, electrolytics) and the pad view (top or bottom, e.g. the buzzer, Phase 1 open item);
  - SOT-23 and SO-8 pinout variants for FETs;
  - connector pin 1 against cable pin 1;
  - the maker's land pattern over a generic library footprint (e.g. STDC14 SMT, Phase 1 open item).
- **DNP parts** marked DNP in the BOM and left out of the CPL.

### 14.2 Assembly outputs

- **CPL relative to the drill/aux origin.**
- **Rotations:** KiCad's footprint zero orientation and JLC's part models do not always agree. Check every part in JLC's placement preview and correct it with a per-part rotation offset (`docs/plan.md` Phase 4).
- **Single-side assembly:** every SMD part on the assembled side.

### 14.3 Fab

- **Order the fab's named stack-up** (e.g. JLC04161H-7628) with **impedance control** for the RF line, confirmed in the fab's calculator [JLC-IMP].
- **JLCPCB 4-layer minimums** [JLC-CAP], via `pcb-design-rules` §3, checked 2026-11-04:

  | Rule | Minimum | Typical design value |
  |---|---|---|
  | Track / space | 0.09 / 0.09 mm | 0.15 / 0.15 mm |
  | Via drill / diameter | 0.15 / 0.25 mm (surcharge below 0.30 mm drill) | 0.30 / 0.60 mm |
  | PTH annular ring | 0.15 mm | — |
  | NPTH drill | 0.50 mm | — |
  | Hole to hole | 0.20 mm | — |
  | Copper to edge | 0.20 mm | 0.50 mm |
  | Silkscreen text height | 1.0 mm | 1.0 mm |

- **Know the tightest rule** on the board and why it is there (e.g. the 0.10 mm RF1 clearance against the 0.09 mm floor, `docs/power-map.md`).

### 14.4 KiCad

- **ERC:** `PWR_FLAG` on rails driven from outside the schematic; Kelvin nets kept distinct with net ties; no-connect flags only where intended.
- **DRC with schematic parity;** refill zones before DRC and before plotting [power-pcb-layout §6.2].
- **Custom rules:** a custom constraint replaces the net-class value even when smaller. Never write a blanket clearance rule; condition each one on its net or class [pcb-design-rules §4].
- **Library footprints ignore the fab:** check thermal-via drills, PTH annular rings and mask webs [pcb-design-rules §6].
- **One source of truth per artefact:** the generated schematic until the first hand edit (D-020); the `.kicad_pcb` for placement from hand-off, with sync tools that only add (D-032).

---

## 15. Go/no-go checklist

A condensed list. The reviewer agent expands on it. Each line names the guide section that explains it.

**Requirements & process**
- [ ] Every HW requirement traced and given a method; S items cite a passing REPORT step; B items listed as open (§1.1).
- [ ] Pin map validated: bonding, alternate functions, unique EXTI lines, firmware parity (§1.1).
- [ ] Every firmware constraint from the hardware written in `docs/firmware-interface.md` (§1.1).
- [ ] The previous phase gate signed off by the user; this gate's criteria from `docs/plan.md` met (§1.2).

**Battery input**
- [ ] TVS after the reverse-polarity element; standoff ≥ $V_{abs}$; **every bus part survives $V_C$** (§2.1, §2.4).
- [ ] Input path conducts both ways when on, or regeneration handled another way (§2.2, §6.7).
- [ ] Power-path $V_{GS}$ inside the $R_{DS(on)}$ point at $V_{bat,min}$ and inside abs max at $V_{abs}$; Zener clamp fitted (§2.2).
- [ ] Hot plug simulated with the switch on and off: FET stays off when it should; inrush inside pulse rating, SOA and fuse $I^2t$ (§2.3).
- [ ] Fuse: continuous derating, breaking capacity ≥ prospective short circuit, voltage rating (§2.5).
- [ ] Off-state drain within budget; dividers after the switch (§2.1, §2.2).
- [ ] Hardware UVLO below a firmware disarm threshold; sag at the oldest pack ≥ every load's minimum (§2.6).
- [ ] Battery ADC: ratio, source impedance, charge bucket, settling, error budget with calibration (§2.6).

**Rails & MCU**
- [ ] Buck VIN abs max ≥ $V_C$; fixed frequency near the radio; effective capacitances after DC bias; layout per datasheet (§3).
- [ ] LDO dissipation and PSRR; radio-supply ripple inside the vendor's limit (§3, §5.4).
- [ ] Power budget uses datasheet maxima; off-board supply branches current-limited (§3).
- [ ] Decoupling and on-chip SMPS parts exactly per datasheet; VDDA filtered (§4.1).
- [ ] Crystals: $C_L$ maths, margin, drive level, ppm budget, trim plan (§4.2).
- [ ] NRST, BOOT, debug connector per vendor; debug land pattern from the maker's drawing (§4.3).
- [ ] Safe state at reset and brown-out: bridge inputs low, driver asleep, chip selects inactive, loads off, fault → timer break (§4.4).

**RF**
- [ ] Vendor match/filter with its direction; pin-to-filter trace copied geometrically; ≥ 2 vias per shunt part (§5.1).
- [ ] 50 Ω GCPW recalculated for the stack-up and confirmed with the fab; no vias, stubs or test points; 1.0–1.3 mm fence (§5.2).
- [ ] Antenna copied exactly, at the edge, keep-out on all layers, edge distances met, no metal in the near field (§5.3).
- [ ] DNP pi at the feed and a conducted test port; tuning planned in the final assembly (§5.3).
- [ ] SMPS loop at the pins and orthogonal to the RF line; switchers and motor leads far from the antenna (§5.4).

**Bridge & current sense**
- [ ] FET $V_{DS}$ ≥ $V_C$ + overshoot; $V_{GS}$ and gate charge inside the driver's budget (§6.2).
- [ ] Phase-node negative swing inside the driver's abs min, with clamps if needed; no shoot-through (§6.3).
- [ ] Charge-pump or bootstrap parts rated and placed; gate R and pull-downs at the FET (§6.4).
- [ ] Shunt value sets the trip range; power and pulse ratings; Kelvin taps; sense filter; blanking (§6.5).
- [ ] Hot loop minimal over solid L2; bulk ripple current inside rating or explicitly time-limited (§6.6).
- [ ] Peak bus voltage on regeneration and switch-off below the lowest bus abs max; TVS energy OK (§6.7).
- [ ] Motor connectors rated for the trip; FET $T_J$ < 100 °C at 40 °C ambient (§6.8).

**Cable inputs, IMU, NFC, buses**
- [ ] ESD at every connector, pass-through, no via before the TVS, ground via at the TVS (§7.1).
- [ ] Encoder RC corner ≥ 2 × the edge rate; phase error < 25 % of a quarter period; Schmitt thresholds; unused inputs tied (§7.2).
- [ ] No back-powering of the MCU from a rail that rises first (§7.3).
- [ ] Encoder supply current-limited; cable pinout confirmed against the purchased part (§7.4, §7.5).
- [ ] IMU rigid, away from stress points, connectors (≥ 6 mm), switch nodes and heat; no traces under it; position and axis map published (§8).
- [ ] NFC coil designed above 13.56 MHz with a DNP trim; metal keep-out on all layers; away from the 2.4 GHz antenna (§9).
- [ ] I²C pull-ups inside the SLVA689A window with the off-board load; address table published (§10.1).
- [ ] Every SPI chip select inactive through power-up; shared MISO handled; per-device clock limits recorded (§10.2).

**Mechanics & thermal**
- [ ] Mechanical keep-outs exist as rule areas; bracket contact area free of parts and copper (§11).
- [ ] Fastener holes NPTH with washer-sized copper keep-outs; metal chassis bonding decided (§11).
- [ ] MLCCs away from screws, connectors and bend lines; heavy parts near supports; connectors accessible and strain-relieved (§11).
- [ ] Bumpers protect the antenna edge; mass budget and S0 current with the placement (§11).
- [ ] Every hot part's $T_J$ from copper-area $R_{θJA}$; nothing hot under the battery or near the IMU and crystals (§12).

**Layout**
- [ ] Anchors untouched; L2 solid and never cut; switch nodes minimal with nothing under them (§13).
- [ ] High-current copper sized per IPC-2221/2152, inner weight stated, ≥ I/1 A vias per transition, no necks (§13.2).
- [ ] Quality bar met; every copper layer rendered and inspected (§13.3).

**Manufacturing (KiCad / JLCPCB)**
- [ ] ERC clean; DRC clean with schematic parity; zones refilled (§14.4).
- [ ] Rules inside JLC capabilities; tightest rule known; stack-up and impedance control on the order (§14.3).
- [ ] Footprints match the LCSC packages; LCSC numbers on every line; stock green for the build quantity; thin parts reserved (§14.1).
- [ ] CPL board-relative; rotations checked in JLC's preview; DNP parts excluded (§14.2).

---

## 16. Open items: assumptions & rules of thumb

Numbers and statements in this guide that are not backed by a primary source yet. Replace each with a measurement or a cited document, then remove it here.

| # | Item | Where | To close |
|---|---|---|---|
| 1 | **ASSUMPTION** Battery internal resistance 60 mΩ new / 150 mΩ aged, used for the fuse breaking check and sag | §2.5, §2.6 | Measure the pack (`simulation/common.py`) |
| 2 | *Rule of thumb* TVS clamp ≈ 1.6 × $V_{RWM}$ beyond the SMBJ family | §2.4 | Read each TVS's own table |
| 3 | **ASSUMPTION** ≈ 5 mm metal-free near field for a PCB IFA (published values are for chip and module antennas) | §5.3 | VNA on the assembled robot |
| 4 | *Rule of thumb* Brushed-motor suppression footprints at the motor connector | §5.4 | Radio sensitivity with motors running at bring-up |
| 5 | *Rule of thumb* Phase-shifting the two bridges lowers bulk ripple | §6.6 | Simulate in S3 before relying on it |
| 6 | *Rule of thumb* A full pack tolerates short regeneration bursts; sustained regeneration needs a firmware limit or chopper | §6.7 | Pack datasheet charge limits |
| 7 | **ASSUMPTION** Encoder supply 10 mA per Hall board | §7.4 | Encoder datasheet or measurement (`docs/architecture.md`) |
| 8 | Gyro drive frequencies (27–33 kHz) and the 6 mm component rule are from the MPU-6000/6050 product specification | §8 | Confirm the clauses in the fitted part's specification (PS-MPU-6500A) |
| 9 | *Rule of thumb* IMU ≥ 15 mm from switch nodes (this board's plan) | §8 | No primary source; keep as a placement target |
| 10 | **ASSUMPTION** NFC keep-out 1 mm around the coil and ≥ 5 mm to metal (this board's choices) | §9 | Phone read range and loop-probe $f_0$ on the assembled robot |
| 11 | **ASSUMPTION** NFC parasitic capacitance 1 pF | §9 | Measured $f_0$ replaces it (`docs/nfc.md`) |
| 12 | NFC metal and ferrite guidance cited from ST AN2866 and NXP AN11276, not read from this environment | §9 | Read both notes and cite sections |
| 13 | **ASSUMPTION** I²C bus capacitance: ≈ 10 pF per pin, ≈ 1 pF/cm, 30 pF per Qwiic device | §10.1 | Measure rise time on the bus with a module fitted |
| 14 | *Rule of thumb* Hot-plugging an expansion module dips the 3.3 V rail | §10.1 | Measure at bring-up, or add a series limit |
| 15 | **ASSUMPTION** 0.5 mm NPTH hole-to-copper clearance (project rule) | §11 | Fastener and washer drawings |
| 16 | *Rule of thumb* Solder mask is not insulation under a clamped steel part | §11 | Keep the copper keep-out; no source needed to be conservative |
| 17 | MLCC flex-crack placement guidance cited generically | §11 | Cite a specific Murata or KEMET document |
| 18 | *Rule of thumb* Staking heavy parts; hold-downs on SMD connectors; strain relief | §11 | Drop and vibration test at bring-up |
| 19 | Electrolytic life rule (×2 per 10 °C) cited generically | §12 | Cite the fitted capacitor's life equation |
| 20 | ST AN5165 and AN2867 rules are taken from the `rf-layout` and `mcu-circuit-design` summaries; st.com is unreachable from this environment (`docs/rf.md` open item 1) | §4, §5 | Read both notes before the layout freeze |
| 21 | JLCPCB capability numbers checked 2026-11-04; they change | §14.3 | Re-fetch jlcpcb.com/capabilities before ordering |

---

## 17. References

Verify every rating against the live datasheet or app note. The numbers here are for orientation and may change.

**Functional blocks.** This guide is component-agnostic: pick parts that meet each block's interface. A board's `docs/decisions.md` and `bom/parts.csv` list its concrete choices.
- **Battery input:** fuse with adequate breaking capacity; back-to-back P-FETs with a gate clamp and soft start; TVS after them; bulk + HF capacitors.
- **Logic rails:** forced-PWM synchronous buck rated above the TVS clamp with an EN UVLO; low-noise LDO.
- **MCU and radio:** wireless MCU with on-chip SMPS; vendor IPD match/filter; published PCB antenna copied exactly; DNP pi and conducted test port.
- **Motor drive:** gate driver with charge pump, sense amplifiers and a fault output; dual N-FET half-bridges; low-side shunts with Kelvin taps; phase-node Schottky clamps if the driver needs them.
- **Cable inputs:** low-capacitance ESD arrays; RC filters; Schmitt buffers with $I_{off}$; current-limited cable supplies.
- **Sensing and storage:** MEMS IMU on its own SPI bus; SPI NOR flash; I²C EEPROM; NFC tag with an internal tuning capacitor.

**Standards**
- **[IPC-2221]** IPC-2221, *Generic Standard on Printed Board Design*: conductor current formula; Table 6-1 spacing.
- **[IPC-2152]** IPC-2152, *Standard for Determining Current Carrying Capacity in Printed Board Design*.
- **[ISO-7089]** ISO 7089, *Plain washers, normal series*: outside diameters.
- **[UM10204]** NXP UM10204, *I²C-bus specification and user manual*: reserved addresses.
- **[CFR-15.205]** 47 CFR §15.205, restricted bands of operation.

**Datasheets (this board's parts, used as examples)**
- **DS11929** ST, STM32WB55xx datasheet (Fig. 16 decoupling, Table 6 SMPS, Tables 52/54 crystals, Table 73 ADC).
- **DS12804** ST, MLPF-WB55-01E3 datasheet (Fig. 13 land pattern).
- **DS13519** ST, ST25DV04KC datasheet (RF characteristics, device select).
- **[RM0434]** ST, STM32WB55xx reference manual (SYSCFG_EXTICR).
- **[SLVSC40]** TI, DRV8711 datasheet (Abs Max, Eq. 1, Fig. 6, p.3–4 external components).
- **[SLUSEA4]** TI, TPS62933 datasheet (§9.3.6 EN UVLO, §10.2.2 design, layout section).
- **[SBVS320A]** TI, TLV755P datasheet (§6.4 thermal, §8.1.1 capacitors).
- **[SCES470D]** TI, SN74LVC3G17 datasheet (thresholds, $I_{off}$).
- **[LF-SMBJ]** Littelfuse, SMBJ series datasheet.
- **[PS-MPU-6500A]** TDK InvenSense, PS-MPU-6500A-01, MPU-6500 product specification.
- **[PS-MPU-6000A]** TDK InvenSense, PS-MPU-6000A-00, MPU-6000/6050 product specification, Assembly section ("Trace Routing", "Component Placement").
- **[W25Q16JV]** Winbond, W25Q16JV datasheet (power-up timing).

**App notes**
- **[AN4488]** ST, *Getting started with STM32F4xxxx MCU hardware development*.
- **[AN4899]** ST, *STM32 GPIO configuration for hardware settings and low-power consumption*.
- **[AN2867]** ST, *Oscillator design guide for STM8 and STM32 microcontrollers*.
- **[AN5042]** ST, *How to calibrate the HSE clock for RF applications on STM32 wireless MCUs*.
- **[AN5165]** ST, *How to develop RF hardware using STM32WB MCUs*.
- **[AN5948]** ST, *How to develop RF hardware using STM32WBA MCUs*.
- **[AN6305]** ST, *Guidelines for PCB design on STM32WBA5MMG*.
- **[UM2448]** ST, *STLINK-V3SET debugger/programmer* user manual (STDC14 pinout).
- **[AN2866]** ST, *How to design a 13.56 MHz customized antenna for ST25 NFC / RFID tags*.
- **[AN11276]** NXP, *NTAG Antenna Design Guide*.
- **[AN928.2]** Silicon Labs, *EFR32 Series 2 Layout Design Guide*.
- **[AN930.2]** Silicon Labs, *EFR32 Series 2 2.4 GHz Matching Guide*.
- **[AN1088]** Silicon Labs, *Designing with an Inverted-F 2.4 GHz PCB Antenna*.
- **[AN91445]** Infineon (Cypress), *Antenna Design and RF Layout Guidelines*.
- **[SWRA117]** TI, *AN043 Small Size 2.4 GHz PCB antenna* (SWRA117D).
- **[SWRA640]** TI, *CC13xx/CC26xx Hardware Configuration and PCB Design Considerations*.
- **[NWP-017]** Nordic, *nWP-017 Antenna tuning*.
- **[ESP-PCB]** Espressif, *ESP Hardware Design Guidelines: PCB Layout Design*.
- **[EZ-GND]** Ezurio FAQ, ground-plane size for module antennas.
- **[AN4747]** NXP, *Kinetis L hardware design considerations* (input RC).
- **[SLVA139]** TI, *Reverse Current/Battery Protection Circuits*.
- **[SLVA680]** TI, *ESD Protection Layout Guide*.
- **[SLVA689A]** TI, *I²C Bus Pullup Resistor Calculation*.
- **[SLUA887]** TI, *Bootstrap Circuitry Selection for Half-Bridge Configurations*.
- **[SLUP169]** TI, *Design and Application Guide for High Speed MOSFET Gate Drive Circuits*.
- **[SLTA055]** TI, *Input and Output Capacitor Selection*.
- **[SCBA004]** TI, *Implications of Slow or Floating CMOS Inputs*.
- **[SBAS788A]** TI, ADS7039-Q1 datasheet, ADC driver and charge-bucket design.
- **[SBAA173A]** TI, *Determining Minimum Acquisition Times for SAR ADCs*.
- **[MT-036]** ADI, *Op Amp Output Phase-Reversal and Input Over-Voltage Protection*.
- **[ADI-FB]** ADI, *Ferrite beads demystified* (DC-bias behaviour).
- **[MLCC-FLEX]** Murata and KEMET MLCC mounting guidance on board flex cracking (§16 item 17).
- **[ELCAP-LIFE]** Aluminium electrolytic capacitor life equation in the manufacturer's technical notes (§16 item 19).
- **[QWIIC]** SparkFun, *Qwiic Connect System* (connector pinout).
- **[Greenhouse]** H. M. Greenhouse, "Design of Planar Rectangular Microelectronic Inductors", *IEEE Trans. Parts, Hybrids and Packaging* PHP-10(2), 1974.
- **[Mohan]** S. S. Mohan et al., "Simple Accurate Expressions for Planar Spiral Inductances", *IEEE JSSC* 34(10), 1999.

**Fab**
- **[JLC-CAP]** JLCPCB, *PCB Manufacturing & Assembly Capabilities*, jlcpcb.com/capabilities/pcb-capabilities.
- **[JLC-IMP]** JLCPCB, *Impedance calculator and stack-ups*, jlcpcb.com/impedance.

**Skills** (the `hardware-design` plugin, CLAUDE.md §1): `mcu-circuit-design`, `analog-circuit-design`, `circuit-simulation`, `power-pcb-layout`, `rf-layout`, `interface-layout`, `pcb-design-rules`. Section numbers are cited as e.g. [power-pcb-layout §3.1]; each skill lists its own primary sources.

**This repository:** `docs/requirements.md` (contract), `docs/decisions.md` (intent), `docs/plan.md` (phases and gates), `simulation/REPORT.md` (S0–S5 evidence), `docs/design-calcs.md`, `docs/power-map.md`, `docs/rf.md`, `docs/nfc.md`, `docs/mechanical.md`, `docs/layout.md`, `docs/firmware-interface.md`.
