# NFC tag and I2C EEPROM

Both sit on I2C3 (PB10 SCL, PB11 SDA) with the Qwiic connector (D-031, D-039). The existing 2.2 kΩ pull-ups serve the
whole bus.

Since D-039 the **NFC corner is a copy of ST's X-NUCLEO-NFC01A1, board MB1163 rev C-01**. The copy covers:
- the tag, an M24SR64-Y;
- its ANT14 printed coil and tuning capacitors;
- its supply filter and pull-ups;
- ST's copper.

The owner's reason, as for the RF corner (D-037): follow the manufacturer's proven design instead of our own coil.

| Device | Part (LCSC) | I2C address (7-bit) | Other pins | Source |
|---|---|---|---|---|
| EEPROM 64 Kbit | M24C64-RMN6TP (C79988) | 0x50 (E2..E0 = 0) | WC low: writes enabled | DocID16891 Rev 33, Fig. 2, s2.3–2.4 |
| NFC tag, NFC Forum Type 4 (ISO 14443-A), 64 Kbit | M24SR64-YMN6T/2 (C222221) | 0x56 (device select 1010110x) | GPO (open drain) → PA2 / EXTI2, 20 kΩ pull-up; RF disable ← PA3, 30 kΩ pull-down | DocID023790 Rev 20, Table 1, s2.6–2.7, Table 80 |

External Qwiic devices must avoid 0x50 and 0x56.

**Bus loading.** Estimated bus capacitance is about 85 pF, below the 100 pF behind the 2.2 kΩ choice (SLVA689A window
967–3541 Ω at 400 kHz, `docs/design-calcs.md`).
- **ASSUMPTION:**
  - ≤ 10 pF per IC pin (MCU, EEPROM, NFC tag, ESD);
  - about 1 pF/cm over 15 cm of trace;
  - 30 pF for one Qwiic device with its cable.
- ST's own I2C pull-ups (R6 / R7 4k7) are copied as not fitted. Fitted, they would put 1.5 kΩ on the bus, still inside
  the window, but our 2.2 kΩ is the designed value.

## Provenance and licence

- **ST files**, uploaded by the owner and kept in the gitignored `reference/mb1163/`, never committed:

  | File | SHA-256 |
  |---|---|
  | `x-nucleo-nfc01a1_schematics.pdf` (MB1163 C-01) | `7847ac9166e011135a44ab7c49e325dd29b03b6b2674857e1f1517fd5f0fbc21` |
  | `x-nucleo-nfc01a1_gerbers.zip`: Gerbers, Excellon, pick-and-place, DRC rules | `a1fbee6806458fa21c830397e475ed1c2d07690f5868330554a49dbe14eca247` |

- **Licence:** ST's Open Platform License Agreement (www.st.com/opla), as for MB1355 (`docs/rf.md`). Everything derived
  carries "Derived from STMicroelectronics MB1163 rev C-01 (X-NUCLEO-NFC01A1)":
  - the `MB1163_*` footprints;
  - `scripts/pcb/mb1163_nfc.json`.
- **Tools:**
  - `scripts/nfc_reference.py` reads ST's Gerbers, drill file and pick-and-place directly; there is no Altium project
    for this board.
    - Nets come from copper connectivity, named from ST's schematic.
    - The script fails if a copper island would need two nets, if a pad's net differs from ST's schematic, or if the coil
      is not one path from AC0 to AC1.
  - `scripts/pcb/nfc_block.py --apply` pasted the corner once, as a group "MB1163 NFC corner" (ungrouped since D-046).
  - `scripts/nfc_coil.py` checks the coil (below).

## The circuit (MB1163 C-01 sheet 1)

