# e-inverted-pendulum-hardware — Claude Code Instructions

Hardware for the self-balancing robot whose firmware lives in
`embedded-pro/e-inverted-pendulum`. The PCB is also the robot's chassis. The full
plan, with every decision and phase gate, is in `docs/plan.md`. Read it before changing anything.

## 1. Skills: load before working

The `hardware-design` plugin (marketplace `hardware-skills`, registered in
`.claude/settings.json`) holds the design rules. Load the matching skill before the work:

| Work | Skill |
|---|---|
| MCU support circuitry, decoupling, crystals, debug, GPIO/ESD | `mcu-circuit-design` |
| Battery divider, ADC drive, encoder input conditioning | `analog-circuit-design` |
| ngspice suite under `simulation/` | `circuit-simulation` |
| DRV8711 bridge, buck, power path, high-current copper | `power-pcb-layout` |
| STM32WB RF path, IPD, antenna, crystal, SMPS near RF | `rf-layout` |
| Connector ESD (encoders, Qwiic, battery) | `interface-layout` |

## 2. Sources of truth

- **Firmware is the requirement source.** Every hardware requirement in
  `docs/requirements.md` traces to a firmware `REQ-*` ID or to a decision in
  `docs/decisions.md`.
- **Pin map:** `pin-data/pinmap.csv`, validated by `scripts/check_pinmap.py` against the
  package and alternate-function data extracted from ST DS11929. It must stay
  1:1 with `targets/platform_implementations/st/` in the firmware for every pin the firmware
  already uses.
- **Component values:** the KiCad schematic, once it exists. Simulations read values from
  `*.kicad_sch`; proposed changes live in the `PROPOSED` dict until accepted.
- **Parts:** `bom/parts.csv` carries the LCSC number for every line. `scripts/jlc_stock.py`
  checks it against JLCPCB before an order and before a schematic freeze.

## 3. Rules

- Every number needs a source: a datasheet (ID and section), app note, firmware file and line,
  or a script in `simulation/` that reproduces it. Unsourced numbers are marked
  **ASSUMPTION** and listed in the doc's open-items section.
- JLCPCB is the fab and assembler. Prefer parts in stock, basic before extended; footprints
  must match the LCSC part's package exactly.
- Stack-up: JLC04161H-7628, 4-layer 1.6 mm, 1 oz outer / 0.5 oz inner. L2 is solid GND and is
  never cut.
- Phases have gates (`docs/plan.md`). Do not start a phase before the previous gate is
  signed off by the user.
- Layout: the user places the anchors and they are never moved (`power-pcb-layout` §1).
- Visuals in docs: Mermaid or ASCII only.

## 4. Tooling

- KiCad 10 (`kicad-cli`, 10.0.8 from `ppa:kicad/kicad-10.0-releases`): ERC, DRC, exports.
  `pcbnew` SWIG still imports in 10.0.x.
- ngspice, plus Python 3 with numpy, scipy, matplotlib and spicelib.
- `python3 simulation/sizing.py`: motor/drive sizing (S0).
- `python3 scripts/check_pinmap.py`: pin map validation.
- `python3 scripts/gcpw.py`: 50 Ω GCPW width/gap for the stack-up (`docs/rf.md`).
- `python3 scripts/nfc_coil.py`: NFC coil inductance/resonance and its footprint (`docs/nfc.md`).
- `python3 scripts/design_calcs.py`: values -> `kicad/gen/values.json`, `docs/design-calcs.md`.
- `python3 kicad/gen/build.py`: regenerate the schematic (until the Phase 1 gate, D-020).
- `python3 scripts/check_netlist.py` / `check_library.py`: netlist and symbol/footprint checks.
- `python3 kicad/gen/board.py --rules <pcb_rules.py>`: update the PCB from the schematic (footprints, nets, net classes
  from `docs/power-map.md`, JLC rules). Placement is the owner's (D-032): it never moves, reshapes or deletes what is on
  the board, only adds missing items (new parts go to the staging area). `--stage-all` is a one-shot reset to staging.
- `python3 scripts/render_board.py`: per-layer, side and 3D renders into `kicad/renders/`.
- `python3 scripts/export_bom.py` then `python3 scripts/jlc_stock.py bom/bom.csv --boards 5`: BOM and stock.
- `python3 scripts/fetch_datasheet.py <LCSC>`: datasheets into the gitignored `datasheets/`.
