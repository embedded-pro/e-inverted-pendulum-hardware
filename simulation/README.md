# Simulation suite

Built per the `circuit-simulation` skill. Results land in `results/` and plots in `plots/`.
Raw simulator output goes to `work/`, which is gitignored. Findings are in `REPORT.md`.

| ID | Script | Question | Status |
|---|---|---|---|
| S0 | `sizing.py` | Gear ratio, current trip, PWM ripple, encoder rate (Python model, no SPICE) | done |
| S1 | `power_entry.py` | Inrush, reverse battery, regeneration at switch-off | Phase 2 |
| S2 | `bridge.py` | H-bridge switching, chopping, FET losses | Phase 2 |
| S3 | `bus.py` | VM sag and ripple into the buck | Phase 2 |
| S4 | `rails.py` | 5V0 and 3V3 transients, LDO PSRR, ripple at VDDRF | Phase 2 |
| S5 | `analog.py` | VBAT ADC settling and accuracy, encoder input edges | Phase 2 |

Requirements: Python 3 with numpy, scipy and matplotlib; ngspice ≥ 42 for S1–S5.

```bash
python3 simulation/sizing.py
```
