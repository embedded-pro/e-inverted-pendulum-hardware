# e-inverted-pendulum: project context

Paste or attach this file at the start of a new conversation to restore the context.

## What it is

The hardware for the embedded-pro `e-inverted-pendulum` two-wheeled self-balancing robot
(github.com/embedded-pro/e-inverted-pendulum-hardware; firmware in github.com/embedded-pro/e-inverted-pendulum).
The PCB is the robot's chassis: one vertical 85 × 130 mm board carries the electronics and the battery, and a WHEELTEC
102 mm steel U-bracket with two MG310 gear motors bolts to its bottom 25 mm strip. Built and assembled at JLCPCB.

The firmware is the requirement source: every hardware requirement in `docs/requirements.md` traces to a firmware
`REQ-*` ID or a decision in `docs/decisions.md`. The work runs in phases with user gates (`docs/plan.md`).

## Architecture (rev A schematic: KiCad 10, 8 sheets + root, 230 parts)

### Power

- **Battery:** 3S LiPo (9.0–12.6 V), XT30, 4 A fuse.
- **Power switch (D-011, D-021):** back-to-back AO4805 P-FETs. FET A blocks a reversed pack, FET B switches the load
  from a slide switch. Gate network: 100k / 100k divider, BZT52C15 V_GS clamp, Miller soft start (1k + 47 nF, ~0.7 A
  inrush), 1 µF gate-source cap against hot-plug turn-on.
- **Clamp and bulk:** SMBJ15A after the FETs; 220 µF + per-bridge 10 µF / 100 nF on VBAT.
- **Rails:** TPS62933F buck VBAT → +5V at 1.2 MHz (EN UVLO start 9.1 V, stop 8.5 V); TLV75533P LDO +5V → +3V3.
- **VBAT sense:** 100k / 27k to PC1, 100 nF bucket; per-board calibration.

### MCU and radio

- STM32WB55RGV6: internal SMPS (10 µH + 10 nH), HSE 32 MHz without external caps (HSETUNE), LSE 32.768 kHz,
  STDC14 (SWD + virtual COM on USART1), BOOT0 pull-down + test pad (no button).
- RF1 → MLPF-WB55-01E3 → 50 Ω GCPW (0.27 / 0.15 mm) → DNP pi tuning → TI SWRA117D printed IFA at the top edge; DNP U.FL.
- Pin map in `pin-data/pinmap.csv`, kept 1:1 with the firmware's NUCLEO-WB55RG target (`scripts/check_pinmap.py`).

### Motor drive

- DRV8711, PWMMODE 1 (TIM1 drives AIN1/2, BIN1/2 directly), four CSD88537ND dual N-FET half-bridges, 0 Ω gate
  resistors at the FETs, SS34 clamps on the phase nodes.
- 50 mΩ low-side shunts with Kelvin taps (net ties at the ground pads), DNP sense filters.
- Trip 2.0 A (ISGAIN 20, TORQUE 186); the 0.5 A continuous rating is enforced by a firmware I²t model (D-027).

### Encoders, sensors, I/O

- One JST PH 6-pin per motor (MG310 pinout, D-028). Hall A/B → TPD4E05U06 ESD → 100 Ω + 1 nF → SN74LVC3G17 → LPTIM1 /
  TIM2. No index: the third buffer input is grounded, so PC5 / PC3 read low.
- MPU-6500 on SPI2 (INT to PC6); W25Q16JV on SPI1 shared with the DRV8711 (33 Ω SCK termination).
- I2C3: Qwiic + ESD, M24C64 EEPROM at 0x50, ST25DV04KC NFC tag at 0x53 / 0x57 with a printed 10-turn 25 × 21 mm coil
  (f0 14.2 MHz, DNP 2.7 pF trim); GPO to PA2.
- 12 × WS2812B-2020-V6 RGB LEDs on +5V from PA7 (TIM17 + DMA) through an SN74AHCT1G125; green status LED on PB0.
  No buttons, no buzzer: the robot doubles as a toy (D-035).
- Test pads with net names on the silkscreen on every sheet: rails, motor phases and shunts, PWM, SPI, encoders,
  IMU, I2C, LED data (D-035).

## Simulation (ngspice, `simulation/`, REPORT.md)

- **S0 sizing:** the trip must be 2.0 A (1.0–1.5 A recover only 12–18° worst case); a 7.4 V average-voltage cap cruises
  1.0 m/s at 57 % of the cap. Lean setpoint ~18° with the bracket.
- **S1 power entry:** two failures found and fixed (hot-plug turn-on, 44.6 A inrush) by the D-021 gate network.
- **S2 bridge:** phase node below the DRV8711 abs max; fixed with SS34 clamps, IDRIVE 00.
- **S3–S5:** bus ripple, UVLO margins, rails, VBAT ADC and encoder edges pass, with firmware conditions
  (`docs/firmware-interface.md`).

## PCB (Phase 3, `hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pcb`)

- 85 × 130 mm, 4 layers JLC04161H-7628, 1 oz outer / 0.5 oz inner. L1 parts and RF, L2 solid GND (never cut), L3
  power pours, L4 signals + GND fill.
- Net classes from `docs/power-map.md`; JLC rules from the `pcb-design-rules` skill; custom DRC rules for the RF1
  trace, keep-outs and the bracket strip.
- **Placement belongs to the owner (D-032).** The board has the outline, rule areas and bracket holes; every part sits
  in the staging area. `scripts/pcb/board.py` only syncs from the schematic: it never moves, reshapes or deletes.
- Brief for the owner: `docs/layout.md`.

## Still to check or do

- Placement (owner), then routing, DRC with schematic parity, and the `power-pcb-layout` §7 / `rf-layout` §12
  checklists (Phase 3 gate).
- Mechanical ASSUMPTIONS in `docs/mechanical.md`: MG310 mass and stall current (the listing says "≤ 2 mA"), battery
  and component masses, the bracket's 18 mm reference face.
- Encoder resolution: 13 PPR is assumed (1040 counts per wheel revolution).
- REQ-ODOM-005 (index pulse) can't be met with the MG310; reported to the firmware.
- Bench items: buck load step, HSE trim, pi-network VNA tuning, NFC coil tuning (C804), thermal soak (`docs/plan.md`
  Phase 4).
- Re-run the JLC stock check before the order.

## Repository (same shape as embedded-pro/e-psu-hardware, D-033)

- `hardware/e-inverted-pendulum/`: KiCad 10 project with project symbols and footprints.
- `scripts/schgen/`: schematic generator (`design/*.py` → `hardware/`), e-psu's engine ported to KiCad 10; `check.py`
  (netlist vs `expected.json`), `check_equivalence.py` (drawing-only changes), `render.sh`.
- `scripts/pcb/`: board sync and renders. `scripts/export_*.py`, `visual_diff.py`: review, fab, release and diff
  packages.
- `simulation/`: S0–S5, values read from the schematic.
- `docs/`: plan, requirements, decisions, design calcs, power map, RF, NFC, layout brief, design guide, schematic PDF.
- `.claude/agents/pendulum-board-reviewer.md`: design-review agent.
- `.github/workflows/`: hardware checks, kicad-bot ERC/DRC, visual diff, release-please.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `chore:`, …).
