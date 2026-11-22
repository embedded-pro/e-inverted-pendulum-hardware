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
  area) and removes parts deleted from the schematic. Only the test pads' net names show on the silkscreen; every
  reference is on F.Fab (D-035, D-052). `--stage-all` is a one-shot reset to staging.
- `python3 scripts/pcb/silk.py [--check | --relayout]`: the test pads' net names at JLCPCB's 1.0 mm / 0.15 mm, clear of
  every label, outline, pad, via, body and the edge, next to their pad (D-041); every other reference on F.Fab, sized
  inside its part (D-052). `board.py` and the paste scripts run it last; run it after moving parts in KiCad. Clean
  labels never move; `--relayout` lays them all out afresh.
- `python3 scripts/rf_reference.py`: ST's MB1355 files (`reference/mb1355/`, gitignored, OPLA) -> `scripts/pcb/mb1355_rf.json`
  and the `MB1355_*` footprints (D-037).
- `python3 scripts/pcb/rf_block.py --apply`: paste the MB1355 RF corner (one shot; no-op once U301 is on the board).
  The scripts lock nothing: locking is the owner's, in KiCad (D-045).
- `python3 scripts/pcb/ungroup_copies.py --apply | --exclusions`: the three copies without groups or pours (D-046), and the
  copied routing's corners as DRC exclusions in the project (`--exclusions` recomputes them: none since D-053).
- `python3 scripts/pcb/pours.py --apply`: the solid L2 GND plane over the board, ST's RF-strip pours and the L2 cut-out,
  ST's NFC B.Cu ground, TI's 12 drive pours, and the board's rule areas; fills the zones (D-053). One shot.
- `python3 scripts/pcb/tidy_copper.py --apply`: exact 45° bends (copied diagonals 1–500 nm off), branches started on
  pads, a ground tee turned into a via, vias moved to JLCPCB's 0.20 mm hole-to-copper (D-053). No-op when tidy.
- `python3 scripts/pcb/route_simple.py --apply`: routing pass 1 (D-054). Each net's islands joined closest-first: pad-to-pad
  links up to 8 mm on one layer (straight or one 45° bend, class width narrowed only to a narrower pad, ≥ 0.15 mm), GND
  ties between a part's adjacent pins, short gaps to free track ends / vias, and one GND via per island off the L2 plane.
  Skips PWR_4.2A (pours), the vendor copies' own connections and a crystal unless both nets route. No-op when nothing
  simple is left.
- `python3 scripts/pcb/vendor_gaps.py --apply`: routing pass 2 (D-055). The vendor copies' missing tracks restored from the
  references where their ends land (or up to a hop onto a part that moved), the rest of a copy's own open connections
  re-joined by `maze.py` at the vendor's width (crystals, switch nodes, RF: F.Cu, no via; crystals as a pair), TI's missing
  vias where they fit, one GND via per open vendor ground pad. No-op when nothing is left.
- `python3 scripts/pcb/power_pours.py --apply`: the power bus (D-056). L3 = `L3_VBAT` corridor (`placement.L3_VBAT`) +
  `L3_GND`; `BUCK_SW_QUIET` on L3 / L4; L1 pours from `placement.L1_POWER`; VBAT via arrays (5 × 0.3 mm at Q101, 2 at the
  buck) and one via per VBAT pad off the plane; TP102 joined. Checks necks (L1 deflated 1.1 mm, L3 5.6 mm). One shot.
- `python3 scripts/pcb/route_maze.py --apply [--max-length 8]`: routing passes 3 / 4 (D-057, D-058). Each net's islands
  joined closest-first by `maze.py` (F.Cu / B.Cu, ≤ 2 vias, no jogs); `--max-length` = pass 3 (short, vias costly),
  without = pass 4 (by priority: encoders, VBAT_SENSE, DRV8711, SPI, I2C, SWD, supplies); in both, the MCU's +3V3 / VDDA
  pins within 10 mm of U301 go first (D-059). Skips PWR_4.2A and the crystals (CLK). Widths are the classes' (D-062: 0.15 mm below 1 A); 3 tries per island gap, in rounds until one routes nothing (several minutes to an hour). GND fills outside
  TI's bridges and ST's B.Cu strip below z 103 give way (D-058). No-op when nothing routable is left.
- `scripts/pcb/maze.py`: the grid router (0.05 mm, F.Cu / B.Cu, 45° turns only, layer-direction costs, ≤ 2 vias, every
  segment and via checked exactly) that `vendor_gaps.py` and `route_maze.py` use.
- `python3 scripts/pcb/route_phases.py --apply`: the four motor phases from TI's strips to J601 / J602 (D-060): each
  motor's pair on F.Cu across the top of the bracket strip, 0.8 mm; the SS34 clamps on their own strips with a GND via
  under the body; C502 beside C507; C603 turned; the phase test pads on their tracks. Checked exactly; one shot.
- `python3 scripts/pcb/gnd_fills.py --apply`: L1_GND / L4_GND fills over the board, outside the vendor copies' areas and
  the keep-outs, lowest priority; 0.3 / 0.6 mm stitching vias on a 5 mm lattice (not in the RF strip, the NFC area or L3's
  VBAT corridor), plus one GND via per cut-off piece of TI's GND fills (D-061). One shot.