| Ours | MB1163 | Part | Role |
|---|---|---|---|
| U803 | U1 | M24SR64-YMN6T/2 (C222221) | NFC Forum Type 4 tag, I2C |
| AE801 | Antenna1 "ANT14" | printed coil, `MB1163_ANT14` | 13.56 MHz antenna |
| C820, C819 | C8, C6 | 47 pF C0G 0603 (CL10C470JB8NNNC, C1671) | AC0 / AC1 to GND: 23.5 pF across the coil |
| C822, C821 | C9, C7 | not fitted | tuning spares, AC0 / AC1 to GND |
| C823 | C2 | not fitted | tuning spare across the coil |
| FB801 | L1 | Würth 742792042 (C5374796) | VCC ferrite |
| C803, C804, C818 | C3, C4, C5 | 1 µF tantalum 293D105X9016A2TE3 (C162327), 100 nF, 100 pF | VCC decoupling (NFC_VCC) |
| R810 | R8 | 20 kΩ | GPO pull-up (> 4.7 kΩ required, DocID023790 Table 1 note 1) |
| R804 | R9 | 30 kΩ | RF disable pull-down: RF on while the MCU is in reset (DocID023790 s2.6) |
| R805, R806 | R6, R7 | 4.7 kΩ, not fitted | ST's I2C pull-ups |

**Not copied:**
- the Arduino headers, LED1–LED3 and R1–R4;
- R5, the 0 Ω that routes RF disable to the headers;
- ST's routing from the cluster out to the headers.

**Host pins:**
- ST drove RF disable from PA7, our LED data line, so ours is on **PA3** (free, next to PA2).
- GPO stays on PA2.

## Coil: ANT14 (`scripts/nfc_coil.py`)

| Item | Value | Source |
|---|---|---|
| Geometry | 31.0 × 30.0 mm, 0.6 mm tracks at 1.2 mm pitch; about 4 turns on F.Cu spiralling in, a layer change, 3.5 turns on B.Cu spiralling out, wound the same way | `mb1163_nfc.json` |
| Inductance on MB1163 (2-layer 1.6 mm) | **2.295 µH** (Greenhouse, segments walked AC0 → AC1, B.Cu at 1.565 mm) | `nfc_coil.py` |
| Inductance on ours (JLC04161H-7628) | **2.298 µH** (B.Cu at 1.551 mm) | `nfc_coil.py` |
| Capacitance across the coil | C_TUN 25 pF typ (22.5–27.5) + C819 / C820 in series 23.5 pF + 1 pF pads (**ASSUMPTION**) | DocID023790 Rev 20; MB1163 schematic |
| f0 | **14.9 MHz** on both boards (14.6–15.3 over C_TUN); ours vs ST's −0.05 % | `nfc_coil.py` |
| Method check | Greenhouse vs modified Wheeler on a regular 4-turn spiral of ANT14's outline: +3.2 % | `nfc_coil.py` |

**What the numbers say:**
- **The copy keeps ST's tuning.** Our stack-up moves f0 by −0.05 %, because our outer copper layers sit 1.551 mm apart
  against ST's 1.565 mm.
- **The calculated f0 sits about 10 % above 13.56 MHz.** This calculation has two limits:
  - It doesn't include the capacitance between the stacked F.Cu and B.Cu spirals. Their overlap is roughly 6 pF in
    parallel-plate terms; part of it appears across the terminals and lowers f0.
  - ST's files don't state ST's target. Tags are often tuned above the carrier, because a reader's antenna pulls them
    down.
- **So measure before changing anything.**
  - To bring the calculated f0 to 13.56 MHz would take about +10.5 pF across the coil (C823), or about 21 pF on each of
    C821 / C822.
  - Fit these only after a loop-probe / VNA measurement or a phone read-range check.

## Layout

- **What is left of the copy (D-046, owner):** AE801, the 14 cluster parts, ST's 58 tracks and 13 vias; no group and no
  pours, all unlocked. ST's GND pour (F.Cu and B.Cu, cut to the cluster, 0.3 mm clearance) is gone: the owner pours the
  ground, and `NFC_POUR_GAP` still keeps any pour 4.4 mm from the coil. Every reference is on the silkscreen (D-041).
  `nfc_block.py` does nothing once AE801 is on the board.
- **Position:**
  - ST's layout is turned 90° counter-clockwise (a rotation, no mirror; owner, 2026-11-15: D-039's 180°, then 90°
    clockwise). The coil is at the right edge; the tag cluster sits to its left, toward the MCU.
  - The whole group sits 8 mm below the corner (`placement.NFC_DROP`), so the tag clears the RF corner's copper. In the
    corner it overlapped the MCU's VDDA / VREF caps and ST's RF ground-strip vias by 0.65 mm.
  - ANT14 copper spans x 10.5 to 40.5 and z 76.5 to 107.5 (mechanical, `docs/mechanical.md`). That is 2 mm in from the
    right edge (**ASSUMPTION**; ST had ≥ 7.6 mm of bare board around it on a board end).
  - U803 is at (−0.6, 91.6); the cluster spans about x −11 to +8, z 82 to 100.
