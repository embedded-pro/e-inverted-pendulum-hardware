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
| R401 | R5 | 0R 0402, fitted | In the antenna path, as ST laid it out (ST's switch to the SMA; D-038) |
| C401 | C36 | not fitted | antenna-match shunt |
| L401 | L3 | 3.6 nH LQG15HS3N6S02D (C19216) | antenna-match series |
| C402 | C37 | 1.2 pF GJM1555C1H1R2WB01D (C76899) | antenna-match shunt |
| AE401 | (copper) | printed meander antenna, ST AN3359 type | `MB1355_Meander_Antenna` |
| L302 → L301 | L5 → L1 | 10 nH → 10 µH | SMPS: VLXSMPS → 10 nH → 10 µH → VFBSMPS (ST's order) |
| C314, C309, C318 | C29, C23, C24 | 4.7 µF, 4.7 µF + 100 nF | VFBSMPS; VDDSMPS |
| C307, C308 | C33, C34 | 100 nF, 100 pF | VDDRF (pin 33) |
| Y301 | X1 | NX2016SA 32 MHz (same part) | HSE, no external caps (HSETUNE) |
| Y302, C315, C316 | X2, C6, C7 | NX2012SA 32.768 kHz + 2 × 6.8 pF | LSE |
| SC401–SC404 | SC1–SC4 | Harwin S0951-46R clips, not fitted | 17.2 × 17.2 mm shield (custom part) |

**PCB antenna only (D-038):** MB1355's SMA branch (R13, C39, L4, C40, J2) and its copper are left out. R401 stays as
ST laid it out; its RF_50 pad is where a conducted test attaches (see Tuning and test).

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
- **Vias:** 60 of ST's vias are moved ≤ 0.045 mm, so that every hole is ≥ 0.20 mm from other-net copper (JLCPCB's
  published floor; ST used down to 0.16 mm).
- **No SMA branch** (D-038): R13 / C39 / L4 / C40 / J2 and their copper are not copied.
- **MCU decoupling on top** (D-038): see below.

## MCU decoupling (D-038)

Values are DS11929 Rev 11 §6.1.6 Fig. 16 (VDD n × 100 nF + 4.7 µF; VDDA 10 nF + 1 µF; VREF+ 100 nF + 1 µF) plus the
Nucleo's VBAT and VDDUSB caps. DS11929 asks for them "as close as possible to (or below) the appropriate pins on the
underside". This board is assembled on top only, so `scripts/pcb/rf_block.py` puts them on top:
- where the Nucleo has the cap on top, at the Nucleo's spot;
- where the Nucleo has it on the bottom, at the nearest top-side spot that clears ST's copper (courtyard and 0.15 mm
  pad clearance), measured centre to pin.

| Ours | Value | Pin | Nucleo (D-01) | Spot on our board |
|---|---|---|---|---|
| C308 | 100 pF | VDDRF 33 | C34, bottom | top, 1.75 mm (three ST GND vias removed, D-037) |
| C307 | 100 nF | VDDRF 33 | C33, bottom | top, 2.80 mm |
| C303 | 100 nF | VDD 68 | C18, top | Nucleo spot |
| C304 | 100 nF | VBAT 1 | C28, top | Nucleo spot |
| C305 | 100 nF | VDDUSB 55 | C31, top | Nucleo spot |
| C306 | 4.7 µF | VDD | C17 (100 nF), top | Nucleo spot, about 14.5 mm below the MCU, as ST's |
| C301 | 100 nF | VDD 30 | C19 / C20, bottom | top, 2.75 mm |
| C302 | 100 nF | VDD 45 | C19 / C20, bottom | top, 1.75 mm |
| C312 | 100 nF | VREF+ 13 | C32, bottom | top, 1.35 mm |
| C313 | 1 µF | VREF+ 13 | — | top, 4.35 mm |
| C310 | 10 nF | VDDA 14 | — | top, 2.90 mm |
| C311 | 1 µF | VDDA 14 | — | top, 4.75 mm |
| FB301 | BLM18PG221SN1D | VDDA 14 | L2 ferrite, bottom | top, 6.00 mm |
| C317 | 100 nF | NRST 8 | C3, bottom | top, 4.05 mm |

