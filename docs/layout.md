# PCB layout (Phase 3): placement brief for the owner

Status: **hand-off (2026-11-13, D-032).** The owner places the components in KiCad. The board starts as a clean
slate:
- **on the board:** the outline, the keep-out rule areas, the reference drawings and the WHEELTEC bracket holes;
- **the MB1355 RF corner (2026-11-15, D-037):** the MCU, RF path, antenna, SMPS, crystals and their copper, pasted at the
  top-left corner (`scripts/pcb/rf_block.py`, `docs/rf.md`); ungrouped, its pours removed (D-046);
- **staging area right of the board:** every other part, grouped by schematic sheet (`docs/images/overview.png`).

From now on the `.kicad_pcb` is the source of truth for placement. `scripts/pcb/board.py` never moves, reshapes or deletes
anything on the board.

**Sources:**
- `docs/mechanical.md`: coordinates, bracket, battery, mass;
- `docs/rf.md`: 2.4 GHz antenna and RF path;
- `docs/nfc.md`: NFC coil;
- `docs/power-map.md`: net classes and current paths;
- decisions D-025 to D-032;
- the `power-pcb-layout`, `pcb-design-rules`, `rf-layout` and `interface-layout` skills.

## Board

| Item | Value | Source |
|---|---|---|
| Outline | 85 mm wide; 130 mm tall at MB1355's antenna tab (top-left, x −42.5 to −14.0) and right of x +6.1 (MB1163 NFC corner), 122.5 mm between them (top edge z 110.02); 1 mm radii on the other corners | D-024, D-037, D-039 |
| Coordinates | Grid origin on the wheel axle at the centre line (x = 0, z = 0); the bottom edge is z −12.5, the top edge z 117.5 (KiCad Y = 150 − z) | D-026 |
| Stack-up | JLC04161H-7628: L1 0.035 / 7628 0.2104 / L2 0.0152 / core 1.065 / L3 0.0152 / 7628 0.2104 / L4 0.035 mm | D-008 |
| Layers | L1 parts, RF, short power pours · L2 solid GND, never cut except MB1355's cut-out under the RF line · L3 VBAT/5V0/3V3 pours, slow signals, GND under the RF strip · L4 signals + GND fill | `docs/plan.md`, D-037 |
| Net classes | PWR_BUS 2.2 mm, MOTOR 0.8, SWITCH 0.5, SUPPLY 0.5, GATE 0.3, RF 0.6 / 0.2 gap (MB1355), NFC 0.25, SENSE and CRYSTAL 0.2, Default 0.2 / 0.15 | `docs/power-map.md` |
| Fab rules | JLCPCB: track / space 0.09, via 0.15 / 0.25, via ring 0.05, PTH ring 0.15, hole-to-hole 0.20 (PTH 0.45), hole-to-copper 0.20 (PTH 0.28), edge 0.20, NPTH ≥ 0.50, silk text ≥ 1.0 / 0.15 mm | D-036, `pcb-design-rules` profiles |
| Silkscreen | Only the test pads' net names: 1.0 mm text, 0.15 mm line (JLCPCB's minimum), clear of every label, outline, pad, via, body and the edge, 0.5 mm from each other so two names never read as one, next to their pad; every other part's reference is on F.Fab (the assembly drawing), sized inside the part; nothing on a net tie. Outlines at 0.15 mm, pin-1 marks and J101's polarity stay | D-035, D-041, D-052, `scripts/pcb/silk.py` |
| Assembly spacing | 0.5 mm between neighbouring parts' pads and bodies (IPC-7351B medium density), 2.5 mm from every part's body to the board edge (JLCPCB assembly terms, DFM items 1 and 3); test pads count as pads, antennas, net ties and holes don't | D-052, `place_block.py`, `scripts/pcb/respace.py --check` |
| Page | A3, so the staging area fits on the sheet | — |

## What DRC enforces (rule areas and project rules)

These are on the board as rule areas (they can be moved or edited in KiCad) and in `hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_dru`.

