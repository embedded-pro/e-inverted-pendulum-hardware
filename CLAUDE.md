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
- JLCPCB is the fab and assembler (D-036). Prefer parts in stock, basic before extended; footprints
  must match the LCSC part's package exactly.
- Stack-up: JLC04161H-7628, 4-layer 1.6 mm, 1 oz outer / 0.5 oz inner. L2 is solid GND and is
  never cut, except the copied MB1355 cut-out under the RF line (D-037) and the NFC coil keep-out (all layers,
  D-039). Design rules are JLCPCB's (`pcb-design-rules`, D-036).
- The RF corner (MCU, RF path, antenna tab, SMPS, crystals) is a literal copy of ST's NUCLEO-WB55 MB1355 rev D-01
  (D-037, `docs/rf.md`). Change it only with ST's reference in hand; ST's files stay in the gitignored `reference/`.
- The NFC corner (M24SR64-Y, ANT14 coil, tuning caps, copper) is a literal copy of ST's X-NUCLEO-NFC01A1 MB1163 rev C-01
  (D-039, `docs/nfc.md`), under the same rule.
- The motor-driver power stage (DRV8711, CSD88537ND bridges, shunts, net ties, support caps, copper) is a copy of TI's
  BOOST-DRV8711 (D-040, `docs/drive.md`), under the same rule; our extras sit beside it.
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
- `python3 scripts/nfc_coil.py`: ANT14 inductance and resonance on ST's board and ours (`docs/nfc.md`).
- `python3 scripts/design_calcs.py`: values -> `scripts/schgen/values.json`, `docs/design-calcs.md`.
- `python3 scripts/schgen/build.py`: regenerate the schematic into `hardware/e-inverted-pendulum/` from
  `scripts/schgen/design/*.py` (D-020, D-033). Sheets follow e-psu-hardware: one titled box per functional block, circuits
  wired with `rail` / `link` / `path`, a design note in each box, `sh.desc` for the root page. Fails on layout lint.
- `python3 scripts/schgen/check.py`: the exported netlist matches `scripts/schgen/expected.json` (names included).
- `python3 scripts/schgen/check_equivalence.py <rev | file.net>`: same parts, fields and connectivity as a git revision;
  run it after any drawing-only change. `scripts/schgen/render.sh`: build, check, `docs/schematic.pdf`, sheet PNGs.
- `python3 scripts/check_netlist.py` / `check_library.py`: netlist and symbol/footprint checks.
- `python3 scripts/pcb/board.py --rules <pcb_rules.py>`: update the PCB from the schematic (footprints, nets, net classes
  from `docs/power-map.md`, JLCPCB rules, D-036). Placement is the owner's (D-032): it never
  moves or reshapes what is on the board; it adds missing items (new parts go to the first free spot in the staging
  area) and removes parts deleted from the schematic. Only references show on the silkscreen; test pads show their net
  (D-035). `--stage-all` is a one-shot reset to staging.
- `python3 scripts/pcb/silk.py [--check]`: silkscreen labels at JLCPCB's 1.0 mm / 0.15 mm, clear of every label, outline,
  pad, via, body and the edge, next to their part (D-041). `board.py` and the paste scripts run it last; run it after
  moving parts in KiCad. Clean labels never move.
- `python3 scripts/rf_reference.py`: ST's MB1355 files (`reference/mb1355/`, gitignored, OPLA) -> `scripts/pcb/mb1355_rf.json`
  and the `MB1355_*` footprints (D-037).
- `python3 scripts/pcb/rf_block.py --apply`: paste the MB1355 RF corner (one shot, a locked group; no-op once present).
- `python3 scripts/nfc_reference.py`: ST's MB1163 Gerbers (`reference/mb1163/`, gitignored) -> `scripts/pcb/mb1163_nfc.json`
  and the `MB1163_*` footprints (D-039). `python3 scripts/pcb/nfc_block.py --apply`: paste the NFC corner, as rf_block does.
- `python3 scripts/drv_reference.py`: TI's BOOST-DRV8711 PcbDoc (`reference/boost-drv8711/`, gitignored) ->
  `scripts/pcb/boost_drv8711.json` and the `BOOST_*` footprints (D-040). `python3 scripts/pcb/drv_block.py --apply`: paste it.
- `python3 scripts/pcb/place_block.py --apply <block>`: place a block of parts at the owner's spots from `placement.py`, once
  (anchors locked): `motor_io` = J601 / J602 at the side edges with their encoder chains and supply (D-042);
  `imu_memory` = the IMU on the centre line, the flash below the MCU, the EEPROM left of it (D-043).
- `python3 scripts/pcb/render.py`: per-layer, side, overview and 3D renders into `docs/images/`.
- `python3 scripts/export_bom.py` then `python3 scripts/jlc_stock.py bom/bom.csv --boards 5`: BOM and stock.
- `python3 scripts/fetch_datasheet.py <LCSC>`: datasheets into the gitignored `datasheets/`.
- `python3 scripts/export_review.py`: review package in `review_exports/e-inverted-pendulum/`.
  `export_jlcpcb.py` (fab + assembly), `export_release.py` (release zip), `visual_diff.py` (PR diff); all outputs are
  gitignored.
- `.mcp.json`: kicad-mcp-pro on `hardware/` (schematic profile), as in e-psu-hardware.

## 5. Review

Design reviews use the `pendulum-board-reviewer` agent (`.claude/agents/`): read-only, works from
`review_exports/e-inverted-pendulum/`, with `docs/requirements.md` as the contract, `simulation/REPORT.md` as the
evidence and `docs/robot-hardware-design-guide.md` as the rubric. CI is a guardrail, not a review.
