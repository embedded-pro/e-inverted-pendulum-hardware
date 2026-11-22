# e-inverted-pendulum — Hardware

[![hardware](https://github.com/embedded-pro/e-inverted-pendulum-hardware/actions/workflows/hardware.yml/badge.svg)](https://github.com/embedded-pro/e-inverted-pendulum-hardware/actions/workflows/hardware.yml)
[![kicad-bot](https://github.com/embedded-pro/e-inverted-pendulum-hardware/actions/workflows/kicad-bot.yml/badge.svg)](https://github.com/embedded-pro/e-inverted-pendulum-hardware/actions/workflows/kicad-bot.yml)
[![KiCad](https://img.shields.io/badge/KiCad-10-blue.svg)](https://www.kicad.org/)

Hardware for the [e-inverted-pendulum](https://github.com/embedded-pro/e-inverted-pendulum) two-wheeled self-balancing
robot. The PCB is the robot's chassis: one vertical 85 × 130 mm 4-layer board carries the electronics, the battery and
the motor bracket. Built and assembled at JLCPCB.

This repository holds the **KiCad** design, the Python scripts that generate the schematic and sync the board, and the
ngspice simulation suite. The firmware lives in its own repository and is the source of the requirements.

> **Status: Phase 3 (layout), placement handed to the owner (D-032).** Phases 0–2 (requirements, schematic,
> simulation) are signed off. The schematic is complete, simulated and ERC-clean; the board has its outline, rule
> areas and bracket holes, with every part in the staging area. See [docs/plan.md](docs/plan.md) for the phase gates.

---

## Highlights

- **STM32WB55RGV6** with BLE 5. The whole RF corner is a copy of ST's NUCLEO-WB55 (MB1355 rev D-01, D-037): internal
  SMPS, 32 MHz HSE without external caps, `MLPF-WB55-01E3` → 3.6 nH / 1.2 pF match → printed meander antenna on
  ST's ground-free tab at the top-left corner (PCB antenna only, D-038). The MCU decoupling sits on top at the
  Nucleo's spots, or the nearest free spot to each pin (DS11929 Fig. 16 values, D-038).
- **DRV8711 gate driver with four external half-bridges** (`CSD88537ND`) for two MG310 gear motors: indexer bypassed
  (PWMMODE 1), 50 mΩ low-side shunts with Kelvin taps, 2.0 A trip, SS34 clamps on every phase node. The power stage is
  a copy of TI's BOOST-DRV8711 (D-040, `docs/drive.md`).
- **Battery path:** XT30, 4 A fuse, back-to-back `AO4805` P-FETs for reverse polarity and switching, with a simulated
  Miller soft start; `SMBJ15A` after the FETs.
- **Rails:** `TPS62933F` buck to 5 V (encoders, RGB LEDs, LDO), `TLV75533P` LDO to 3.3 V, ferrite-filtered VDDA.
- **12 RGB LEDs** (`WS2812B-2020-V6`) on one PA7 timer/DMA pin through a 5 V `SN74AHCT1G125`: it is also a toy (D-035).
  No buttons, no buzzer.
- **Test pads** on every sheet (rails, motor phases and shunts, PWM, SPI, encoders, IMU, I2C), net names on the silk.
- **Sensors and storage:** `MPU-6500` IMU on SPI2, `W25Q16JV` flash on SPI1, `M24C64` EEPROM and an `M24SR64-Y` NFC tag
  with a printed 13.56 MHz coil on I2C3, plus a Qwiic port.
- **Encoder inputs:** ESD at the connector, 100 Ω + 1 nF, `SN74LVC3G17` Schmitt buffers with 5 V-tolerant inputs.

---

## Board architecture

The schematic has 8 hierarchical sheets, one functional block each, drawn as titled boxes with design notes (the
e-psu-hardware pattern, D-033):

| Sheet | Function | Key parts |
|-------|----------|-----------|
| `e-inverted-pendulum.kicad_sch` | Root: sheet descriptions, power flow, grounding | — |
| `power_entry` | Battery input, fuse, power switch with soft start, TVS, VBAT sense | `AO4805`, `SMBJ15A`, XT30 |
| `logic_power` | 5V0 buck and 3V3 LDO | `TPS62933F`, `TLV75533P` |
| `mcu` | MCU pin map, decoupling, SMPS, clocks, reset/boot, STDC14 debug | `STM32WB55RGV6` |
| `rf` | 2.4 GHz path and printed antenna | `MLPF-WB55-01E3` |
| `drive` | Gate driver, four half-bridges, current sense | `DRV8711`, `CSD88537ND` |
| `motors_encoders` | Motor + encoder connectors, encoder conditioning | JST PH 6-pin, `TPD4E05U06`, `SN74LVC3G17` |
| `imu_flash` | IMU and SPI flash | `MPU-6500`, `W25Q16JV` |
| `ui` | Status LED, 12 RGB LEDs, Qwiic, EEPROM, NFC tag | `WS2812B-2020-V6`, `SN74AHCT1G125`, `M24C64`, `M24SR64-Y` |

---

## Design requirements

The firmware is the requirement source. [docs/requirements.md](docs/requirements.md) traces every hardware
requirement to a firmware `REQ-*` ID or to a decision in [docs/decisions.md](docs/decisions.md). The key targets:

| Item | Target | Source |
|------|--------|--------|
| Battery | 3S LiPo, 9.0–12.6 V, XT30, reverse-polarity protected | D-011, D-021 |
| Motors | 2 × MG310 1:20 (7.4 V), average motor voltage capped at 7.4 V by firmware | D-027 |
| Drive | DRV8711, PWMMODE 1, trip 2.0 A (ISGAIN 20, TORQUE 186), 0.5 A continuous by firmware I²t | D-027, S0 |
| Encoders | Hall A/B, no index; 1040 counts per wheel revolution (13 PPR is an assumption) | D-028 |
| Radio | BLE on the STM32WB55, RF corner copied from ST's NUCLEO-WB55 (MB1355) | D-001, D-007, D-037 |
| PCB | 85 × 130 mm, 4 layers JLC04161H-7628, L2 solid GND, JLCPCB assembly | D-008, D-024 |

[docs/firmware-interface.md](docs/firmware-interface.md) lists the settings the firmware must apply (DRV8711 registers,
voltage cap, ADC scaling, clock trims, I2C addresses).

### Simulation

`python3 simulation/run_all.py` runs S0–S5 (motor sizing, power entry, H-bridge switching, bus ripple, rails, ADC and
encoder edges). Two power-entry failures and one phase-node abs-max violation were found and fixed in the schematic.
Details: [simulation/REPORT.md](simulation/REPORT.md).

---

## Repository layout

```
e-inverted-pendulum-hardware/
├── hardware/
│   └── e-inverted-pendulum/          # KiCad 10 project
│       ├── e-inverted-pendulum.kicad_pro / .kicad_sch (root) / .kicad_pcb / .kicad_dru
│       ├── power_entry / logic_power / mcu / rf / drive / motors_encoders / imu_flash / ui .kicad_sch
│       ├── e-inverted-pendulum.kicad_sym    # project symbols
│       ├── e-inverted-pendulum.pretty/      # project footprints (XT30, STDC14, MB1355_* and MB1163_* from ST, ...)
│       └── sym-lib-table, fp-lib-table
├── scripts/
│   ├── schgen/                       # schematic generator: design/*.py -> hardware/ (D-020, D-033)
│   ├── pcb/                          # board sync (add-only, D-032), RF / NFC corner pastes (rf_block.py D-037, nfc_block.py D-039), renders
│   ├── export_review.py              # review package     -> review_exports/<board>/
│   ├── export_jlcpcb.py              # fab + assembly     -> manufacturing/<board>/
│   ├── export_release.py             # release bundle     -> release/<board>-<version>.zip
│   ├── visual_diff.py                # PR visual diff     -> diff/<board>/
│   ├── rf_reference.py               # ST MB1355 files (reference/, gitignored) -> pcb/mb1355_rf.json + MB1355_* footprints
│   ├── nfc_reference.py              # ST MB1163 Gerbers (reference/, gitignored) -> pcb/mb1163_nfc.json + MB1163_* footprints
│   └── check_*.py, design_calcs.py, nfc_coil.py, gcpw.py, export_bom.py, jlc_stock.py
├── simulation/                       # ngspice suite (S0–S5) + REPORT.md
├── pin-data/                         # pin map and the DS11929 package data it is checked against
├── bom/                              # part catalogue, BOM, stock check
├── docs/
│   ├── plan.md, requirements.md, decisions.md, design-calcs.md, power-map.md, rf.md, nfc.md, layout.md, ...
│   ├── robot-hardware-design-guide.md    # design and review knowledge base
│   ├── schematic.pdf
│   └── images/                       # board renders
├── .claude/agents/pendulum-board-reviewer.md   # design-review agent
├── PROJECT_CONTEXT.md                # design summary, decisions, open items
└── .github/workflows/                # hardware checks, kicad-bot, visual diff, release
```

Generated outputs are gitignored: `review_exports/`, `manufacturing/`, `release/`, `diff/`.

---

## Getting started

KiCad 10 project. Open `hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pro`.

```bash
git clone https://github.com/embedded-pro/e-inverted-pendulum-hardware.git
```

### Headless checks (the same ones CI runs)

```bash
python3 scripts/check_pinmap.py --firmware ../e-inverted-pendulum
```

```bash
python3 scripts/schgen/build.py
```

```bash
python3 scripts/schgen/check.py
```

```bash
kicad-cli sch erc --severity-all --exit-code-violations hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_sch
```

```bash
python3 scripts/check_netlist.py && python3 scripts/check_library.py
```

### Changing the schematic

The schematic is generated: edit `scripts/schgen/design/<sheet>.py`, then rebuild. `scripts/schgen/render.sh` rebuilds,
checks the netlist against `expected.json`, writes `docs/schematic.pdf` and renders each sheet to PNG. After a
drawing-only change, prove the circuit is unchanged against the last commit:

```bash
python3 scripts/schgen/check_equivalence.py HEAD
```

Then bring the board in line (new parts land in the staging area; nothing on the board moves):

```bash
python3 scripts/pcb/board.py --rules <path to pcb_rules.py from the pcb-design-rules skill>
```

The RF corner is a copy of ST's NUCLEO-WB55 (MB1355 rev D-01, D-037). It is pasted once, and a second
run does nothing (since D-046 it is no longer a group and has no pours; `docs/rf.md`):

```bash
python3 scripts/pcb/rf_block.py --apply
```

`scripts/rf_reference.py` re-derives `scripts/pcb/mb1355_rf.json` and the `MB1355_*` footprints from ST's files, which are
kept out of the repository in `reference/mb1355/` (ST's Open Platform License).

The NFC corner is a copy of ST's X-NUCLEO-NFC01A1 (MB1163 rev C-01, D-039): the M24SR64-Y, its ANT14 coil, tuning caps,
copper and pour, pasted the same way (`docs/nfc.md`). `scripts/nfc_reference.py` re-derives `scripts/pcb/mb1163_nfc.json`
and the `MB1163_*` footprints from ST's Gerbers in `reference/mb1163/`; `scripts/nfc_coil.py` checks the coil.

```bash
python3 scripts/pcb/nfc_block.py --apply
```

### Review and fabrication packages

- The export, BOM, stock, datasheet and visual-diff scripts are thin wrappers around the hardware-design plugin's,
  pinned in `scripts/plugin.py`; `python3 scripts/plugin_gates.py` runs the plugin's gates as CI does (D-064).
- `python3 scripts/export_review.py`: ERC/DRC, netlist, BOM, PDFs and renders for a design review, used by the
  `pendulum-board-reviewer` agent in [`.claude/agents/`](.claude/agents/).
- `python3 scripts/export_jlcpcb.py`: Gerbers, drill, BOM and CPL for JLCPCB.
- `python3 scripts/export_bom.py` then `python3 scripts/jlc_stock.py bom/bom.csv --boards 5`: BOM and live stock.

---

## Before ordering

1. Finish Phase 3: placement (owner), routing, DRC clean with schematic parity, the `power-pcb-layout` §7 and
   `rf-layout` §12 checklists ([docs/plan.md](docs/plan.md)).
2. Re-run the stock check; every line must be in stock for the order quantity.
3. JLCPCB options (PCB + assembly, D-036): 4 layers, JLC04161H-7628, 1.6 mm, 1 oz outer / 0.5 oz inner; impedance
   control only if JLCPCB holds MB1355's RF line as drawn (0.6 / 0.2 mm on L1 over L3, `docs/rf.md`). Check every CPL rotation in the preview
   (the WS2812B-2020 footprint is the datasheet pattern turned 180°).
4. Leave the DNP parts off: antenna-match C401, shield clips SC401–SC404, NFC tuning spares C821–C823 and pull-ups R805 / R806, sense filters C501/C504, motor
   snubbers C603/C607, encoder pull-ups, R602.

---

## Continuous integration

- [`hardware.yml`](.github/workflows/hardware.yml): pin map, regenerate the schematic with no diff, netlist against
  the generator's intent, ERC, netlist and symbol/footprint checks.
- [`kicad-bot.yml`](.github/workflows/kicad-bot.yml): [kicad-bot](https://github.com/embedded-pro/kicad-bot) ERC/DRC
  with schematic parity, on pushes to `main` and on pull requests; DRC does not fail the build until the board is
  routed. kicad-bot runs without KiCad's libraries, so its ERC shows library-lookup warnings; `hardware.yml` is the
  library check.
- [`kicad-diff.yml`](.github/workflows/kicad-diff.yml): red/green visual diff of schematic and board on pull requests.
- KiCad on GitHub runners: `scripts/install_kicad.sh 10` (and kicad-bot ≥ v0.1.5) pins the KiCad PPA to `amd64`.
  Ubuntu 26.04 runners otherwise install Ubuntu's KiCad 9, which can't open this project; the script fails if
  `kicad-cli` isn't 10.x.
- [`release.yml`](.github/workflows/release.yml): [release-please](https://github.com/googleapis/release-please) from
  Conventional Commits; each release attaches the fabrication bundle from `scripts/export_release.py`.

Third-party actions are pinned to a full commit SHA. CI is a guardrail, not a design review: use the
`pendulum-board-reviewer` agent with [docs/robot-hardware-design-guide.md](docs/robot-hardware-design-guide.md) for that.

Design rules come from the `hardware-design` skills in
[claude-hardware-skills](https://github.com/gabrielfrasantos/claude-hardware-skills).
