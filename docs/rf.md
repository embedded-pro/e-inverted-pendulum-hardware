# RF design: a copy of ST's NUCLEO-WB55 RF corner

The radio is chip-down with no certification (D-007). Since D-037 its **whole RF corner is a copy of ST's NUCLEO-WB55
board, MB1355 rev D-01**:
- the RF path and antenna;
- the VDDRF / VDDSMPS decoupling and the SMPS inductors;
- the HSE and LSE crystals.

The copy covers schematic values, parts and land patterns, and the copper as ST laid it out. The owner's reason: copy
the manufacturer's proven layout instead of designing our own, to lower the risk. The `rf-layout` skill still governs
what the copy doesn't decide; its sections are cited as rf-layout §n.

## Provenance and licence

- **ST files**, provided by the owner and kept in the gitignored `reference/mb1355/`, never committed (the repository is
  public):

  | File | SHA-256 |
  |---|---|
  | `mb1355_bdp.zip`: Altium projects MB1355C and MB1355D | `ad7be995776e9f944c29ef07bcb9332485e4587c921fab62ec7ab5afaca39811` |
  | `mb1355_bom.zip`: C02 and D01 BOMs | `5ce83a5293de09aaa038f3d7e7bf76d534de2dc20eeb9228fb7f1be404a95dc0` |
  | `mb1355-wb55rg-d01_schematic.pdf` | `ba5a0e923b8c7be2b7bbff5ed9b2aba39222fa39b449c3b1ae075841b3643a88` |

- **Licence:** the files come under ST's **Open Platform License Agreement** (www.st.com/opla).
  - Everything derived from them carries "Derived from STMicroelectronics MB1355 rev D-01": the `MB1355_*` footprints,
    `scripts/pcb/mb1355_rf.json` and the values.
  - The OPLA text itself couldn't be read from this environment (st.com blocks automated access); the owner accepted it
    when downloading.
- **Tools:**
  - `scripts/rf_reference.py` reads `MB1355D/MB1355.PcbDoc` through KiCad 10's Altium importer and writes:
    - `scripts/pcb/mb1355_rf.json`: parts, copper, vias, zones, rule areas, the tab outline and the net map;
    - the `MB1355_*` footprints: ST's land patterns re-centred on their pads, plus the antenna as one custom pad.
  - `scripts/pcb/rf_block.py --apply` pastes the corner onto our board, once.

## The circuit (MB1355 D-01 sheet 3 and BOM)

