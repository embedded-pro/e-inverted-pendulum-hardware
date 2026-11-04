# e-inverted-pendulum-hardware

Hardware for the [e-inverted-pendulum](https://github.com/embedded-pro/e-inverted-pendulum) self-balancing robot: a single 4-layer PCB that is also the robot's chassis. It carries an STM32WB55RG (BLE), a DRV8711 driving two brushed DC gearmotors with ABZ encoders, an MPU-6500 IMU, SPI flash and a 3S LiPo power path. Built and assembled at JLCPCB.

Status: **Phase 1 (schematic) complete, awaiting the gate review**. Phase 0 was signed off on 2026-11-04. (see [docs/plan.md](docs/plan.md) for every phase).

| Phase 0 output | Where | Reproduce |
|---|---|---|
| Hardware requirements traced to firmware REQ IDs | [docs/requirements.md](docs/requirements.md) | |
| Decisions D-001 to D-016 | [docs/decisions.md](docs/decisions.md) | |
| Pin map, validated against the package and the firmware | [docs/pinmap.md](docs/pinmap.md), `pin-data/pinmap.csv` | `python3 scripts/check_pinmap.py --firmware ../e-inverted-pendulum` |
| Motor, gear and current-trip sizing (S0) | [simulation/REPORT.md](simulation/REPORT.md) | `python3 simulation/sizing.py` |
| Mechanical concept and mass budget | [docs/mechanical.md](docs/mechanical.md), `mechanical/mass_budget.csv` | |
| Architecture and power budget | [docs/architecture.md](docs/architecture.md) | |
| Key-part list feeding the generator | `bom/parts.csv`, `bom/passives.json` | `python3 scripts/passive_catalog.py` |

| Phase 1 output | Where | Reproduce |
|---|---|---|
| Schematic (KiCad 10, 8 sheets, 171 parts) | `kicad/`, [docs/schematic.pdf](docs/schematic.pdf) | `python3 kicad/gen/build.py` |
| Component values and their sources | [docs/design-calcs.md](docs/design-calcs.md) | `python3 scripts/design_calcs.py` |
| Custom symbols and footprints | `kicad/lib/` | `python3 kicad/gen/make_library.py`, `make_footprints.py` |
| ERC (0 errors, 0 warnings) | CI | `kicad-cli sch erc --severity-all kicad/e-inverted-pendulum.kicad_sch` |
| Netlist, pin map and symbol/footprint checks | CI | `python3 scripts/check_netlist.py`, `check_library.py`, `check_pinmap.py` |
| Assembly BOM (64 lines, all in stock for 5 boards) | `bom/bom.csv`, `bom/bom_jlc.csv`, `bom/stock_check.json` | `python3 scripts/export_bom.py` then `jlc_stock.py bom/bom.csv --boards 5` |
| Gate checklist and open items | [docs/checklists/phase1.md](docs/checklists/phase1.md) | |
| Settings the firmware must apply | [docs/firmware-interface.md](docs/firmware-interface.md) | |

Design rules come from the `hardware-design` skills in [claude-hardware-skills](https://github.com/gabrielfrasantos/claude-hardware-skills).
