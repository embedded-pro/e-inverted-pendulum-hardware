# Motor driver: a copy of TI's BOOST-DRV8711

Since D-040 the **motor-driver power stage is a copy of TI's BOOST-DRV8711 BoosterPack**. The copy covers:
- the DRV8711;
- the four CSD88537ND half-bridges;
- the two 50 mΩ shunts and their Kelvin net ties;
- the DRV8711's support capacitors;
- TI's copper.

The owner's reason, as for the RF (D-037) and NFC (D-039) corners: follow the manufacturer's proven board. TI's board
is a stepper driver, but its hardware is two full H-bridges; we drive them in PWM mode (PWMMODE 1, D-002), bridge B
for the left motor and A for the right (D-042: each bridge feeds the connector on its own side).

## Provenance and licence

- **TI files**, uploaded by the owner and kept in the gitignored `reference/boost-drv8711/`, never committed:

  | File | SHA-256 |
  |---|---|
  | `slvc575b.zip`: BOOST-DRV8711 hardware and software files (Altium project, Gerbers, ODB++, BOM, PDFs) | `c2080fc05c273ee07dc64f03d715ba4cacdde6aab6a1f4a9d0eadcbc6b9526b2` |
  | `drv8711_slvsc40h.pdf`: DRV8711 datasheet SLVSC40H (May 2020) | `d04e2538bc6e1bea359037ce1e8ab39a36e8100197319951d4f3d19884a60843` |

- **Licence:** TI's design-file terms (the owner confirms publishing is allowed). Everything derived carries "Derived
  from Texas Instruments BOOST-DRV8711 design files (SLVC575B)":
  - the `BOOST_*` footprints;
  - `scripts/pcb/boost_drv8711.json`.
- **Tools:**
  - `scripts/drv_reference.py` reads `BOARD/BOOST-DRV8711.PcbDoc` through KiCad 10's Altium importer, as
    `rf_reference.py` does for ST's board.
    - It selects the power stage.
    - It copies the stage's tracks, vias and pours inside its box, pruning the legs to TI's headers.
    - It checks every pad's net, and TI's mirrored Q2 / Q4 wiring.
  - `scripts/pcb/drv_block.py --apply` pastes it once, as the locked group "BOOST-DRV8711 drive".

## The circuit (BOOST-DRV8711 schematic and BOM, SLVSC40H)

| Ours | TI | Part | Role |
|---|---|---|---|
| U501 | U1 | DRV8711DCPR (C60013), TI's PowerPAD land with 12 thermal vias | gate driver, PWMMODE 1 |
| Q501 / Q503 | Q1 / Q3 | CSD88537ND (C117439) | xOUT1 half-bridges: FET1 high side, FET2 low side |
| Q502 / Q504 | Q2 / Q4 | CSD88537ND | xOUT2 half-bridges, **mirrored as TI wires them**: FET1 low side, FET2 high side |
| R509 / R512 | R1 / R2 | CRA2512-FZ-R050ELF, 50 mΩ 2512 3 W (C840617) | Rsense, bridge A / B |
| NT501 / NT502 | NT1 / NT2 | TI's 10 mil net tie, **on B.Cu** | xISENP Kelvin tap at the shunt's SENSE pad |
| NT503 / NT504 | NT3 / NT4 | TI's 10 mil net tie, **on B.Cu** | xISENN Kelvin tap at the shunt's GND pad |
| C508 | C2 | 10 nF 100 V 0603 (C342523) | VM at the pin |
| C514 | C8 | 1 µF 100 V 1206: CL31B105KCHNNNE (C13832), for TI's HMK316B7105KL-T (not stocked) | VM |
| C510 | C3 | 100 nF 100 V 0603 (C77058) | CP1–CP2 flying cap |
| C509 | C4 | 1 µF 50 V 0805 (C28323) | VCP to VM |
| C511 | C5 | 100 nF 25 V 0603 (C338036) | V5 |
| C512 | C6 | 1 µF 16 V 0603 (C76617) | VINT |
| C513 | C7 | 1 nF 0603 (C22402015) | BEMF |
| C507 | C1 | **220 µF 35 V SMD EEEFK1V221P** at the centre of TI's through-hole 100 µF 100 V | VM bulk (owner: SMT only) |