**Off the board until the pours (owner, D-047):** `ANTENNA_TAB`, `NFC_COIL`, `NFC_POUR_GAP`, `BATTERY_BACK` and MB1355's
L2 cut-out under the RF line were deleted in KiCad. The next `scripts/pcb/board.py` run re-adds the four board areas;
the L2 cut-out comes back with the L2 pour (`docs/rf.md`). Until then the project rules that name them check nothing,
and silk.py keeps labels off the tab's polygon from `placement.py`.

| Name | Where | Rule | Why |
|---|---|---|---|
| `ANTENNA_TAB` | MB1355's tab, x −42.5 to −14.0, z 109.98 → top edge, all layers | no vias or pour; only the antenna feed (RF_ANT) may cross it (project rule) | Ground-free antenna tab (D-037, `docs/rf.md`) |
| project rules (D-046) | the MB1355 and BOOST-DRV8711 copies | ST's 0.10 mm on the RF / SMPS / HSE nets and C318, TI's 0.178 mm on DRV_* nets (not to pours); Y301 / Y302 tight placement; the copied 90° corners are DRC exclusions | Vendor geometry kept as copied; anything new is checked in full |
| `NFC_COIL` | ANT14 + 0.5 mm: x 10.0 → edge, z 76.0 → edge, all layers | no tracks, vias or pour (the coil footprint excepted) | MB1163 copy (D-039, `docs/nfc.md`) |
| `NFC_POUR_GAP` | ANT14 + ST's 4.4 mm coil-to-pour gap: x 6.1 → edge, z 72.1 → edge, all layers | no vias or pour | ST's pour edge on MB1163; ST's own cluster copper sits in it |
| `BRACKET_STRIP` | bottom 25 mm, front and back | **no footprints** except the bracket holes MB1–MB8 (project rule) | Chassis attachment (D-026) |
| `BRACKET_BASE_CONTACT` | bottom 25 mm, B.Cu | no tracks, vias or pour | The steel bracket base sits on the back |
| `BATTERY_BACK` | x ±38.5, z 39–76, B.Cu | **no through-hole pins** (project rule; NPTH holes allowed), except J601 / J602 / J101 over the cradle's relief | The battery lies on the back (D-025, D-044, D-047) |
| project rule | RF1 net | 0.104 mm clearance | MB1355's 0.265 mm fan-out from pin 31 between the 0.4 mm-pitch pins |
| project rule | NPTH holes | 0.5 mm hole-to-copper | Screw threads touch the hole wall |
| project rule | silkscreen outlines of two parts | may sit closer than 0.15 mm, never overlap; labels keep 0.15 mm to everything (silk checks are errors) | JLCPCB gives no silk-to-silk figure; KiCad applies its silk-to-pad 0.15 mm to both (D-041) |

## Placement guidance (from the design docs)

- **RF (`docs/rf.md`):** done by the copy (ungrouped, no pours since D-046). It holds:
  - U301, FL401, the match and AE401 (no SMA branch, D-038);
  - L301 / L302, Y301 / Y302 and their caps (the shield-clip pads SC401–SC404 were removed by the owner, D-047);
  - the MCU decoupling on top, at the Nucleo's spots or the nearest free spot to each pin (D-038, `docs/rf.md`);
  - ST's copper, vias and ground (the owner removed the ground field's 236 vias, D-047; the 54 beside the RF line stay).

  The MCU decoupling the owner parked (D-047) is back on top after the fan-out (D-048, `scripts/pcb/mcu_escape.py
  --decoupling`, `docs/rf.md`). R301 (SPI1 SCK termination) and C803 of the NFC cluster are placed with the rest
  (D-051, below).

  Its position on the outline (the tab) is part of the copy. Still yours:
  - route the decoupling (C301–C313, C317, FB301) to its pins and +3V3;
  - route the MCU's signals on from the fan-out vias (below);
  - pour the RF strip's ground over the 1.2 mm stitching grid (D-049, `scripts/pcb/gnd_vias.py`); U301's exposed pad
    has 33 ground vias on a 0.8 mm lattice in its paste gaps;
  - pour the board-wide ground.
