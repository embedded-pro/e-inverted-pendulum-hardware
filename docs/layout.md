# PCB layout (Phase 3): placement brief for the owner

Status: **hand-off (2026-11-13, D-032).** The owner places the components in KiCad. The board starts as a clean
slate:
- **on the board:** the outline, the keep-out rule areas, the reference drawings and the WHEELTEC bracket holes;
- **the MB1355 RF corner (2026-11-15, D-037):** the MCU, RF path, antenna, SMPS, crystals and their copper, pasted at the
  top-left corner as one group, "MB1355 RF corner" (`scripts/pcb/rf_block.py`, `docs/rf.md`);
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
| Silkscreen | One label per part: the reference; a test pad's net name; nothing on a net tie. 1.0 mm text, 0.15 mm line (JLCPCB's minimum), clear of every label, outline, pad, via, body and the edge, next to its own part; outlines at 0.15 mm. 19 references with no room in the MB1355 core and beside TI's FETs are on F.Fab, sized to fit inside their part | D-035, D-041, `scripts/pcb/silk.py` |
| Page | A3, so the staging area fits on the sheet | — |

## What DRC enforces (rule areas and project rules)

These are on the board as rule areas (they can be moved or edited in KiCad) and in `hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_dru`:

| Name | Where | Rule | Why |
|---|---|---|---|
| `ANTENNA_TAB` | MB1355's tab, x −42.5 to −14.0, z 109.98 → top edge, all layers | no vias or pour; only the antenna feed (RF_ANT) may cross it (project rule) | Ground-free antenna tab (D-037, `docs/rf.md`) |
| group "MB1355 RF corner" | top-left: MCU, RF, SMPS, crystals | ST's clearance (0.10 mm), arcs/angles and tight placement allowed inside the group (project rules); the L2 cut-out under the RF line | Literal copy of MB1355 (D-037) |
| `NFC_COIL` | ANT14 + 0.5 mm: x 10.0 → edge, z 76.0 → edge, all layers | no tracks, vias or pour (the coil footprint excepted) | MB1163 copy (D-039, `docs/nfc.md`) |
| `NFC_POUR_GAP` | ANT14 + ST's 4.4 mm coil-to-pour gap: x 6.1 → edge, z 72.1 → edge, all layers | no vias or pour | ST's pour edge on MB1163; ST's own cluster copper sits in it |
| `BRACKET_STRIP` | bottom 25 mm, front and back | **no footprints** except the bracket holes MB1–MB8 (project rule) | Chassis attachment (D-026) |
| `BRACKET_BASE_CONTACT` | bottom 25 mm, B.Cu | no tracks, vias or pour | The steel bracket base sits on the back |
| `BATTERY_BACK` | x ±38.5, z 39–76, B.Cu | **no through-hole pins** (project rule; NPTH holes allowed) | The battery lies on the back (D-025) |
| project rule | RF1 net | 0.104 mm clearance | MB1355's 0.265 mm fan-out from pin 31 between the 0.4 mm-pitch pins |
| project rule | NPTH holes | 0.5 mm hole-to-copper | Screw threads touch the hole wall |
| project rule | silkscreen outlines of two parts | may sit closer than 0.15 mm, never overlap; labels keep 0.15 mm to everything (silk checks are errors) | JLCPCB gives no silk-to-silk figure; KiCad applies its silk-to-pad 0.15 mm to both (D-041) |

## Placement guidance (from the design docs)

- **RF (`docs/rf.md`):** done by the copy. The group "MB1355 RF corner" holds:
  - U301, FL401, the match and AE401 (no SMA branch, D-038);
  - L301 / L302, Y301 / Y302 and their caps, the shield-clip pads;
  - the MCU decoupling on top, at the Nucleo's spots or the nearest free spot to each pin (D-038, `docs/rf.md`);
  - ST's copper, vias and ground.

  Move it only as a group; its position on the outline (the tab) is part of the copy. Still yours:
  - route the decoupling (C301–C313, C317, FB301) to its pins and +3V3;
  - route the MCU's other pins out of the corner;
  - pour the board-wide ground.
- **IMU, flash and EEPROM (D-043, `scripts/pcb/place_block.py imu_memory`): placed.**
  - U701 (MPU-6500) on the centre line at (0, 78), rotation 0: its position and axes are published
    (`docs/firmware-interface.md`). C701 / C702 / C703 at VDD / VDDIO / REGOUT, R701 (nCS pull-up) above it, the SPI2 /
    INT test pads in a column to its left.
  - U702 (W25Q16JV) below the MCU at (−20, 81.3), turned 180° so DI / CLK face R301 (SPI1 SCK 33 Ω, between the MCU and
    the flash); C704 at VCC, R702 / R703 / R704 at /CS, /WP, /HOLD; TP706 (FLASH_NCS) to the left.
  - U802 (M24C64) stacked under the flash in the same column (−20, 70.4; D-044), SDA / SCL on its right, C802 at VCC,
    the I2C3 pull-ups R808 / R809 below it.
  - Still yours, routing: SPI2 from the MCU's left pins (46–50) to the IMU, about 30 mm, under the NFC cluster; I2C3 from
    the MCU's top pins (28 / 29) around its left side and down to the EEPROM, about 50 mm (inside the bus
    budget's 15 cm, `docs/nfc.md`); SPI1 and FLASH_NCS from the bottom pins. Keep them off the RF
    strip and the L2 cut-out under the RF line.
