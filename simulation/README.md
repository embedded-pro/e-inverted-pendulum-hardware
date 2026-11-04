# Simulation suite

Built per the `circuit-simulation` skill. Results land in `results/` and plots in `plots/`.
Raw simulator output goes to `work/`, which is gitignored. Findings are in `REPORT.md`.

| ID | Script | Question | Status |
|---|---|---|---|
| S0 | `sizing.py` | Gear ratio, current trip, PWM ripple, encoder rate (Python model, no SPICE) | done |
| S1 | `power_entry.py` | Inrush, hot plug, reverse battery, regeneration at switch-off | done (2 fixes) |
| S2 | `bridge.py` | H-bridge switching, phase-node limits, FET losses | done (1 fix) |
| S3 | `bus.py` | Bus ripple, battery sag, UVLO margins | done |
| S4 | `rails.py` | Buck by equations, LDO with the TI model | done (buck dynamics: bench) |
| S5 | `analog.py` | VBAT ADC settling and accuracy, encoder edges | done |

Requirements: Python 3 with numpy, scipy and matplotlib; ngspice ≥ 42 for S1–S5. TI models (S4) are not
committed (TI copyright); fetch them first.

```bash
python3 simulation/fetch_models.py
```

```bash
python3 simulation/run_all.py
```

Models: `models/devices.lib` (our datasheet-derived MOSFET, TVS, zener, Schottky and capacitor models).
