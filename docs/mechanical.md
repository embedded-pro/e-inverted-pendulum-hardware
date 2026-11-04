# Mechanical concept: the PCB is the chassis

Status: Phase 3 baseline for the **85 × 130 mm** plate (D-024). Dimensions marked **ASSUMPTION** become
anchors once the motors, brackets, wheels and battery are in hand and weighed.
`mechanical/mass_budget.csv` is the single source for `simulation/sizing.py`.

## Coordinates

- **x:** across the plate, along the wheel axle; x = 0 on the vertical centreline. The plate spans x −42.5 … +42.5 mm.
- **z:** up the plate, z = 0 on the wheel axle. The axle is 15 mm above the bottom edge, so the plate
  spans z −15 … +115 mm.
- **y:** through the plate, from its mid-plane, positive toward the **bottom side** (the motor side). The top side is
  the component side (D-015).

The pivot is the wheel axle, which is the motor axis: y = +14 mm (`axle` row in the mass budget). The CoM, ℓ and lean are
measured from there.

## Arrangement

Side view (robot drives left/right on the page):

```
                 top side │ │ bottom side
                (parts)   │ │  (motors)
   z 115 ─────────────────┤ ├
            antenna, bumpers
                          │ │
   z 77.5 ┌────────┐      │ │
          │BATTERY │◄─────┤ │   strap through two slots (z ≈ 39 and z ≈ 81)
   z 42.5 └────────┘      │ │
                          │ │
                          │ │  ┌─────┐
   z 0  ─ ─ ─ ─ ─ ─ ─ ─ ─ ┤ ├──┤  ●  │ motor axis = wheel axle, y = +14 mm
   z −15 ─────────────────┴─┘  └─────┘
```

Front view of the top side (the battery covers the middle band):

```
 x −42.5                                         +42.5
   ┌───────────────────────────────────────────────┐ z 115
   │ [ANTENNA keep-out, all layers]   bumper ○  ○  │
   │                                               │ z ≈ 99.5  (≥ 22 mm above the battery)
   │  MCU + RF + crystals, STDC14, LEDs, buttons   │
   │  ▭▭▭▭ strap slot ▭▭▭▭                         │ z ≈ 81
   │ ┌───────────────────────────────────────────┐ │ z 77.5
   │ │  BATTERY ZONE 75 × 35 (no parts)          │ │
   │ └───────────────────────────────────────────┘ │ z 42.5
   │  ▭▭▭▭ strap slot ▭▭▭▭                         │ z ≈ 39
   │  IMU, flash, encoder buffers, buck, LDO       │
   │ ○ ○  DRV8711, FETs, Rsense, bulk caps    ○ ○  │ ← motor-mount M3 slots
   │ ENC/MOT     XT30   switch          MOT/ENC    │
   └───────────────────────────────────────────────┘ z −15
```

- **Top side:** every SMD part (JLC single-side PCBA) and, by default, the battery. The battery sits flat in a
  component keep-out zone and is held by a strap through two milled slots.
- **Bottom side:** the two gearmotors, end to end on the axle line, output shafts facing out. There are no components on this face,
  so the motor mounts, nuts and battery strap never press on parts.
- **Plate:** 85 mm wide × 130 mm tall × 1.6 mm (D-024), 1 mm corner radii.
- **Mechanical holes:** NPTH, with a 1 mm copper keep-out ring on every layer, so no screw or bracket touches a net.

## Motor mounting: the motors overhang the plate

The two motors with encoders are about 67 mm long each (**ASSUMPTION**, JGA25-370 listings). End to end they span about
x ±68 mm, so each gearbox face sits about 25.5 mm outboard of the plate's side edge.
- **Gearbox-face L-brackets don't reach.** A standard 25 mm L-bracket's base leg (25–30 mm) would overlap the plate by
  only 0–3 mm. The bracket needs a base leg of at least about 40 mm, or the motor is held at its can.
- **Adjustable default:** each side gets two M3 slots, 10 mm long along x, at x ≈ ±32 mm, z ≈ +20 and +30 mm.
  These suit a long L-bracket, a printed cradle or a can clamp. **ASSUMPTION:** holes can't go below the axle, because the
  motor can covers z ±12.5 mm and the bottom edge is at z −15 mm.