- **NFC (`docs/nfc.md`):** done by the copy. The group "MB1163 NFC corner" holds AE801 (ANT14), U803 (M24SR64-Y) and
  ST's cluster (FB801, C803 / C804 / C818–C823, R804–R806, R810) with ST's tracks, vias and GND pour, turned 90° from ST's
  board and 8 mm below the corner: the coil at the right edge, the tag to its left, beside the MCU. Move it only as a group. Still yours: route NFC_GPO (PA2), NFC_RF_DIS (PA3),
  QWIIC_SDA / SCL and +3V3 into the cluster; keep metal (screws, battery cradle) out of `NFC_POUR_GAP`.
- **Motor drive (`docs/drive.md`):** done by the copy. The group "BOOST-DRV8711 drive" holds TI's power stage (U501,
  Q501–Q504, R509 / R512, the net ties NT501–NT504 on B.Cu, C507–C514) with TI's tracks, vias and pours, turned 180°
  (FETs nearest the strip; bridge A on the right drives the right motor, B the left, D-042), centred on x 0 from z 13.5 to 50.5, and our extras at the nearest free spots (SS34 D501–D504, C501–C506, R515–R518). Move it only as a
  group. Still yours: the phase outputs to J601 / J602, the logic pins to the MCU, the board-wide ground.
- **Power (`docs/power-map.md`, power-pcb-layout §3):**
  - **Buck:** TPS62933F per SLUSEA4 §12, its switch node kept small and away from the IMU and the antenna.
- **Motor connectors and encoder inputs (D-042, D-044, `scripts/pcb/place_block.py motor_io`): placed.**
  - J601 at the left edge and J602 at the right, plug entering from the side, pins at x ±35.7 from z 35.5 to 45.5
    (raised 20 mm, D-044). The upper four pins of each sit over the battery's edge: the cradle needs a
    relief there (`docs/mechanical.md`). J601's pin 1 (M−) is at the top, J602's at the bottom.
  - Inward from each connector, in signal order: the ESD (U601 / U603) beside pins 2–5, the four RC rows (pull-up DNP,
    100 Ω, 100 Ω, pull-up DNP) at x ±28.8, the 1 nF caps at x ±25.9, then the SN74LVC3G17 (U602 / U604) with its
    bypass and test pads above the rows at z 50.6. The right side mirrors the left.
  - The encoder supply (R601 / R602, F601, C601 / C602, TP605 / TP606) sits above the left chain, z 59–63.
  - Still yours, routing:
    - Both motor pins leave at the bottom of the connector and run about 22 mm down the side to the phase pours that end
      at z 13.5 on the same side.
      The top motor pin's trace runs down under the housing, outboard of the pads, so no motor copper passes the
      encoder rows.
    - Connector → ESD with no via and no stub, a GND via at the ESD's GND pins (interface-layout §2).
    - ENC_VCC across to J602; the buffered outputs to PC0 / PC2 (left) and PA0 / PA1 (right).
- **Through-hole parts:** J101 XT30, SW101 switch, J601/J602 PH 6-pin. They must stay outside `BATTERY_BACK`, except
  J601 / J602, whose pins sit over the cradle's relief (D-044, project rule).
- **Holes for you to place (staged under "Mechanical"):** battery cradle MC1–MC4 and bumpers MH1/MH2. Footprints
  `MountingHole_M3_NPTH_KeepOut7mm` and `..._M2_..._KeepOut5.5mm` are in the project library for more.

## After placing

1. Save in KiCad, then lock the parts you consider fixed (they become the anchors for routing; power-pcb-layout §1).
   The scripts lock nothing (D-045). The three copies are KiCad groups: a click selects the whole group; double-click it
   (or right-click → Enter Group) to select one part, track or via inside.
2. Re-sync and check. This keeps every position:

   ```bash
   python3 scripts/pcb/board.py --rules <path to pcb_rules.py>
   ```

   It ends by laying the silkscreen labels out (`scripts/pcb/silk.py`, D-041): labels that are clean stay put, the
   others move next to their part. `python3 scripts/pcb/silk.py --check` reports without changing anything.

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
