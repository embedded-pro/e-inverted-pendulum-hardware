# PCB layout (Phase 3)

Status: **anchor draft v2 for owner gate A** (2026-11-13). It replaces v1, which the owner rejected. Nothing is locked yet.
When the owner approves or corrects the anchors, they are locked on the board (`fp.SetLocked(True)`) and never moved
again (power-pcb-layout §1).

**Sources:**
- `docs/mechanical.md`: coordinates, bracket, battery, mass;
- `docs/rf.md`: 2.4 GHz antenna and RF path;
- `docs/nfc.md`: NFC coil;
- `docs/power-map.md`: net classes;
- decisions D-025 to D-031;
- the `power-pcb-layout`, `pcb-design-rules`, `rf-layout` and `interface-layout` skills.

**Files:**
- board: `kicad/e-inverted-pendulum.kicad_pcb`;
- generator: `kicad/gen/board.py` + `kicad/gen/placement.py`;
- renders: `kicad/renders/` (`scripts/render_board.py`).

## Board

| Item | Value | Source |
|---|---|---|
| Outline | 85 × 130 mm, 1 mm corner radii | D-024 |
| Coordinates | x ±42.5; z = 0 on the wheel axle at the centre of the 25 mm bracket strip; bottom edge z −12.5, top edge z 117.5; front view | D-026 |
| Stack-up | JLC04161H-7628: L1 0.035 / 7628 0.2104 / L2 0.0152 / core 1.065 / L3 0.0152 / 7628 0.2104 / L4 0.035 mm | D-008 |
| Layers | L1 parts, RF, short power pours · L2 solid GND, never cut · L3 VBAT/5V0/3V3 pours, slow signals · L4 signals + GND fill (none in the bracket strip) | `docs/plan.md`, D-026 |
| Rules | JLC 4-layer profile (`pcb_rules.py apply --fab jlcpcb --netclasses`), 45° corners only, net classes from the power map | pcb-design-rules |
| Project rules | RF1 clearance 0.10 mm (DS12804 copy); AE401 shorting-leg ring 0.10 mm (it is a via); NPTH to copper 0.5 mm; **no THT pin under the back-mounted battery**; **no part in the bracket strip** except the bracket holes | `kicad/e-inverted-pendulum.kicad_dru` |
| Grid origin | the wheel axle on the centreline (x = 0, z = 0) | `docs/mechanical.md` |
| Aux origin | bottom-left board corner (CPL files) | JLC |

## Zones (front view)

```
 x −42.5                                                        +42.5
   ┌───────────── 2.4 GHz keep-out band, full width, all layers ─────────────┐ z 117.5
   │                    AE401 IFA, feed above RF1 (x 0)                      │
   ├─────────────────────────────────────────────────────────────────────────┤ z 111.1
   │ SW101 (THT)  LEDs   J401  FL401→pi            U803 ┌── AE801 NFC coil ──┐│
   │ MH1          U701 IMU  [U301 MCU]   Y302      U802 │  25 × 21, all-layer ││
   │                         U702 flash                 └─── keep-out ───────┘│ z 84.5
   │             · · · · · battery on the BACK, z 40–75 · · · · ·    MH2       │
   │  MC3                     SW301 BOOT0         BZ801       MC4   J801 ◄────│ Qwiic
   │       U201/L201 buck                                     J301 STDC14 ◄───│ mid right edge
   │  MC1                      SW801 user                     MC2             │
   │ F101  Q101  D102                                                        │ z 40
   │ J101 XT30 (THT)    D501 D502      D503 D504                             │
   │                Q501 Q502 [C507] Q503 Q504                               │
   │──► J601 PH6  U601 U602   R509 [U501 DRV8711] R512   U604 U603  J602 ◄───│
   ├──────────────── bracket strip: no parts, no B.Cu copper ────────────────┤ z 12.5
   │ ∘MB5 ○MB1                     axle z 0                    ○MB2 ∘MB6     │
   │ ∘MB7 ○MB3        (motors + WHEELTEC bracket behind)       ○MB4 ∘MB8     │
   └─────────────────────────────────────────────────────────────────────────┘ z −12.5
```

## Anchor draft

