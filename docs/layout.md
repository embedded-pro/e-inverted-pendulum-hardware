# PCB layout (Phase 3): placement brief for the owner

Status: **hand-off (2026-11-13, D-032).** The owner places the components in KiCad. The board starts as a clean
slate:
- **on the board:** the outline, the keep-out rule areas, the reference drawings and the WHEELTEC bracket holes;
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
| Outline | 85 × 130 mm, 1 mm corner radii | D-024 |
| Coordinates | Grid origin on the wheel axle at the centre line (x = 0, z = 0); the bottom edge is z −12.5, the top edge z 117.5 (KiCad Y = 150 − z) | D-026 |
| Stack-up | JLC04161H-7628: L1 0.035 / 7628 0.2104 / L2 0.0152 / core 1.065 / L3 0.0152 / 7628 0.2104 / L4 0.035 mm | D-008 |
| Layers | L1 parts, RF, short power pours · L2 solid GND, never cut · L3 VBAT/5V0/3V3 pours, slow signals · L4 signals + GND fill | `docs/plan.md` |
| Net classes | PWR_BUS 2.2 mm, MOTOR 0.8, SWITCH 0.5, SUPPLY 0.5, GATE 0.3, RF 0.27 / 0.15 gap, NFC 0.25, SENSE and CRYSTAL 0.2, Default 0.2 / 0.15 | `docs/power-map.md` |
| Fab rules | JLCPCB: track / space 0.09, via 0.15 / 0.25, via ring 0.05, PTH ring 0.15, hole-to-hole 0.20 (PTH 0.45), hole-to-copper 0.20 (PTH 0.28), edge 0.20, NPTH ≥ 0.50, silk text ≥ 1.0 / 0.15 mm | D-036, `pcb-design-rules` profiles |
| Silkscreen | References only; test pads show their net name; net ties unlabelled | D-035, `scripts/pcb/board.py` |
| Page | A3, so the staging area fits on the sheet | — |

## What DRC enforces (rule areas and project rules)

These are on the board as rule areas (they can be moved or edited in KiCad) and in `hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_dru`:

| Name | Where | Rule | Why |
|---|---|---|---|
| `ANTENNA_KEEPOUT` / `ANTENNA_BASE` | full-width band, z 111.1 → top edge, all layers | no tracks, vias or pour (base strip: no vias or pour) | 2.4 GHz IFA keep-out (D-029, `docs/rf.md`) |
| `NFC_COIL_KEEPOUT` | top-right, x 16 → edge, z 84.5–106.5, all layers | no tracks, vias or pour | NFC coil area; move it with the coil (`docs/nfc.md`) |
| `BRACKET_STRIP` | bottom 25 mm, front and back | **no footprints** except the bracket holes MB1–MB8 (project rule) | Chassis attachment (D-026) |
| `BRACKET_BASE_CONTACT` | bottom 25 mm, B.Cu | no tracks, vias or pour | The steel bracket base sits on the back |
| `BATTERY_BACK` | x ±38.5, z 39–76, B.Cu | **no through-hole pins** (project rule; NPTH holes allowed) | The battery lies on the back (D-025) |
| project rule | RF1 net | 0.104 mm clearance | DS12804 Fig. 13 matching trace |
| project rule | NPTH holes | 0.5 mm hole-to-copper | Screw threads touch the hole wall |

## Placement guidance (from the design docs)

- **RF (`docs/rf.md`):**
  - MLPF FL401 IN must sit 1.5 mm from the MCU's RF1 pad (pin 31), on a 200 µm trace with 104 µm gaps.
  - RF1 is on the package's bottom edge at rot 0, so rotate the MCU so it faces the antenna.
  - MLPF OUT → pi (C401, R401, C402) → AE401 feed: one short 50 Ω GCPW (0.27 / 0.15 mm), L1 only, no vias.
  - U.FL J401 hangs off RF_50 through R402.
  - HSE Y301 goes at pins 34/35; SMPS L301/L302 at pins 41–44; LSE Y302 at pins 3/4.
- **IMU (U701):** next to the MCU's SPI2 pins (PB12–PB15, PC6). If it sits far from the axle, report its position for the
  firmware (`docs/firmware-interface.md`, tangential acceleration).
- **NFC:** the ST25DV (U803) right at the coil's terminals (AE801 pads 1/2 on its left side); AC0/AC1 short and paired.
  Keep the coil ≥ 5 mm from the 2.4 GHz band and from metal (battery, screws).
- **Power (`docs/power-map.md`, power-pcb-layout §3):**
  - **Hot loop:** each bridge's 100 nF HF cap closest to its FET pair's drain and LS source, with L2 GND directly under the loop
    (≤ 5 nH, S2).
  - **Gate resistors:** at the FETs.
  - **Rsense:** R509/R512 between their pair's LS sources, with Kelvin taps from the inner pad edges.
  - **SS34 clamps:** D501–D504 at the phase nodes.
  - **Bulk:** C507 between the bridges.
  - **Buck:** TPS62933F per SLUSEA4 §12, its switch node kept small and away from the IMU and the antenna.
- **Encoders:** ESD (U601/U603) at each PH 6-pin connector, then the RC, then the buffer (U602/U604).
  Motor pins 1 and 6 bracket the encoder pins, so keep the motor traces away from the encoder lines.
- **Through-hole parts:** J101 XT30, SW101 switch, J601/J602 PH 6-pin. They must stay outside `BATTERY_BACK`.
- **Holes for you to place (staged under "Mechanical"):** battery cradle MC1–MC4 and bumpers MH1/MH2. Footprints
  `MountingHole_M3_NPTH_KeepOut7mm` and `..._M2_..._KeepOut5.5mm` are in the project library for more.

## After placing

1. Save in KiCad, then lock the parts you consider fixed (they become the anchors for routing; power-pcb-layout §1).
2. Re-sync and check. This keeps every position:

   ```bash
   python3 scripts/pcb/board.py --rules <path to pcb_rules.py>
   ```

   ```bash
   kicad-cli pcb drc --schematic-parity --severity-all hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pcb
   ```

   ```bash
   python3 scripts/pcb/render.py
   ```

3. Phase 3 steps 4–8 follow: support placement around your anchors, power copper, critical routes, the rest of the
   routing, fills, DRC and fab outputs.

## Previous generated draft (gate A v2, not applied)

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