| Ours | MB1355 | Part | Role |
|---|---|---|---|
| FL401 | U12 | MLPF-WB55-01E3 (C2651048) | IPD: match + low-pass filter (DS12804) |
| R401 | R5 | 0R 0402, fitted | "RF switch": RF_50 → PCB antenna |
| C401 | C36 | not fitted | antenna-match shunt |
| L401 | L3 | 3.6 nH LQG15HS3N6S02D (C19216) | antenna-match series |
| C402 | C37 | 1.2 pF GJM1555C1H1R2WB01D (C76899) | antenna-match shunt |
| AE401 | (copper) | printed meander antenna, ST AN3359 type | `MB1355_Meander_Antenna` |
| R402 | R13 | 0R, not fitted | "RF switch": RF_50 → SMA |
| C403, C404 | C39, C40 | not fitted | SMA filter / match shunts |
| R403 | L4 | 0R 0402, fitted | SMA branch series element |
| J401 | J2 | edge SMA, not fitted | ST's `SMA_T_9.52_NF` land |
| L302 → L301 | L5 → L1 | 10 nH → 10 µH | SMPS: VLXSMPS → 10 nH → 10 µH → VFBSMPS (ST's order) |
| C314, C309, C318 | C29, C23, C24 | 4.7 µF, 4.7 µF + 100 nF | VFBSMPS; VDDSMPS |
| C307, C308 | C33, C34 | 100 nF, 100 pF | VDDRF (pin 33) |
| Y301 | X1 | NX2016SA 32 MHz (same part) | HSE, no external caps (HSETUNE) |
| Y302, C315, C316 | X2, C6, C7 | NX2012SA 32.768 kHz + 2 × 6.8 pF | LSE |
| SC401–SC404 | SC1–SC4 | Harwin S0951-46R clips, not fitted | 17.2 × 17.2 mm shield (custom part) |

**Connector options:**
- Default: R401 fitted, so RF_50 drives the PCB antenna.
- To use J401 instead (external 50 Ω antenna or instrument): fit R402 0R, remove R401, fit J401.

**Deliberate differences from MB1355**, each owner-approved and recorded in D-037:
- **VDDRF caps on top.**
  - ST has C33 / C34 on the bottom under pin 33; this board is top-assembled.
  - C308 (100 pF) sits right above pin 33 (1.8 mm, centre to centre), after removing three of ST's GND vias.
  - C307 (100 nF) sits about 2.8 mm away, at the nearest spot that clears ST's copper.
  - Both are routed by the owner.
- **SMPS inductors:** ST's parts are out of stock at JLCPCB (74479777310A: 2 left; LQP15MN10NG02D: 0).
  - LQM21FN100M80L (10 µH) and LQG15HS10NJ02D (10 nH) sit on ST's pads.
  - ST's part numbers are listed as alternates in `bom/parts.csv`.
- **LSE:** ST's C_L 7 pF crystal (EXS00A-MU00389) isn't stocked.
  - NX2012SA STD-MUB-3 (C_L 6 pF, C889705) sits on ST's land with 2 × 6.8 pF (AN2867; ST: 2 × 10 pF).
  - With 10 pF, either stocked variant would pull 30–40 ppm.
- **Shield:** ST's 17.2 mm brass shield is a custom part. The clip pads are copied; the clips and the shield are not
  fitted.
- **Vias:** 104 of ST's vias are moved ≤ 0.05 mm, so that every hole is ≥ 0.20 mm from other-net copper (JLCPCB's
  published floor; ST used down to 0.16 mm).

## Stack-up and the RF line

| Item | Value | Source |
|---|---|---|
| Our stack-up | JLC04161H-7628, 1.6 mm (unchanged, D-008 / D-036) | JLCPCB |
| MB1355 stack-up | L1 1.6 mil / 18 mil FR-4 Dk 4.2 / L2 1.2 mil / 20 mil Dk 4.4 / L3 / 18 mil / L4 | `MB1355.PcbDoc` |
| RF line (copied) | 0.6 mm on L1, 0.2 mm gaps to the L1 ground pour | `mb1355_rf.json` |
| Reference plane | **L3**: ST cuts L2 out under the line and the match (copied as rule area "MB1355 L2 cut-out"); L3 is ground under the RF strip | `MB1355.PcbDoc` |
| Z0 on MB1355 | 56.3 Ω (corners 51.1–61.5) | `scripts/gcpw.py` |
| **Z0 on ours** | **56.9 Ω** (corners 51.9–61.9): +0.6 Ω vs ST | `scripts/gcpw.py` |
| Same line over an uncut L2 | 33.9 Ω, which is why the cut-out is part of the copy | `scripts/gcpw.py` |

- **Why our stack-up is close enough:** ST references the line to L3, about 1 mm down, so the line is set mostly by its
  0.2 mm coplanar gaps. Our L1→L3 is 1.29 mm and theirs 0.995 mm.
  - The owner kept JLC04161H-7628 (no stack-up change) after this was found. JLC04161H-2116A, which matches ST's
    0.457 mm L1→L2, would have given 56.6 Ω.
  - The model ignores the solder mask, which lowers both lines by about 1–2 Ω.
- **Impedance-control note for the order:** the line is not a textbook 50 Ω on L2.
  - Order impedance control only if JLCPCB will hold ST's geometry as drawn (0.6 / 0.2 mm, L1 referenced to L3).
  - Otherwise order without it. The geometry is ST's, and the VNA step covers the residual.
- **Calculator check:** `gcpw.py` reproduces ST's DS12804 Fig. 13 line (47.9 Ω, against ~50 Ω expected).