The values follow TI's board, which matches the SLVSC40H pin table. The datasheet's layout section asks for 1 µF on V5;
the pin table and TI's board use 100 nF, and so do we.

**Kept on top of TI's circuit** (owner, D-040), each at the nearest free top-side spot (`drv_block.py` reports the
distances):

| Part | Where | Distance from its target |
|---|---|---|
| D501–D504 SS34 | phase-node clamps, anode GND (S2: the dead-time body-diode swing passes the −0.6 V phase-pin absolute maximum, SLVSC40H §6.1) | 5.4–7.0 mm from the FET's phase pads |
| C502 / C503, C505 / C506 | 10 µF + 100 nF per bridge at the high-side drains | 2.0–6.4 mm |
| C501 / C504 | 1 nF across xISENP / xISENN, not fitted | 2.8–2.9 mm from the ISEN pins |
| R515–R518 | nFAULT / nSTALL / SDATO pull-ups, nSLEEP pull-down | 1.5–4.8 mm from their pins |

**Dropped** (owner, D-040): the 8 gate and 4 sense series 0 Ω resistors. They would have cut TI's traces; the
DRV8711's IDRIVE sets the gate slew instead.

**Not copied:** TI's LaunchPad headers, terminal blocks, LEDs, R3–R6 and the routing to them. TI's R3 3.3 kΩ SDATO
pull-up is our R517 2.2 kΩ, sized for our shared SPI bus.

## Layout

- **Position:** TI's stage is turned 180° about its centre (owner, 2026-11-15; `placement.DRIVE_TURN`).
  - Its box (TI's parts and pours) is centred on x 0, from z 13.5 (1 mm above the bracket strip) to z 50.5.
  - The FETs are nearest the strip, in a row at z 25.0; the DRV8711 is above them, at (−4.0, 40.0).
  - Bridge A is on the right and drives the right motor (J602); bridge B is on the left and drives the left motor
    (J601). The phase pours end at z 13.5 on their own side, so the outputs don't cross (D-042). The bulk C507 is
    bottom-right, at (13.8, 18.9).
  - The DRV8711's 12 PowerPAD thermal vias (0.33 mm, plated, no lead) now sit inside `BATTERY_BACK`. The battery rule
    was scoped to plated holes over 0.4 mm, so they count as vias (already allowed there); real leads are still caught.
- **Copper:** TI's 2-layer copper goes on our F.Cu and B.Cu: 173 tracks, 144 vias and 12 pours (VM, phase, GND_A / B,
  GND).
  - L2 stays solid GND under it, never cut: closer to the hot loops than TI's bottom layer.
  - Two of TI's vias moved 0.01 mm, to reach JLCPCB's 0.20 mm hole-to-copper from the net ties' bridges.
- **Project DRC rules**, inside the group only:
  - TI's 0.178 mm clearance (under our 0.2 mm MOTOR / PWR_BUS class value, above JLCPCB's 0.09);
  - TI's 90° corners exempt from the 45° rule.
- **Routing gate:** `--gate jogs=5 --gate track_junctions=1`.
  - One of the jogs is TI's: 0.19 mm on A2HS.
  - The other four jogs and the T-junction are ST's copies.
  - Shorts, clearance and the fab floor are not relaxed.
- **Phase outputs:** TI's phase pours end at the top of the box, where TI's terminal block sat. From there to J601 /
  J602 (PH 6-pin at the board edges) the routing is the owner's.
- **Net ties on the bottom:** copper only, nothing to assemble, no label.
- **Silkscreen (D-041):** every reference on the silk except C503 / C506, whose only spots beside the FETs Q501 / Q503
  take (their references are on F.Fab). The extras are placed so that no two outlines overlap.

## Open items

1. Owner: route the four phase outputs to J601 / J602, the logic pins (SPI, AIN / BIN, nFAULT, nSTALL, nSLEEP, RESET)
   to the MCU, and the board-wide ground.
2. The SS34 clamps sit 5.4–7.0 mm from the phase pads (the nearest free spots around TI's dense FET row). Check the
   phase-node swing on the bench with the clamps fitted and not fitted.
3. Shunt temperature at the 2.0 A trip (0.2 W in a 3 W 2512, TI's part).
4. Confirm TI's design-file licence for publishing the derived footprints and geometry.
