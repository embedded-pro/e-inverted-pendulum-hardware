# Mechanical concept: the PCB is the chassis

Status: Phase 0 concept. Dimensions marked **ASSUMPTION** become anchors once the motors, wheels
and battery are in hand and weighed. `mechanical/mass_budget.csv` is the single source for
`simulation/sizing.py`.

## Arrangement (side view: robot drives left/right on the page)

```
            ┌─────────┐  ← top edge: printed IFA antenna, keep-out on all layers
            │ ANTENNA │    bumpers on both faces just below it (HW-MEC-004)
            │  MCU/RF │
  bottom    │░BATTERY░│ top side (components + battery in a keep-out zone, strap slots)
  side ───► │  logic  │
 (motors)   │   IMU   │ ← sagittal centreline, ~30 mm above the axle
   ┌────────┤ DRV8711 │
   │ MOTOR  │  FETs   │
   └──(●)───┴─────────┘ ← bottom edge, axle 15 mm above it
      wheel axle (lateral, into the page)
```

- **Top side:** every SMD part (JLC single-side PCBA) plus the battery, which sits in a
  component keep-out zone held by a strap through two milled slots.
- **Bottom side:** the two gearmotors on L-brackets, end to end on the axle line, output
  shafts facing out. No components on this face, so the motor brackets, nuts and battery
  strap never press on parts.
- **Plate (ASSUMPTION):** 130 mm wide × 170 mm tall × 1.6 mm. 130 mm fits between the two
  gearbox faces.
- **Bracket holes:** NPTH M3 with a 1 mm copper keep-out ring on every layer, so the bracket
  never touches a net.

## Mass budget (from `mechanical/mass_budget.csv`)

| Item | Mass | Position (z above axle, y toward bottom side) | Source |
|---|---|---|---|
| PCB plate 130×170×1.6 | 65 g | z 70 mm | ASSUMPTION, FR-4 1.85 g/cm³ |
| Components | 25 g | z 60 mm | ASSUMPTION |
| 2 × JGA25-370 + encoder | 2 × 95 g | on the axle, y +14 mm | ASSUMPTION, seller listings 90–100 g |
| 2 × bracket | 2 × 12 g | on the axle, y +14 mm | ASSUMPTION |
| 3S 1000 mAh LiPo, 75×35×22 | 85 g | z 100 mm, y −12 mm | ASSUMPTION |
| Cables, XT30, bumpers, screws | 35 g | z 40–125 mm | ASSUMPTION |
| 2 × wheel, Ø68 mm | 2 × 35 g | wheel mass M | ASSUMPTION |

Result (S0):
- body m = 0.424 kg;
- ℓ = 40.9 mm;
- J about the CoM = 1.05e-3 kg·m²;
- **fall time constant τ = 102 ms**.

The motors put a lot of mass on the axle, which keeps ℓ short. Raising the battery is the
cheapest way to slow the fall. It stops at z ≈ 100 mm, about 22 mm below the antenna
keep-out (`rf-layout` §4: a battery acts as ground).

## Consequences for the firmware

- **Static lean ≈ 7°.** The CoM sits 4.9 mm toward the motor side, so the plate balances
  tilted about 7° and the pitch setpoint must be calibrated. Moving the battery further
  toward the top side reduces this.
- **Track width.** Two 25 mm gearmotors end to end (about 67 mm each with an encoder) plus
  couplers put the wheel centre planes about 0.19 m apart. This replaces the 0.145 m
  placeholder (`WheelOdometryImpl.hpp:20`); measure once assembled.
- **Body inertia.** `pendulum-dynamics.md` labels J "about the axle", but its kinetic energy
  ½mv_b² + ½Jθ̇² requires J about the **centre of mass**. S0 uses J about the CoM.
- **Reflected rotor inertia.** J_R = 2·J_rotor·G² ≈ 2.8e-4 kg·m² at 1:9.6, equivalent to
  0.24 kg on the axle. The firmware model (and LQR design) should include it (see
  `simulation/REPORT.md`, S0).

## Open items

1. Weigh the motors, wheels and battery; update `mass_budget.csv`; rerun `sizing.py`.
2. Decide the motor bracket and coupler, then fix the hole pattern as a layout anchor.
3. Decide bumper material and position (3D-printed or rubber feet on M3 standoffs).