## Antenna and the tab

- **Antenna:** the meander antenna of MB1355 (ST AN3359 type), copied as copper: one custom pad on F.Cu, under solder mask.
- **The tab**, with MB1355's outline copied at our top-left corner (D-037, D-024 amended):
  - 28.5 mm wide, from the left edge to x −14.0, with ST's 45° chamfers;
  - the board edge is 1.1 mm above the antenna;
  - ground starts 7.5 mm down, at z 109.98;
  - right of the tab, the whole top edge steps down to z 110.02, the ground line, where J401's edge SMA lands (as on ST).
- **Keep-out:** rule area `ANTENNA_TAB` on all four layers: no pour and no vias.
  - A project DRC rule allows only the antenna feed (RF_ANT) to cross it.
  - It replaces the full-width `ANTENNA_KEEPOUT` / `ANTENNA_BASE` band of D-029.
- **Positions:** antenna feed at mechanical (−22.87, 110.26); the MCU centre is at about (−17.6, 97.2).
- **Near field:** no metal within about 5 mm of the tab.
  - The NFC coil (x ≥ 16) is ≥ 30 mm away.
  - The battery (top edge z 75, on the back) is ≥ 35 mm below.
  - The bracket holes are at the bottom.
  - The bumper screws must stay clear of the tab (the owner places them).

## Layout rules that come with the copy

- **The group:** "MB1355 RF corner" holds:
  - the 27 copied footprints, including U301;
  - 69 tracks and arcs and 317 vias;
  - the L1 / L2 / L3 / L4 ground of the RF strip;
  - the L2 cut-out and ST's four pad keep-outs.

  It is locked: move or rotate it as one unit. `board.py` never moves it, and `rf_block.py` does nothing once it exists.
- **Project DRC rules** (`scripts/pcb/board.py`), each applying inside the group only:
  - clearance ≥ 0.10 mm (ST's own rule; JLCPCB's floor is 0.09);
  - ST's arcs and corner angles are exempt from the 45° rule;
  - ST's tight placement is allowed: shared 0R switch pad, crystal and clips.
  - The RF1 fan-out from pin 31 keeps 0.104 mm between the 0.4 mm-pitch pins.
- **Exception to "L2 is solid GND, never cut"** (CLAUDE.md): only the copied cut-out under the RF line and match.
- **Routing-quality gate:** ST's routing has four short sideways jogs (0.15–0.23 mm, on VFBSMPS, VDDSMPS and
  OSC32_IN, at the MCU pins). They stay as copied, so the gate is run as
  `pcb_rules.py check --allow-unrouted --gate jogs=4`. Shorts, clearance and the fab floor are not relaxed.
- **Silkscreen:** the corner's references are on F.Fab (too dense for silk); elsewhere D-035 holds.
- **Ground and stitching:**
  - The L1 / L3 / L4 ground outside the copied strip, and the board-wide L2 plane, are the owner's pours.
  - Until then DRC lists ST's stitching vias in the shield area as dangling.

## Tuning and test

- **VNA tuning** in the final assembly (battery, motors and wheels fitted), per rf-layout §3. Target SWR ≤ 2 across
  2400–2483.5 MHz.
  - Tune with C401 (not fitted) and C402 (1.2 pF): the robot's ground plane, battery and motors differ from MB1355's.
  - The match is ST's starting point, not a guarantee for this chassis.
- **Conducted test:** fit R402 and J401, remove R401.

## Open items

1. VNA-tune C401 / C402 on the assembled robot (the copy carries ST's match for MB1355, not for this chassis).
2. Ask JLCPCB whether they hold a non-standard GCPW (0.6 / 0.2 mm referenced to L3) under impedance control; if not,
   order without it.
3. Check AN5165 (RF hardware for STM32WB) and AN2867 against the copy once st.com can be read.
4. Owner: route C307 / C308 to pin 33 and +3V3, pour the board-wide ground, and keep the bumper screws clear of the tab.
