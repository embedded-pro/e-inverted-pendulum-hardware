# PCB layout (Phase 3)

Status: **anchor draft for owner gate A.** Nothing is locked yet. When the owner approves or corrects the anchors, they are
locked on the board (`fp.SetLocked(True)`) and never moved again (power-pcb-layout §1).

**Sources:**
- `docs/mechanical.md`: outline, coordinates, mounts, battery;
- `docs/rf.md`: antenna and RF path;
- `docs/power-map.md`: net classes;
- the `power-pcb-layout`, `pcb-design-rules`, `rf-layout` and `interface-layout` skills.

**Files:**
- board: `kicad/e-inverted-pendulum.kicad_pcb`;
- generator: `kicad/gen/board.py` + `kicad/gen/placement.py`;
- renders: `kicad/renders/` (`scripts/render_board.py`).

## Board

| Item | Value | Source |
|---|---|---|
| Outline | 85 × 130 mm, 1 mm corner radii; wheel axle 15 mm above the bottom edge | D-024 |
| Stack-up | JLC04161H-7628: L1 0.035 / 7628 0.2104 / L2 0.0152 / core 1.065 / L3 0.0152 / 7628 0.2104 / L4 0.035 mm | D-008 |
| Layers | L1 parts, RF, short power pours · L2 solid GND, never cut · L3 VBAT/5V0/3V3 pours, slow signals · L4 signals + GND fill | `docs/plan.md` |
| Rules | JLC 4-layer profile (`pcb_rules.py apply --fab jlcpcb --netclasses`), 45° corners only, net classes from the power map | pcb-design-rules |
| Project rules | RF1 clearance 0.10 mm (DS12804 copy); AE401 shorting-leg ring 0.10 mm (it is a via); NPTH to copper 0.5 mm | `kicad/e-inverted-pendulum.kicad_dru` |
| Grid origin | the wheel axle on the centreline (x = 0, z = 0) | `docs/mechanical.md` |
| Aux origin | bottom-left board corner (CPL files) | JLC |

## Zones (top-side view)

```
 x −42.5                                                   +42.5
   ┌─────────────┬─────────────────────────────────────────────┐ z 115
   │ AE401 IFA   │ SW301   D801 D802   MH1     J301     MH2     │
   │ keep-out    │  BOOT0  LEDs        bumper  STDC14   bumper  │
   │ (all layers)│                                     J801 ◄──│ Qwiic
   │ J401 U.FL   │                              SW801           │
   │ Y301 U301 (MCU, RF1 up)                           BZ801    │
   │ FL401 → pi → feed       U702 flash                         │
   │                 ▭▭▭▭ strap slot ▭▭▭▭                        │ z 81
   │ ┌─────────────────────────────────────────────────────────┐│
   │ │ BATTERY ZONE: no footprints on the top side (rule area)  ││
   │ └─────────────────────────────────────────────────────────┘│ z 41.5
   │                 ▭▭▭▭ strap slot ▭▭▭▭                        │ z 39
   │ MS2 slot              U701 IMU                 MS4 slot    │
   │ MS1 slot                         U201 L201     MS3 slot    │
   │          D501 Q501 Q502  C507  Q503 Q504 D503              │
   │ U602 D502   R509      U501 DRV8711   R512   D504   U604    │
   │ U601 (ESD)     F101  Q101  D102                    U603    │
   │ J602 ENC_L  J601 MOT_L  J101 XT30  SW101  J603 MOT_R J604  │
   └─────────────────────────────────────────────────────────────┘ z −15
                      wheel axle at z = 0
```

## Anchor draft

Mechanical coordinates (x across, z up from the axle, mm, top-side view); rotation in degrees, KiCad convention.