The crystals need nothing added: Y301 (HSE) has no external caps (HSETUNE), and Y302 with C315 / C316 sits on ST's lands
as copied (D-037). The decoupling is inside the group; its routing is the owner's.

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
  - right of the tab the top edge steps down to z 110.02, the ground line, as on ST (where ST's edge SMA sits; not
    fitted here, D-038), up to x +6.1, where it rises back to z 117.5 for the MB1163 NFC corner (D-039).
- **Keep-out:** rule area `ANTENNA_TAB` on all four layers: no pour and no vias.
  - A project DRC rule allows only the antenna feed (RF_ANT) to cross it.
  - It replaces the full-width `ANTENNA_KEEPOUT` / `ANTENNA_BASE` band of D-029.
- **Positions:** antenna feed at mechanical (−22.87, 110.26); the MCU centre is at about (−17.6, 97.2).
- **Near field:** no metal within about 5 mm of the tab.
  - The NFC coil (ANT14, x ≥ 10.5, D-039) is ≥ 24.5 mm away from the antenna (x ≤ −14.0).
  - The battery (top edge z 75, on the back) is ≥ 35 mm below.
  - The bracket holes are at the bottom.
  - The bumper screws must stay clear of the tab (the owner places them).

## Layout rules that come with the copy

- **The group:** "MB1355 RF corner" holds:
  - 34 footprints: U301, the RF-corner parts and the MCU decoupling (D-038);
  - 61 tracks and arcs and 317 vias;
  - the L1 / L2 / L3 / L4 ground of the RF strip;
  - the L2 cut-out and ST's four pad keep-outs.

  It is a group, unlocked (D-045): move or rotate it as one unit. `board.py` never moves it, and `rf_block.py` does nothing once it exists.
- **Project DRC rules** (`scripts/pcb/board.py`), each applying inside the group only:
  - clearance ≥ 0.10 mm (ST's own rule; JLCPCB's floor is 0.09);
  - ST's arcs and corner angles are exempt from the 45° rule;
  - ST's tight placement is allowed: shared 0R switch pad, crystal and clips.
  - The RF1 fan-out from pin 31 keeps 0.104 mm between the 0.4 mm-pitch pins.
- **Exception to "L2 is solid GND, never cut"** (CLAUDE.md): only the copied cut-out under the RF line and match.
- **Routing-quality gate:** ST's routing has four short sideways jogs (0.15–0.23 mm, on VFBSMPS, VDDSMPS and
  OSC32_IN, at the MCU pins). They stay as copied, so the gate is run as
  `pcb_rules.py check --allow-unrouted --gate jogs=4`. Shorts, clearance and the fab floor are not relaxed.
- **Silkscreen:** references on the silk where a 1.0 mm label fits clear of everything (D-041). 17 do not: C301, C307,
  C308, C310, C312, C314–C317, C401, C402, FL401, L302, L401, SC404, Y301, Y302. Their references are on F.Fab.
- **Ground and stitching:**
  - The L1 / L3 / L4 ground outside the copied strip, and the board-wide L2 plane, are the owner's pours.
  - Until then DRC lists ST's stitching vias in the shield area as dangling.

## Tuning and test

- **VNA tuning** in the final assembly (battery, motors and wheels fitted), per rf-layout §3. Target SWR ≤ 2 across
  2400–2483.5 MHz.
  - Tune with C401 (not fitted) and C402 (1.2 pF): the robot's ground plane, battery and motors differ from MB1355's.
  - The match is ST's starting point, not a guarantee for this chassis.
- **Conducted test:** remove R401 and solder a 50 Ω pigtail to its FL401-side pad (RF_50), shield to the L1 ground
  beside it. There is no connector since D-038.

## Open items

1. VNA-tune C401 / C402 on the assembled robot (the copy carries ST's match for MB1355, not for this chassis).
2. Ask JLCPCB whether they hold a non-standard GCPW (0.6 / 0.2 mm referenced to L3) under impedance control; if not,
   order without it.
3. Check AN5165 (RF hardware for STM32WB) and AN2867 against the copy once st.com can be read.
4. Owner: route the decoupling (C301–C313, C317, FB301) to its pins and +3V3, pour the board-wide ground, and keep the
   bumper screws clear of the tab.
5. Check the VDDA / VREF+ caps (4.35–6.0 mm from pins 13 / 14). They are the farthest; unlock the group to bring
   them closer if routing frees a spot.