- **MCU fan-out (D-048, `scripts/pcb/mcu_escape.py --fanout`): done.** Each of the 38 U301 pins another part uses
  has a 0.2 mm stub on F.Cu to a 0.15 / 0.25 mm via, 0.30 or 0.75 mm past the pad (0.40 mm for pins 6 and 16),
  alternating rows. Route on from the vias on any layer; the via size is in the project's via list. Power, ground and
  the copy's own nets (crystals, RF1, SMPS) have no fan-out: they stay with their parts on top.
- **IMU, flash and EEPROM (D-043, D-047, `scripts/pcb/place_block.py imu_memory`): placed by the owner.**
  - U701 (MPU-6500) on the centre line at (0, 78), rotation 0: its position and axes are published
    (`docs/firmware-interface.md`). C701 / C702 / C703 at VDD / VDDIO / REGOUT, R701 (nCS pull-up) above it.
  - U702 (W25Q16JV) left of the MCU at (−26.2, 82.9), turned 180°; U802 (M24C64) above it in the same column at
    (−26.3, 89.0) (D-047).
  - Their support parts and test pads are placed with the rest (D-051, below): C704 and R702–R704 at U702's pins, R301
    (SPI1 SCK 33 Ω) on the SCK route, C802 at U802, the I2C3 pull-ups R808 / R809 at the Qwiic port, TP701–TP706 in one
    row left of the IMU.
  - Still yours, routing: SPI2 from the MCU's left pins (46–50) to the IMU, about 30 mm, under the NFC cluster; I2C3 from
    the MCU's top pins (28 / 29) around its left side and down to the EEPROM, about 50 mm (inside the bus
    budget's 15 cm, `docs/nfc.md`); SPI1 and FLASH_NCS from the bottom pins. Keep them off the RF
    strip and the L2 cut-out under the RF line.
- **NFC (`docs/nfc.md`):** done by the copy (ungrouped, no pours since D-046). It holds AE801 (ANT14), U803 (M24SR64-Y) and
  ST's cluster (FB801, C803 / C804 / C818–C823, R804–R806, R810) with ST's tracks and vias, turned 90° from ST's
  board and 8 mm below the corner: the coil at the right edge, the tag to its left, beside the MCU. Still yours (the cluster's GND pour included): route NFC_GPO (PA2), NFC_RF_DIS (PA3),
  QWIIC_SDA / SCL and +3V3 into the cluster; keep metal (screws, battery cradle) out of `NFC_POUR_GAP`.
- **Motor drive (`docs/drive.md`):** done by the copy (ungrouped, its 12 pours removed since D-046). It holds TI's power stage (U501,
  Q501–Q504, R509 / R512, the net ties NT501–NT504 on B.Cu, C507–C514) with TI's tracks and vias, turned 180°
  (FETs nearest the strip; bridge A on the right drives the right motor, B the left, D-042), from z 13.5 to 50.5, centred on x +10.85 since the owner moved it 2.85 mm right (D-047) and D-050 another 8 mm (`scripts/pcb/shift_block.py drive`), and our extras at the nearest free spots (SS34 D501–D504, C501–C506, R515–R518). Still yours: the power copper
  the pours carried (VM, phases, GND_A / GND_B), the phase outputs to J601 / J602, the logic pins to the MCU, the board-wide ground.
- **Power (D-049, `scripts/pcb/place_block.py power`, `docs/power-map.md`, power-pcb-layout §3): placed** right of the
  power entry, x −15.5…+3.5, z 51.2–64.1, all on top, to TI's layout guidance (TPS62933 datasheet ZHCSO99D §12.1, Fig.
  12-2):
  - U201 (TPS62933F) at (−7.7, 58.0), VIN / GND pins toward the power entry; C203 (100 nF) the closest part to VIN /
    GND, C202 / C201 (10 µF) beside it, so VBAT arrives from the left and the input loop is the smallest on the block.
  - C204 (BST) between BST and SW; L201 right of U201, its SW pad facing pin 5; the SW node is about 2 mm of copper,
    17 mm from the IMU.
  - C208 / C206 / C207 (output) under L201, +5V pads up; U202 (TLV75533P) beside them, IN / EN toward C209, OUT toward
    C210.
  - R201 / R202 (EN), C205 (SS), R204 / R203 (FB) in a row above U201, the FB pair over FB (pin 8), away from SW;
    TP201 (+5V), TP203 (GND) and TP202 (+3V3) right of L201 (moved there by D-050 so the LED rings leave their labels room).
  - Still yours, routing: VBAT and GND wide to C201–C203 and U201 with vias to L2; the SW node short and minimal,
    nothing under it on L3 / L4; the +5V sense to R203 from the output caps, away from L201; +5V on to the encoders and
    the LEDs, +3V3 on the L3 plane.