<!-- BEGIN anchors (kicad/gen/board.py) -->
| Ref | x | z | Rot | Why |
|---|---|---|---|---|
| AE401 | -29.00 | +108.85 | 0 | SWRA117D IFA, top-left corner, 1.65 mm from the side edge (docs/rf.md) |
| U301 | -27.00 | +95.00 | 180 | STM32WB55: rotated so RF1 (pin 31) faces the antenna; HSE at the top-left corner |
| FL401 | -28.75 | +101.44 | 0 | MLPF IN 1.5 mm from the RF1 pad, OUT toward the feed (DS12804 Fig. 13) |
| Y301 | -34.30 | +98.30 | 0 | HSE 32 MHz at OSC_IN/OSC_OUT (pins 35/34, top-left corner after rotation) |
| J401 | -23.00 | +104.50 | 0 | U.FL conducted test port (DNP), beside the RF_50 line |
| U702 | -10.00 | +87.00 | 0 | W25Q16 flash on SPI1, next to the MCU's SPI1 pins |
| J301 | +22.00 | +104.00 | 0 | STDC14 debug header, away from the antenna |
| SW301 | -14.00 | +110.00 | 0 | BOOT0 button at the top edge |
| D801 | -3.00 | +111.50 | 0 | green LED at the top edge |
| D802 | +2.00 | +111.50 | 0 | red LED at the top edge |
| SW801 | +22.00 | +90.00 | 0 | user button |
| BZ801 | +34.00 | +88.00 | 0 | buzzer, right edge of the upper band |
| J801 | +39.00 | +98.50 | 90 | Qwiic (I2C3), entry from the right edge |
| U701 | +0.00 | +31.00 | 0 | MPU-6500 on the centreline, 31 mm above the axle, >= 15 mm from switch nodes |
| U501 | +0.00 | +6.00 | 90 | DRV8711: gate-drive side (pins 20-38) up, bridge A pins on the left, bridge B on the right |
| Q501 | -15.50 | +14.00 | 90 | bridge A1 (MOT_L_P) |
| Q502 | -9.00 | +14.00 | 90 | bridge A2 (MOT_L_N) |
| Q503 | +9.00 | +14.00 | 90 | bridge B1 (MOT_R_P) |
| Q504 | +15.50 | +14.00 | 90 | bridge B2 (MOT_R_N) |
| R509 | -12.00 | +7.00 | 0 | Rsense A between its two LS sources |
| R512 | +12.00 | +7.00 | 0 | Rsense B between its two LS sources |
| C507 | +0.00 | +16.00 | 0 | 220 uF VM bulk, centred between the bridges |
| D501 | -21.50 | +13.00 | 90 | SS34 clamp MOT_L_P |
| D502 | -25.50 | +6.00 | 90 | SS34 clamp MOT_L_N |
| D503 | +21.50 | +13.00 | 90 | SS34 clamp MOT_R_P |
| D504 | +25.50 | +6.00 | 90 | SS34 clamp MOT_R_N |
| J101 | -8.00 | -11.00 | 0 | XT30 battery socket at the bottom edge |
| SW101 | +3.00 | -11.00 | 0 | power switch at the bottom edge |
| F101 | -12.50 | -4.00 | 0 | battery fuse right after the XT30 |
| Q101 | -3.00 | -3.50 | 0 | AO4805 back-to-back power switch |
| D102 | +6.50 | -4.00 | 0 | SMBJ15A TVS after the power switch |
| J601 | -24.00 | -5.30 | 0 | left motor (XH), cable from below |
| J603 | +21.50 | -5.30 | 0 | right motor (XH), cable from below |
| J602 | -39.50 | -8.15 | 0 | left encoder (PH 5-pin), cable from below |
| J604 | +31.50 | -8.15 | 0 | right encoder (PH 5-pin), cable from below |
| U601 | -35.50 | -3.50 | 90 | left encoder ESD at the connector (pass-through) |
| U603 | +35.50 | -3.50 | 90 | right encoder ESD at the connector (pass-through) |
| U602 | -35.50 | +5.00 | 0 | left encoder Schmitt buffer after the RC filters |
| U604 | +35.50 | +5.00 | 0 | right encoder Schmitt buffer after the RC filters |
| U201 | +14.00 | +26.00 | 0 | TPS62933F buck, right of the IMU, >= 15 mm from it |
| L201 | +18.50 | +26.00 | 0 | buck inductor at SW |
| MS1 | -32.00 | +20.00 | 0 | motor mount L (MountingSlot_M3_10mm_NPTH_KeepOut7mm) |
| MS2 | -32.00 | +30.00 | 0 | motor mount L (MountingSlot_M3_10mm_NPTH_KeepOut7mm) |
| MS3 | +32.00 | +20.00 | 0 | motor mount R (MountingSlot_M3_10mm_NPTH_KeepOut7mm) |
| MS4 | +32.00 | +30.00 | 0 | motor mount R (MountingSlot_M3_10mm_NPTH_KeepOut7mm) |
| MH1 | +10.00 | +109.50 | 0 | bumper (MountingHole_M3_NPTH_KeepOut7mm) |
| MH2 | +37.00 | +109.50 | 0 | bumper (MountingHole_M3_NPTH_KeepOut7mm) |
<!-- END anchors -->