- **Outline:** right of x +6.1 the top edge is back at z 117.5. x +6.1 is the coil's left edge minus ST's 4.4 mm
  coil-to-pour gap. Between the RF tab and x +6.1 the edge stays on MB1355's step at z 110.02 (D-037). With the coil
  8 mm lower, the strip above it (z 107.5 to 117.5) carries no parts, only the keep-outs.
- **Rule areas** (all four layers, so L2 is open under the coil, the NFC exception to "L2 never cut"):
  - `NFC_COIL`: the coil + 0.5 mm, to the board edges. No tracks, vias or pour; only the coil footprint's own copper.
  - `NFC_POUR_GAP`: the coil + ST's 4.4 mm pour gap (MB1163's pour edge). No pour or vias. ST's own cluster copper sits
    in it, as on MB1163.
- **Clearances:**
  - from metal: the battery's top edge (z 75, on the back) is **1.5 mm** below the coil. That is under the 5 mm this
    doc asked for: accepted by the owner with the 90° turn. Expect more downward detuning; C821–C823 are the spares;
  - from the 2.4 GHz antenna (x ≤ −14.0): ≥ 24.5 mm.
- **DRC and the routing gate:**
  - ST's GND T-branch on B.Cu (from the VSS via to the C6 / C8 ground vias) stays as copied.
  - ST's 90° corners are DRC exclusions in the project (D-046), so anything new is checked in full.
  - The routing gate runs with `--gate track_junctions=1` (and `jogs=4` for MB1355). Shorts, clearance and the fab
    floor are not relaxed.
- **Deviation:** ST's drill file lists ANT14's two layer changes as **non-plated** 0.5 mm holes. A non-plated hole
  would leave the coil open between F.Cu and B.Cu, so ours are plated (0.5 mm drill, 1.27 mm pads, as ST's lands).

## Firmware notes (`docs/firmware-interface.md`)

- **Type 4 command set:** the M24SR64-Y is not a plain I2C memory. The host opens an I2C session and selects the NDEF,
  system or CC file, then reads or updates binary. ST's X-CUBE-NFC1 driver is the reference.
- **RF disable (PA3):** high turns RF off. The 30 kΩ pull-down keeps RF on while the MCU is in reset.
- **GPO (PA2):** delivered as "session opened" (DocID023790 s2.7). It is configured in the system file.

## Open items

1. Measure f0 on the assembled robot (loop probe / VNA) and check the read range with an Android and an iOS phone; fit
   C823 or C821 / C822 only if the measurement asks for it.
2. ST's MB1163 BOM is not in hand. Confirm the 47 pF part (tolerance, dielectric) when it is; ours is C0G ±5%.
3. Owner: route NFC_GPO (PA2), NFC_RF_DIS (PA3), QWIIC_SDA / SCL and +3V3 into the cluster; pour the cluster's ground
   to the board-wide ground.
4. Owner: keep the bumper screws, the battery cradle and any metal out of `NFC_POUR_GAP`.
5. **ASSUMPTION:** the coil's 2 mm from the board edge. Check the phone read range with the bumper fitted.
6. The coil is 1.5 mm above the battery (owner, 2026-11-15). Measure f0 with the battery fitted, not on a bare board.
7. **`NFC_COIL` and `NFC_POUR_GAP` are off the board until the pours (owner, D-047).** The next `board.py` run re-adds
   them; until then nothing stops copper under or near the coil, which would detune it (D-039). C803 is back on ST's
   land in the cluster (D-051).
8. **The right LED ring's top row (D809–D811, D-050) sits in the 4.4 mm pour gap,** its pads about 1.6 mm below the coil.
   D-039's rule forbids vias and pour there, not pads, and ST's own cluster copper sits in the gap too. Keep the LED
   routing's vias out of it, and measure f0 with the LEDs fitted.