- **Motor connectors and encoder inputs (D-042, D-044, D-047, `scripts/pcb/place_block.py motor_io`): placed, arranged
  by the owner.**
  - J601 at the left edge and J602 at the right, plug entering from the side, pins at x ±33.65 (2.05 mm inward for
    JLCPCB's 2.5 mm body-to-edge, D-052) from z 35.5 to 45.5
    (raised 20 mm, D-044). The upper four pins of each sit over the battery's edge: the cradle needs a
    relief there (`docs/mechanical.md`). J601's pin 1 (M−) is at the top, J602's at the bottom.
  - Inward from each connector: the ESD (U601 / U603) beside pins 2–5, the four row parts (pull-up DNP, 100 Ω, 100 Ω,
    pull-up DNP) in a column at x ±31.5…32, the 1 nF caps at x ±28.2…28.75, then the SN74LVC3G17 (U602 / U604) at
    x −27.5 / +27.75 with its bypass; TP601 / TP602 beside U602. C603 / C607 (snubbers, DNP) below the connectors.
  - The encoder supply (R601 / R602, F601, C601 / C602) sits below the left chain, z 28–32.
  - TP603 / TP604 (right encoder outputs) beside U604 and TP605 / TP606 (ENC_VCC, GND) below the encoder supply are
    placed with the rest (D-051).
  - Still yours, routing:
    - Both motor pins leave at the bottom of the connector and run about 22 mm down the side to the phase pours that end
      at z 13.5 on the same side.
      The top motor pin's trace runs down under the housing, outboard of the pads, so no motor copper passes the
      encoder rows.
    - Connector → ESD with no via and no stub, a GND via at the ESD's GND pins (interface-layout §2).
    - ENC_VCC across to J602; the buffered outputs to PC0 / PC2 (left) and PA0 / PA1 (right).
- **Power entry and debug (owner, D-047; `place_block.py power_entry`, D-052): placed.** J101 (XT30) at the left edge,
  pins at x −37.1, z 56.4 / 61.4 (0.9 mm inward for the 2.5 mm edge rule), with F101, Q101, D101 / D102, C101–C103 and
  R101–R105 beside it (x −37…−18, z 50–63); J301 (STDC14) left of the MCU at (−36.2, 97.2), its body 3.2 mm from the edge.
- **RGB LEDs and status LED (D-050, `scripts/pcb/place_block.py leds`): placed** in the centre as two square rings,
  mirrored about the centre line between the power block and the IMU:
  - each ring has 6 WS2812B-2020 on a 7.0 mm square (corners plus the middle of the top and bottom sides, 3.5 mm pitch),
    centred at (−9, 70.5) and (+9, 70.5);
  - the chain runs D802 (bottom middle, left ring) round the left ring to D807, across to D808 and round the right ring
    to D813;
  - each LED's 100 nF cap sits inside its ring at the VDD pad (bottom row at 0°, top row at 180°);
  - U804 (level shifter) with C801, R803, R802 at its output, C805 (bulk) and TP801 are left of the left ring;
  - D801 (green status) with R801 sits on the centre line between the rings.
  - Still yours, routing: the data chain in order (U804 → R802 → D802 DIN … D813), +5V and GND to every LED through
    its cap, LED_DATA from PA7's fan-out via. Keep vias out of the NFC pour gap (x ≥ 6.1, z ≥ 72.1): the right ring's
    top row sits in it, 1.6 mm below the coil (`docs/nfc.md`).
- **The rest (D-051, `scripts/pcb/place_block.py rest`): placed.** Edge parts first, then the support parts at their
  pins, then the test pads in rows per block in the room left. Every spot keeps the existing silkscreen labels where
  they are and leaves its own label a clean spot. Since D-052 only the test pads' names are on the silkscreen, all of
  them clean; the edge parts sit 2 mm further in.
  - SW101 (power switch) at the left edge above the battery, turned 90°: pins at x −36.5, z 79.0 / 83.7 / 88.4, between
    J801 and J301, lever on top (`docs/mechanical.md`). SW_ON runs about 30 mm down to R102.
  - J801 (Qwiic) at the left edge between J101 and SW101, the cable entering from the edge, pads at x −35.18, z 68.5–71.5;
    U801 (its ESD) beside the pads for pass-through routing (interface-layout §2); R808 / R809 (I2C3 pull-ups) right of
    U801, where the bus enters.
  - C704 / R702–R704 at U702's VCC, /CS, /WP, /HOLD; C802 at U802's VCC; R301 6 mm down the SCK route from its fan-out
    via; R302 3.8 mm from the BOOT0 via; C803 on ST's MB1163 land (D-039).
  - Test pads, 2.4 mm pitch (2.7 mm next to a 1.5 mm pad):
    - power entry: a column at x −28, z 73.5 → 63.0 (BAT_F, PP_G, VBAT, GND, VBAT_SENSE), BAT_F / PP_G nearest Q101;
    - Qwiic: a column at x −24, z 72.6 → 67.2 (SDA, GND, SCL);
    - drive logic: a row at z 53.5, x 9.0 → 28.2 (nFAULT, MISO, SCS, MOSI, SCK, AIN2, AIN1, BIN1, BIN2), above the
      DRV8711's logic vias, in their order;
    - drive power: one row per bridge, below each motor's phase route: z 29.0, x −17.0 → −9.5 (MOT_L_P, MOT_L_N,
      SENSE_B, GND) and z 28.0, x 27.0 → 34.5 (GND, SENSE_A, MOT_R_N, MOT_R_P);
    - MCU: a row above J301 at z 104.0, x −37.5 → −32.7 (NRST, VFBSMPS, BOOT0); TP303 (VDDA) beside the VDDA caps at
      (−6.0, 98.5), 2.1 mm from C311's pad (D-052);
    - IMU and flash: a row left of the IMU at z 80.9, x −16.9 → −4.9 (FLASH_NCS, IMU_NCS, SCK, MOSI, MISO, INT);
    - encoders: TP603 / TP604 beside U604 at (23.45, 44.5) / (23.45, 36.0), in the right chain's table since D-052;
      ENC_VCC / GND at z 26.0 below F601.
  - Still yours, routing: SW_ON to R102; I2C3 J801 → U801 → R808 / R809 → U802 → MCU and on to U803; each test pad's
    stub to the copper it probes, short and on top.
