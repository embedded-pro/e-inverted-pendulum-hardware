# e-inverted-pendulum-hardware

Hardware for the [e-inverted-pendulum](https://github.com/embedded-pro/e-inverted-pendulum) self-balancing robot: a single 4-layer PCB that is also the robot's chassis. It carries an STM32WB55RG (BLE), a DRV8711 driving two brushed DC gearmotors with ABZ encoders, an MPU-6500 IMU, SPI flash and a 3S LiPo power path. Built and assembled at JLCPCB.

Status: **Phase 0 complete, awaiting review** (see [docs/plan.md](docs/plan.md) for every phase).

| Phase 0 output | Where | Reproduce |
|---|---|---|
| Hardware requirements traced to firmware REQ IDs | [docs/requirements.md](docs/requirements.md) | |
| Decisions, including proposals D-013 to D-015 | [docs/decisions.md](docs/decisions.md) | |
| Pin map, validated against the package and the firmware | [docs/pinmap.md](docs/pinmap.md), `pin-data/pinmap.csv` | `python3 scripts/check_pinmap.py --firmware ../e-inverted-pendulum` |
| Motor, gear and current-trip sizing (S0) | [simulation/REPORT.md](simulation/REPORT.md) | `python3 simulation/sizing.py` |
| Mechanical concept and mass budget | [docs/mechanical.md](docs/mechanical.md), `mechanical/mass_budget.csv` | |
| Architecture and power budget | [docs/architecture.md](docs/architecture.md) | |
| Key-part BOM with JLCPCB stock | `bom/parts.csv`, `bom/stock_check.json` | `python3 scripts/jlc_stock.py bom/parts.csv --boards 5` |

Design rules come from the `hardware-design` skills in [claude-hardware-skills](https://github.com/gabrielfrasantos/claude-hardware-skills).