- **Fixed once the mount is chosen:** the owner picks the bracket or cradle (open item 2). The slots become anchors at gate A.

## Mass budget (from `mechanical/mass_budget.csv`)

| Item | Mass | Position (z above the axle, y from the axle; + = bottom side) | Source |
|---|---|---|---|
| PCB plate 85 × 130 × 1.6 | 33 g | z 50 mm, y −14 mm | D-024, FR-4 1.85 g/cm³ |
| Components | 25 g | z 45 mm, y −16 mm | ASSUMPTION |
| 2 × JGA25-370 + encoder | 2 × 95 g | on the axle | ASSUMPTION, seller listings 90–100 g |
| 2 × bracket | 2 × 12 g | z 0, y −5 mm | ASSUMPTION |
| 3S 1000 mAh LiPo, 75 × 35 × 22 | 85 g | z 60 mm, y −25.8 mm (flat on the top side) | ASSUMPTION |
| Cables, XT30, bumpers, screws | 35 g | z 10–105 mm, y −14 mm | ASSUMPTION |
| 2 × wheel, Ø68 mm | 2 × 35 g | wheel mass M | ASSUMPTION |

Result (S0, `simulation/results/sizing_summary.json`):
- body m = 0.392 kg;
- ℓ = 26.3 mm (was 40.9 mm on the 130 × 170 plate);
- J about the CoM = 4.85e-4 kg·m²;
- **fall time constant τ = 86 ms** (was 102 ms). A 500 Hz loop still gets about 43 updates per τ.
- D-013 holds: 1:9.6 on the 6000 rpm winding recovers 10° at every corner and is still the best choice
  (`simulation/REPORT.md` S0, finding 1).

The motors put about half the body mass on the axle, which keeps ℓ short. The battery's height is limited by the antenna:
its top edge (z 77.5 mm) must stay ≥ 22 mm below the antenna keep-out (`rf-layout` §4: a battery acts as ground).

## Consequences for the firmware

- **Static lean ≈ 21° toward the top side** (S0 finding 8). Phase 0 measured the CoM from the plate plane and got 7°. Measured from
  the axle (the true pivot, 14 mm behind the plate), the plate, the parts and the battery all sit on the top side of the
  pivot.
  - The pitch setpoint must be calibrated.
  - A tilt-based fall cut-off (REQ-SAFE-002) must be measured from that setpoint, not from vertical.
  - Strapping the battery on the **bottom side**, over the motors (z 42.5–77.5 mm, clear of the motor cans), cuts the lean to
    **9.8°**. The strap slots allow either face. This is a change to D-015, so it is the owner's call (open item 4).
- **Track width.** Two 25 mm gearmotors end to end (about 67 mm each with an encoder) plus couplers put the wheel centre
  planes about 0.19 m apart, whatever the plate width. This replaces the 0.145 m placeholder
  (`WheelOdometryImpl.hpp:20`); measure once assembled.
- **Body inertia.** `pendulum-dynamics.md` labels J "about the axle", but its kinetic energy
  ½mv_b² + ½Jθ̇² requires J about the **centre of mass**. S0 uses J about the CoM.
- **Reflected rotor inertia.** J_R = 2·J_rotor·G² ≈ 2.8e-4 kg·m² at 1:9.6, equivalent to
  0.24 kg on the axle. The firmware model (and LQR design) should include it (see
  `simulation/REPORT.md`, S0).

## Open items

1. Weigh the motors, wheels and battery; update `mass_budget.csv`; rerun `sizing.py`.
2. Choose the motor mount (long L-bracket, printed cradle or can clamp) and coupler, then fix the slots as layout anchors.
3. Decide bumper material and position (3D-printed or rubber feet on M3 standoffs).
4. Battery face: top side (D-015, lean 21°) or bottom side (lean 9.8°). Owner decision at gate A.
5. JGA25 output-shaft offset: if the shaft is eccentric, turning it toward the plate moves the axle closer to the
   plate and reduces the lean. Measure it on the purchased motor (**ASSUMPTION**: concentric).