- **Through-hole parts:** J101 XT30, SW101 switch, J601/J602 PH 6-pin. They must stay outside `BATTERY_BACK`, except
  J601 / J602 and J101, whose pins sit over the cradle's relief (D-044, D-047, project rule). SW101's pins are above the
  battery (z ≥ 79).
- **Assembly spacing (D-052):** `python3 scripts/pcb/respace.py --check` lists any two parts closer than 0.5 mm and any
  body within 2.5 mm of the edge; `--apply` moves the parts no table holds by the smallest step, keeping their tracks at
  their angles. It moved 24 parts, among them the vendors' Y301, C309, C314–C316, C318, L301, L401, C401 (ST) and C510,
  C511, C514 (TI) by 0.05–0.35 mm, and our MCU caps C302, C303, C307, C308 by 0.45–2.0 mm (their nearest pad now
  1.9–3.6 mm from the pin). D504 and C503 left TI's copper they sat on: route them. Run `--check` after moving parts.
- **Holes for you to place (staged under "Mechanical", the only parts still off the board, D-051):** battery cradle
  MC1–MC4 and bumpers MH1/MH2. Footprints
  `MountingHole_M3_NPTH_KeepOut7mm` and `..._M2_..._KeepOut5.5mm` are in the project library for more.

## After placing

