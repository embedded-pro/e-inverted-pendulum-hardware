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

- **STM32WB55RGV6** with BLE 5: internal SMPS, 32 MHz HSE without external caps, printed IFA through an
  `MLPF-WB55-01E3` filter on a 50 Ω GCPW line, DNP pi tuning and a DNP U.FL test port.
- **DRV8711 gate driver with four external half-bridges** (`CSD88537ND`) for two MG310 gear motors: indexer bypassed
  (PWMMODE 1), 50 mΩ low-side shunts with Kelvin taps, 2.0 A trip, SS34 clamps on every phase node.
- **Battery path:** XT30, 4 A fuse, back-to-back `AO4805` P-FETs for reverse polarity and switching, with a simulated
  Miller soft start; `SMBJ15A` after the FETs.
- **Rails:** `TPS62933F` buck to 5 V (encoders, buzzer, LDO), `TLV75533P` LDO to 3.3 V, ferrite-filtered VDDA.
- **Sensors and storage:** `MPU-6500` IMU on SPI2, `W25Q16JV` flash on SPI1, `M24C64` EEPROM and an `ST25DV04KC` NFC tag
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
| `ui` | LEDs, button, buzzer, Qwiic, EEPROM, NFC tag, test points | `M24C64`, `ST25DV04KC` |

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
| Radio | BLE on the STM32WB55, printed IFA | D-001, D-007 |
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
│       ├── e-inverted-pendulum.pretty/      # project footprints (XT30, STDC14, NFC coil, ...)
│       └── sym-lib-table, fp-lib-table
├── scripts/
│   ├── schgen/                       # schematic generator: design/*.py -> hardware/ (D-020, D-033)
│   ├── pcb/                          # board sync from the schematic (add-only, D-032) and renders
│   ├── export_review.py              # review package     -> review_exports/<board>/
│   ├── export_jlcpcb.py              # fab + assembly     -> manufacturing/<board>/
│   ├── export_release.py             # release bundle     -> release/<board>-<version>.zip
│   ├── visual_diff.py                # PR visual diff     -> diff/<board>/
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

### Review and fabrication packages

- `python3 scripts/export_review.py`: ERC/DRC, netlist, BOM, PDFs and renders for a design review, used by the
  `pendulum-board-reviewer` agent in [`.claude/agents/`](.claude/agents/).
- `python3 scripts/export_jlcpcb.py`: Gerbers, drill, BOM and CPL for JLCPCB.
- `python3 scripts/export_bom.py` then `python3 scripts/jlc_stock.py bom/bom.csv --boards 5`: BOM and live stock.

---

## Before ordering

1. Finish Phase 3: placement (owner), routing, DRC clean with schematic parity, the `power-pcb-layout` §7 and
   `rf-layout` §12 checklists ([docs/plan.md](docs/plan.md)).
2. Re-run the stock check; every line must be in stock for the order quantity.
3. JLCPCB options: 4 layers, JLC04161H-7628, 1.6 mm, 1 oz outer / 0.5 oz inner; check every CPL rotation in the
   preview.
4. Leave the DNP parts off: pi tuning C401/C402, U.FL J401 + R402, NFC trim C804, sense filters C501/C504, motor
   snubbers C603/C607, encoder pull-ups, R602.

---

## Continuous integration

- [`hardware.yml`](.github/workflows/hardware.yml): pin map, regenerate the schematic with no diff, netlist against
  the generator's intent, ERC, netlist and symbol/footprint checks.
- [`kicad-bot.yml`](.github/workflows/kicad-bot.yml): [kicad-bot](https://github.com/embedded-pro/kicad-bot) ERC/DRC
  with schematic parity; DRC does not fail the build until the board is routed. **Manual runs only for now:**
  kicad-bot v0.1.3 installs KiCad 9.0.8, which can't open this KiCad 10 project. The release workflow's fab bundle
  depends on it too.
- [`kicad-diff.yml`](.github/workflows/kicad-diff.yml): red/green visual diff of schematic and board on pull requests.
- [`release.yml`](.github/workflows/release.yml): [release-please](https://github.com/googleapis/release-please) from
  Conventional Commits; each release attaches the fabrication bundle from `scripts/export_release.py`.

Third-party actions are pinned to a full commit SHA. CI is a guardrail, not a design review: use the
`pendulum-board-reviewer` agent with [docs/robot-hardware-design-guide.md](docs/robot-hardware-design-guide.md) for that.

Design rules come from the `hardware-design` skills in
[claude-hardware-skills](https://github.com/gabrielfrasantos/claude-hardware-skills).
