# Mechanical concept: the PCB on a WHEELTEC U-bracket

Status: Phase 3, re-baselined 2026-11-13 for the owner's hardware (D-025 to D-029). Dimensions marked **ASSUMPTION**
become anchors once the parts are measured. `mechanical/mass_budget.csv` is the single source for
`simulation/sizing.py`.

## Coordinates

- **x:** across the plate, along the wheel axle; x = 0 on the vertical centreline. The plate spans x −42.5 … +42.5 mm.
- **z:** up the plate, with z = 0 on the wheel axle at the centre of the 25 mm bracket strip. The bottom edge is
  z −12.5. The top edge is z +117.5 at the antenna tab and right of x +6.1 (the NFC corner), and z +110.02 between
  them (D-024, D-037 and D-039 outline, D-026 axle).
- **y:** through the plate, from its mid-plane, positive toward the **back** (where the bracket, motors and battery
  are). The front is the component side.

The pivot is the wheel axle: y = +18.8 mm, i.e. the bracket leg's hole 18 mm from the base plus the 0.8 mm half plate.

## Arrangement

Side view (robot drives left/right on the page):

```
                 front │ │ back
                (parts)│ │
   z 117.5 ────────────┤ │  2.4 GHz antenna tab (top-left) and NFC coil (top-right); z 110 between them
                       │ │
   z 75    ────────────┤ ├────────┐
                       │ │BATTERY │ 22 mm thick, on a printed cradle (4 × M3)
   z 40    ────────────┤ ├────────┘
                       │ │
   z 12.5  ────────────┤ ├─┐  bracket base (2 mm steel) on the back of the strip
   z 0     ─ ─ ─ ─ ─ ─ ┤ ├─┼──────(●) motor axis = wheel axle, y = +18.8 mm
   z −12.5 ────────────┴─┴─┘
```

Front view (component side):

```
 x −42.5                                              +42.5
   ┌──────────────────────┐ z 117.5         ┌──────────────────┐ z 117.5
   │ ░ antenna tab ░░░░░░░ ╲               │  (no parts)      │
   │ ░ (MB1355) no ground ░ ╲______________│ ANT14 NFC coil   │ z 110.0 between, step at x +6.1
   │  MCU + RF corner   M24SR64-Y tag ◄──── │ (MB1163 copy)    │
   │  (MB1355 copy)     (left of the coil)  └──────────────────│ z 76.5 (coil bottom)
   │                                                    │ z ~76
   │       (battery behind this band: SMD parts only)   │
   │                                                    │ z ~40
   │◄J601 (L)   bridge B   DRV8711   bridge A   J602 (R)►│ PH6 plugs enter from the side edges (D-042)
   ├──────────────────────────────────────────────────┤ z 12.5
   │ ○M3  ∘M2     bracket strip: no parts        ∘M2  ○M3│ (axle z 0)
   └──────────────────────────────────────────────────┘ z −12.5
      bracket legs 8.5 mm outside each side edge (x ±51)
```

Left edge, top to bottom: J301 (STDC14, left of the MCU, D-047), SW101 (power switch, above the battery, D-051), J801
(Qwiic, D-051), J101 (XT30 battery input, D-047), J601 (left motor, D-042).

- **Front:** every SMD part (JLC single-side PCBA), with no parts in the bottom 25 mm strip.
- **Back:** the bracket in the strip, the motors behind it, and the battery above them. No parts.
- **Plate:** 85 mm wide × 1.6 mm; 130 mm tall at the top-left antenna tab (x −42.5 to −14.0) and right of x +6.1, where
  the MB1163 NFC corner sits (D-039); 122.5 mm between them, where the top edge steps down to z 110.02 (MB1355's
  outline, D-037).
- **Mechanical holes:** NPTH with an outer-layer copper keep-out (7 mm for M3, 5.5 mm for M2). The strip has no
  B.Cu copper at all, because the steel base presses on it.

## Chassis: WHEELTEC U-bracket (D-026)

From the owner's drawing (2026-11-13):

| Item | Value |
|---|---|
| Length over the legs | 102 mm |
| Base width | 25 mm |
| Sheet | 2 mm steel |
| Base holes | 4 × Ø3.3 on 64 × 17 mm; 4 × Ø2.4 on 77 × 14 mm |
| Leg | R12.5 end, Ø8 shaft hole, motor screws Ø3.2 on Ø17 PCD |
| Motor axis | 18 mm from the base |

**Fitting to the board:**
- The base lies flat on the back of the strip, centred on x = 0, and is bolted through 4 × M3 (64 × 17 mm). The
  4 × Ø2.4 holes (77 × 14 mm) are provided as well.
- The motors sit inside the U, gearbox faces against the legs, shafts out through them.
- **ASSUMPTION:** the 18 mm dimension is measured from the base's outer face. Check it on the part.

## Motors: MG310 1:20 (D-027)

- **Rating:** 7.4 V; 0.4 kgf·cm at 400 rpm; stall 1.5 kgf·cm.
- **Encoder:** Hall A/B, no index.
- **Cable:** 6 wires (1 M−, 2 encoder VCC, 3 A, 4 B, 5 GND, 6 M+), ending in a PH 2.0 6-pin plug.
- **Mass:** 65 g each, **ASSUMPTION** (60–70 g in listings).
- **Stall current:** 2.0 A at 7.4 V, **ASSUMPTION** (the listing says "≤ 2 mA").