### Why these positions

- **RF corner (top-left).**
  - The STM32WB55 is rotated 180°, so RF1 (pin 31) is on its top edge.
  - FL401 IN is 1.5 mm from the RF1 pad edge (DS12804 Fig. 13).
  - FL401 OUT, the pi network and the antenna feed all lie on one vertical line (x = −29.0), with 6.6 mm from OUT to the feed.
  - The HSE crystal sits at pins 34/35, the package corner next to RF1, as on ST's boards. The SMPS pins (41–44) face the
    left edge, away from the RF line.
- **Antenna:** 1.65 mm from the side edge and 1.0 mm from the top edge. Nothing metallic within 5 mm of the keep-out:
  the bumper screws are at the top-right, and the STDC14 is 40 mm from the antenna.
- **Power stage (bottom centre).**
  - The DRV8711 is rotated 90° with its gate-drive side (pins 20–38) facing up. Bridge A's pins (30–37) are on the left,
    toward Q501/Q502 (left motor). Bridge B's pins (21–28) are on the right, toward Q503/Q504.
  - Each bridge's Rsense sits between its two FETs' low-side sources.
  - The 220 µF bulk is centred between the bridges.
  - The SS34 clamps sit beside the FET outputs, on the way to the XH connectors.
- **Battery entry.** XT30 → F101 → Q101 (AO4805) → D102 runs along the bottom edge into the bridge from below. The power
  switch is at the bottom edge, where it can be reached.
- **Encoder chains (bottom corners).** Each runs PH connector → TPD4E05U06 ESD at the connector (pass-through) → RC
  filters → SN74LVC3G17 buffer, in signal order, away from the bridge.
- **IMU.** On the centreline, 31 mm above the axle:
  - 19 mm from the buck inductor and ≥ 15 mm from the bridge switch nodes;
  - below the strap slot.
- **Buck:** right of the IMU, between it and the right motor mount; ≥ 40 mm from the antenna.

## Gate A: what the owner decides

1. **Anchors:** approve, or move any of them. Approved anchors get locked.
2. **Battery face:**
   - top side (D-015, as drawn): static lean ≈ 21°, and the top-side battery zone stays free of parts;
   - bottom side, over the motors: lean ≈ 9.8°, and the 37 × 77 mm zone on the top side is freed except for a strap channel.
   - See `docs/mechanical.md` open item 4.
3. **Motor mount:** the M3 slots at x ±32, z 20/30 are a default. A standard 25 mm L-bracket doesn't reach the
   gearbox face (`docs/mechanical.md`). Choose a long bracket, a printed cradle or a can clamp, or give the hole pattern.
4. **Connectors:**
   - XH (motor) and PH (encoder), horizontal, cable entry from the bottom edge;
   - XT30 vertical at the bottom edge;
   - slide switch at the bottom edge.
   - Confirm, or say where the cables should leave.

## Open items

1. STDC14 (J301) uses KiCad's generic `PinHeader_2x07_P1.27mm_Vertical_SMD`. The LCSC datasheet for C5307809 is Samtec's
   through-hole catalogue page and has no SMD land pattern. Compare the footprint with Samtec's FTSH-1xx-01-xxx-DV-K footprint
   drawing before ordering.
2. 3D models are not installed in this environment, so the 3D render shows pads only.
3. Phase 3 steps 4–8 (support placement, power copper, critical routes, Freerouting, finish) start after gate A.