Mechanical coordinates (mm, front view); rotation in degrees, KiCad convention. Generated from `placement.py`.

<!-- BEGIN anchors (kicad/gen/board.py) -->
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
<!-- END anchors -->

### Why these positions

The owner's floorplan (2026-11-13, D-029) fixes the MCU at the top centre, the antenna at the top, the battery on the
back, an empty bottom strip for the chassis, motor connectors on both side edges, the STDC14 mid-edge and the IMU near
the MCU. Within that:

- **RF.**
  - The STM32WB55 is rotated 180°, so RF1 (pin 31) is on its top edge.
  - FL401 IN is 1.5 mm from the RF1 pad edge (DS12804 Fig. 13). OUT, the pi network and the feed lie on x = 0.
  - The IFA keep-out is a full-width band, like SWRA117D's own board.
  - HSE at pins 34/35; U.FL test port beside the RF_50 line.
- **IMU (U701)** sits left of the MCU, next to its SPI2 pins (PB12–PB15, PC6 face left after the rotation). It is about
  94 mm above the axle, so the firmware compensates for the tangential acceleration (`docs/firmware-interface.md`).
- **NFC.** The coil is in the top-right corner, 5 mm below the 2.4 GHz band and 10 mm above the battery outline on the
  back. The ST25DV is at the coil's terminals, rotated so AC0/AC1 face the coil and SDA/SCL/GPO face the MCU (I2C3 and
  PA2 are on the MCU's right and top edges). The EEPROM shares I2C3 below it.
- **Flash** below the MCU: SPI1 (PB3–PB5, PA15) is on the MCU's bottom edge after rotation.
- **Over the battery (front, SMD only):** buck, buttons, buzzer, Qwiic, STDC14 at the middle of the right edge, and the
  battery-cradle holes MC1–MC4 (inside the battery outline, so the cradle is a tray under the battery).
- **Lower band (THT allowed):**
  - XT30 on the left edge;
  - MG310 sockets on both edges, entry from the side, just above the strip;
  - encoder ESD and buffers inboard of each socket;
  - DRV8711 at the centre (rotated 90°, gate-drive pins up), with the four FETs above it, the bulk cap between the
    bridges and the SS34 clamps above the FETs;
  - power path XT30 → F101 → Q101 → D102 into the bridge.
- **Bracket strip (z −12.5…12.5):**
  - only the bracket holes: 4 × M3 (64 × 17) and 4 × Ø2.4 (77 × 14), from the drawing;
  - no parts on either face, and no copper on B.Cu, where the steel base sits;
  - L2 GND runs through it (inner layers keep 0.5 mm from the holes).

## Gate A v2: what the owner decides

1. **Anchors:** approve, or move any of them. Approved anchors get locked.
2. **Bracket screws:** which hole pattern carries the screws: M3 on 64 × 17, Ø2.4 on 77 × 14, or both (both are drilled
   now). Confirm the 18 mm axis-to-base dimension (sets the axle and the S0 lean).
3. **Battery cradle:** 4 × M3 at x ±30, z 50/72, inside the battery outline. Confirm, or give the cradle's hole pattern.
4. **Bumpers:** MH1 top-left and MH2 on the right edge below the NFC coil (nylon, near the coil). Confirm the positions,
   or say if bumpers should be a printed top cap instead (the top edge is the antenna).
5. **STDC14** at the middle of the right edge (the left edge has the XT30 and the power path). Confirm the side.

## Open items

1. STDC14 (J301) uses KiCad's generic `PinHeader_2x07_P1.27mm_Vertical_SMD`. The LCSC datasheet for C5307809 is Samtec's
   through-hole catalogue page, with no SMD land pattern. Check against Samtec's FTSH-1xx-01-xxx-DV-K footprint drawing.
2. MG310 cable: confirm that its pin 1 (M−) lands on the board socket's pin 1 (PH cables are straight-through).
3. NFC coil tuning and read-range check on the assembled robot (`docs/nfc.md`).
4. 3D models are not installed in this environment, so the 3D render shows pads only.
5. Phase 3 steps 4–8 (support placement, power copper, critical routes, routing, finish) start after gate A.