## Mass budget (from `mechanical/mass_budget.csv`)

| Item | Mass | Position (z above the axle, y from the axle; + = back) | Source |
|---|---|---|---|
| PCB plate 85 × 130 × 1.6, minus the step between the tab and the NFC corner (10 899 mm²) | 32.3 g | z 51.7, y −18.8 mm | D-024, D-037, D-039, FR-4 1.85 g/cm³ |
| Components | 30 g | z 60, y −20.8 mm | ASSUMPTION |
| 3S 1000 mAh LiPo, 75 × 35 × 22 | 85 g | z 57.5, y −7.0 mm (on the back, z 40–75) | ASSUMPTION |
| Battery cradle | 10 g | z 57.5, y −12.8 mm | ASSUMPTION |
| 2 × MG310 + encoder | 2 × 65 g | on the axle | ASSUMPTION |
| WHEELTEC bracket | 64 g | z 0, y −11.7 mm | derived: 8.2 cm³ of steel |
| Screws, cables, XT30 lead, bumpers | 35 g | z 10–100 mm | ASSUMPTION |
| 2 × wheel, Ø65 mm | 2 × 30 g | wheel mass M | owner: 65 mm; mass ASSUMPTION |

Result (S0, `simulation/results/sizing_summary.json`):
- body m = 0.386 kg;
- ℓ = 28.5 mm;
- J about the CoM = 4.32e-04 kg·m²;
- **fall time constant τ = 83 ms**: about 41 updates per τ at 500 Hz.

## Consequences for the firmware

- **Static lean ≈ 18° toward the front.** The bracket puts the axle 18.8 mm behind the plate. The plate and parts
  are in front of it, and even the back-mounted battery is 7 mm in front (battery on the front: 27°).
  - Calibrate the pitch setpoint.
  - Measure the fall limit (REQ-SAFE-002) from that setpoint, not from vertical.
- **Wheel radius 0.0325 m** (65 mm wheels, owner). **Track width ≈ 0.15 m**: wheel centre planes about 24 mm outside
  the 102 mm bracket (shaft, hub and half the wheel width; measure once assembled). This replaces the 0.145 m
  placeholder (`WheelOdometryImpl.hpp:20`).
- **IMU position.** The IMU sits on the centre line, 78 mm above the axle (D-043); the axis map is in
  `docs/firmware-interface.md`. Its accelerometer
  reads the tangential acceleration r·θ̈ on top of gravity. The firmware must subtract it (r from the layout, θ̈ from the
  gyro) or keep the complementary-filter crossover low.
- **Body inertia:** J about the **centre of mass** (`pendulum-dynamics.md` labels it "about the axle"). The
  reflected rotor inertia, J_R = 2·J_rotor·G² ≈ 8e-4 kg·m² at 1:20, belongs in the plant model (S0).

## Open items

1. Weigh the motors, wheels, bracket and battery; update `mass_budget.csv`; rerun `sizing.py`.
2. Confirm the bracket's 18 mm axis-to-base dimension and which base holes carry the screws.
3. Design the battery cradle on the 4 × M3 holes (`docs/layout.md`). Falling backward lands on the battery,
   so the cradle should have a lip that takes the impact.
4. Bumpers (HW-MEC-004): MH1 top-left and MH2 on the right edge below the NFC coil (coil bottom z 76.5). Use nylon
   hardware, and keep metal at least ST's 4.4 mm pour gap from the coil (`docs/nfc.md`).
5. Motor plugs (D-042): J601 / J602 face sits 0.55 mm inside the side edge (**ASSUMPTION**: the footprint's silk keeps
   JLCPCB's clearance to the edge). Check the PH plug, its latch and the cable bend against the bracket legs (x ±51,
   behind the board) and the wheels on the assembled robot.
6. **Battery cradle relief (D-044, moved by D-052):** J601 / J602's upper four pins (x ±33.65, z 39.5–45.5) sit over
   the battery's side edges. Their through-hole tails stick out on the back (**ASSUMPTION**: about 1.5 mm; measure the
   S6B-PH-K), so the cradle needs a relief at x ±32.28…±35.03, z 38.4–46.6 (pads plus 0.5 mm).
   **J101 (D-047, moved by D-052):** the XT30 at the left edge with both pins (1.9 mm holes, 3.2 mm pads) at x −37.1,
   z 56.4 / 61.4, over the battery's left edge. Its tails stick out on the back (**ASSUMPTION**: about 1.5 mm; measure
   the XT30UPB-F), so the cradle needs a second relief at x −39.2…−35.0, z 54.3–63.5 (pads plus 0.5 mm).
   The connectors moved inward in D-052 so every part's body keeps JLCPCB's 2.5 mm from the board edge (assembly
   terms, DFM item 3): their plugs now start about 2.5 mm inside the edge, the cables entering over the board.
7. **Power switch (D-051, moved by D-052):** SW101 (SS-12D10L5) at the left edge, turned 90° so it slides along z, pins
   at x −36.5, z 79.0 / 83.7 / 88.4, its body 2.5 mm from the edge. Its lever stands out of the front (component side) and is
   worked from the front; its through-hole tails are above the battery (z ≥ 79 > 75), so the cradle needs no relief.
   **ASSUMPTION**: lever and body heights from the part family, not measured; check that the lever clears a front cover
   or bumper, and that a fall on the left side doesn't hit it (HW-MEC-004 bumpers).