1. Save in KiCad, then lock the parts you consider fixed (they become the anchors for routing; power-pcb-layout §1).
   The scripts lock nothing (D-045), and the three copies are no longer groups (D-046): every part, track and via selects
   on its own.
2. Re-sync and check. This keeps every position:

   ```bash
   python3 scripts/pcb/board.py --rules <path to pcb_rules.py>
   ```

   It ends by laying the silkscreen labels out (`scripts/pcb/silk.py`, D-041, D-052): the test pads' names that are clean
   stay put, the others move next to their pad; references go to F.Fab. `python3 scripts/pcb/silk.py --check` reports
   without changing anything; `--relayout` lays every name out afresh. `python3 scripts/pcb/respace.py --check` checks
   JLCPCB's assembly spacing.

   ```bash
   kicad-cli pcb drc --schematic-parity --severity-all hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pcb
   ```

   ```bash
   python3 scripts/pcb/render.py
   ```

3. Phase 3 steps 4–8 follow: support placement around your anchors, power copper, critical routes, the rest of the
   routing, fills, DRC and fab outputs.

## Previous generated draft (gate A v2, not applied; superseded by the MB1355 RF corner, D-037)

For reference only; the owner rejected it. Mechanical coordinates (mm, front view), rotation in degrees.

| Ref | x | z | Rot | Why |
|---|---|---|---|---|
| AE401 | +0.00 | +111.35 | 0 | SWRA117D IFA at the top edge, above RF1 (D-029, docs/rf.md) |
| U301 | +2.00 | +97.50 | 180 | STM32WB55 at the top centre, rotated so RF1 (pin 31) faces the antenna |
| FL401 | +0.25 | +103.94 | 0 | MLPF IN 1.5 mm from the RF1 pad (DS12804 Fig. 13) |
| Y301 | -4.50 | +101.50 | 0 | HSE 32 MHz at OSC_IN/OSC_OUT (pins 35/34) |
| J401 | -5.50 | +106.80 | 0 | U.FL conducted test port (DNP), beside the RF_50 line |
| U701 | -12.00 | +94.00 | 0 | MPU-6500 beside the MCU's SPI2 pins (left side after rotation) |
| U803 | +11.00 | +101.00 | 180 | ST25DV04KC: AC0/AC1 toward the coil, I2C and GPO toward the MCU |
| U802 | +11.00 | +89.00 | 180 | M24C64 EEPROM on I2C3 |
| AE801 | +29.00 | +95.50 | 0 | NFC coil 25 x 21 mm, top-right, above the battery outline |
| U702 | -2.00 | +86.00 | 0 | W25Q16 flash below the MCU's SPI1 pins |
| SW101 | -37.70 | +103.00 | 0 | power switch at the top-left (it only switches the SW_ON gate line) |
| D801 | -20.00 | +107.50 | 0 | green LED at the top |
| D802 | -16.00 | +107.50 | 0 | red LED at the top |
| SW301 | +10.00 | +78.00 | 0 | BOOT0 button |
| SW801 | +20.00 | +52.00 | 0 | user button |
| BZ801 | +20.00 | +66.00 | 0 | buzzer |
| J301 | +38.00 | +59.00 | 0 | STDC14 debug at the middle of the right edge (D-029) |
| J801 | +39.00 | +72.00 | 90 | Qwiic (I2C3), entry from the right edge |
| U201 | -20.00 | +60.00 | 0 | TPS62933F buck, mid-left, far from the antenna and the IMU |
| L201 | -15.50 | +60.00 | 0 | buck inductor at SW |
| J101 | -37.50 | +33.50 | 0 | XT30 battery socket on the left edge, below the battery band (THT) |
| F101 | -37.00 | +41.00 | 0 | battery fuse after the XT30 |
| Q101 | -29.50 | +43.00 | 0 | AO4805 back-to-back power switch |
| D102 | -20.00 | +44.00 | 0 | SMBJ15A TVS after the power switch |
| J601 | -35.50 | +26.00 | 270 | left MG310 (PH 6-pin), entry from the left edge, just above the strip |
| J602 | +35.50 | +15.50 | 90 | right MG310 (PH 6-pin), entry from the right edge, just above the strip |
| U601 | -30.00 | +21.00 | 90 | left encoder ESD at the connector |
| U602 | -25.50 | +21.00 | 90 | left encoder Schmitt buffer |
| U603 | +30.00 | +21.00 | 90 | right encoder ESD at the connector |
| U604 | +25.50 | +21.00 | 90 | right encoder Schmitt buffer |
| U501 | +0.00 | +20.00 | 90 | DRV8711: gate-drive pins up, bridge A on the left, bridge B on the right |
| R509 | -10.00 | +18.00 | 0 | Rsense A |
| R512 | +10.00 | +18.00 | 0 | Rsense B |
| Q501 | -17.00 | +28.00 | 90 | bridge A1 (MOT_L_P) |
| Q502 | -10.50 | +28.00 | 90 | bridge A2 (MOT_L_N) |
| Q503 | +10.50 | +28.00 | 90 | bridge B1 (MOT_R_P) |
| Q504 | +17.00 | +28.00 | 90 | bridge B2 (MOT_R_N) |
| C507 | +0.00 | +30.50 | 0 | 220 uF VM bulk between the bridges |
| D501 | -21.00 | +37.50 | 0 | SS34 clamp MOT_L_P |
| D502 | -13.50 | +37.50 | 0 | SS34 clamp MOT_L_N |
| D503 | +13.50 | +37.50 | 0 | SS34 clamp MOT_R_P |
| D504 | +21.00 | +37.50 | 0 | SS34 clamp MOT_R_N |
| MB1 | -32.00 | +8.50 | 0 | bracket M3 (MountingHole_M3_NPTH_KeepOut7mm) |
| MB2 | +32.00 | +8.50 | 0 | bracket M3 (MountingHole_M3_NPTH_KeepOut7mm) |
| MB3 | -32.00 | -8.50 | 0 | bracket M3 (MountingHole_M3_NPTH_KeepOut7mm) |
| MB4 | +32.00 | -8.50 | 0 | bracket M3 (MountingHole_M3_NPTH_KeepOut7mm) |
| MB5 | -38.50 | +7.00 | 0 | bracket M2 (MountingHole_M2_NPTH_KeepOut5.5mm) |
| MB6 | +38.50 | +7.00 | 0 | bracket M2 (MountingHole_M2_NPTH_KeepOut5.5mm) |
| MB7 | -38.50 | -7.00 | 0 | bracket M2 (MountingHole_M2_NPTH_KeepOut5.5mm) |
| MB8 | +38.50 | -7.00 | 0 | bracket M2 (MountingHole_M2_NPTH_KeepOut5.5mm) |
| MC1 | -30.00 | +50.00 | 0 | battery cradle (MountingHole_M3_NPTH_KeepOut7mm) |
| MC2 | +30.00 | +50.00 | 0 | battery cradle (MountingHole_M3_NPTH_KeepOut7mm) |
| MC3 | -30.00 | +72.00 | 0 | battery cradle (MountingHole_M3_NPTH_KeepOut7mm) |
| MC4 | +30.00 | +72.00 | 0 | battery cradle (MountingHole_M3_NPTH_KeepOut7mm) |
| MH1 | -38.00 | +92.00 | 0 | bumper (MountingHole_M3_NPTH_KeepOut7mm) |
| MH2 | +39.50 | +80.50 | 0 | bumper (nylon) (MountingHole_M3_NPTH_KeepOut7mm) |

## Open items

1. STDC14 (J301) uses KiCad's generic `PinHeader_2x07_P1.27mm_Vertical_SMD`. The LCSC datasheet for C5307809 is Samtec's
   through-hole catalogue page, with no SMD land pattern. Check against Samtec's FTSH-1xx-01-xxx-DV-K footprint drawing.
2. MG310 cable: confirm that its pin 1 (M−) lands on the board socket's pin 1.
3. Bracket: which hole pattern carries the screws (both are drilled), and the 18 mm axis-to-base dimension.
4. NFC coil tuning and read-range check on the assembled robot (`docs/nfc.md`).
5. 3D models are not installed in this environment, so the 3D render shows pads only.