- `python3 scripts/pcb/ripup.py --apply`: take up the routing of passes 1, 3 and 4 (the tracks and vias they added, known
  from the history: 86255bf vs 90d12ca, 6926847 vs ae59e46); the copies, pass 2, the power bus, the fan-out, the GND
  lattice and the pours stay (D-059). No-op once gone. Re-route with `route_simple` then `route_maze` (pass 3, pass 4).
- `python3 scripts/pcb/improve_placement.py --study | --apply <groups>`: the ratsnest's length (per-net Manhattan MST, the
  pcb-design-rules skill's measure) and the parts / groups whose move would shorten it; `--apply` moves the named groups
  (`j301`, `mcu_tp`, `flash`, `imu_tp`, `drive_tp`) each by the shortest-total translation that passes `place_block`'s
  checks, the pours, the keep-outs and a clean silk spot for every name, and writes the new spots into `placement.py`
  (D-059). Run it on a board without passes 1, 3 and 4.
- `python3 scripts/nfc_reference.py`: ST's MB1163 Gerbers (`reference/mb1163/`, gitignored) -> `scripts/pcb/mb1163_nfc.json`
  and the `MB1163_*` footprints (D-039). `python3 scripts/pcb/nfc_block.py --apply`: paste the NFC corner, as rf_block does.
- `python3 scripts/drv_reference.py`: TI's BOOST-DRV8711 PcbDoc (`reference/boost-drv8711/`, gitignored) ->
  `reference/boost-drv8711/boost_drv8711.json` (gitignored, D-063) and the `BOOST_*` footprints (D-040). `python3 scripts/pcb/drv_block.py --apply`: paste it.
- `python3 scripts/pcb/place_block.py --apply <block>`: place a block of parts at the owner's spots from `placement.py`, once
  (`--replace` moves a placed block to its changed table): `motor_io` = J601 / J602 at the side edges
  with their encoder chains and supply (D-042, D-044); `imu_memory` = the IMU on the centre line, the flash and the
  EEPROM left of the MCU (D-043); `power` = the TPS62933F buck and the TLV75533P LDO right of the power entry, to TI's
  layout guidance (D-049); `power_entry` = J101, F101, Q101 and their parts at the left edge, the owner's arrangement
  (D-047, D-052); `leds` = the 12 RGB LEDs as two square rings in the centre, their caps, the chain's driver and
  the status LED (D-050); `rest` = the power switch and the Qwiic port at the left edge, the support parts at their
  pins and the test pads in rows per block (D-051). The tables hold the owner's positions from KiCad (D-047): after
  moving parts, update them so `--replace` changes nothing; parts parked off the board (MC1–MC4, MH1 / MH2) are not in
  them. It refuses a spot that touches a courtyard, other-net copper or a silk outline, puts a pad under another
  part's silkscreen, or breaks JLCPCB's assembly spacing (0.5 mm between parts, 2.5 mm body to edge, D-052).
- `python3 scripts/pcb/respace.py --check | --apply`: JLCPCB's assembly spacing (IPC-7351B medium density: 0.5 mm
  between neighbouring parts' pads and bodies; 2.5 mm from a body to the edge, D-052). `--apply` moves the parts no table
  holds by the smallest step, tracks kept at their angles, a vendor's track end staying on the moved pad; one shot,
  no-op when clean. Run `--check` after moving parts.
- `python3 scripts/pcb/shift_block.py --apply drive | motor_left | motor_right`: move a placed block with its copper
  (tracks and vias inside its courtyards' box, on its nets) to the target of its anchor in `placement.py`; refuses on
  any clash or spacing break; no-op once there (D-050, D-052).
- `python3 scripts/pcb/mcu_escape.py --fanout | --decoupling`: a 0.2 mm stub and a 0.15 / 0.25 mm via from every MCU pin
  another part uses, staggered in two rows, clear of the crystals and the RF nets; then the MCU decoupling caps at ST's
  lands, the Nucleo's spots or the nearest free spot to their pin, top side (D-048). One shot each; no-op when done.
- `python3 scripts/pcb/gnd_vias.py --apply`: GND vias on a regular lattice, 0.15 / 0.25 mm: 33 in U301's exposed pad
  (0.8 mm, in the paste gaps) and a 1.2 mm stitching grid over ST's RF ground strip, skipping points that don't fit
  (D-049). One shot; no-op when done.
- `python3 scripts/pcb/render.py`: per-layer, side, overview and 3D renders into `docs/images/`.
- `python3 scripts/plugin.py <skill> <script> [args]`: run any hardware-design plugin script at the pinned tag
  (`PLUGIN_TAG`, fetched into the gitignored `.hw/`; `$HW` overrides). The export, BOM, stock, datasheet and visual-diff
  scripts below are thin wrappers around the plugin's (D-064).
- `python3 scripts/plugin_gates.py`: the plugin's gates as CI runs them (net classes, routing geometry, ground, the
  scripted design review), with ratchet limits at today's counts; reports in `plugin-gates/` (D-064).
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
