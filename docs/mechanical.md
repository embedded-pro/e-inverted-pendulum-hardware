# Mechanical concept: the PCB on a WHEELTEC U-bracket

Status: Phase 3, re-baselined 2026-11-13 for the owner's hardware (D-025 to D-029). Dimensions marked **ASSUMPTION**
become anchors once the parts are measured. `mechanical/mass_budget.csv` is the single source for
`simulation/sizing.py`.

## Coordinates

- **x:** across the plate, along the wheel axle; x = 0 on the vertical centreline. The plate spans x −42.5 … +42.5 mm.
- **z:** up the plate, with z = 0 on the wheel axle at the centre of the 25 mm bracket strip. The bottom edge is
  z −12.5 and the top edge z +117.5 (D-024 outline, D-026 axle).
- **y:** through the plate, from its mid-plane, positive toward the **back** (where the bracket, motors and battery
  are). The front is the component side.

The pivot is the wheel axle: y = +18.8 mm, i.e. the bracket leg's hole 18 mm from the base plus the 0.8 mm half plate.

## Arrangement

Side view (robot drives left/right on the page):

```
                 front │ │ back
                (parts)│ │
   z 117.5 ────────────┤ │  2.4 GHz antenna band (front, all layers)
                       │ │
   z 79    ────────────┤ ├────────┐
                       │ │BATTERY │ 22 mm thick, on a printed cradle (4 × M3)
   z 44    ────────────┤ ├────────┘
                       │ │
   z 12.5  ────────────┤ ├─┐  bracket base (2 mm steel) on the back of the strip
   z 0     ─ ─ ─ ─ ─ ─ ┤ ├─┼──────(●) motor axis = wheel axle, y = +18.8 mm
   z −12.5 ────────────┴─┴─┘
```

Front view (component side):

```
 x −42.5                                              +42.5
   ┌──────────────────────────────────────────────────┐ z 117.5
   │ ░░░░░░░ 2.4 GHz IFA keep-out band (all layers) ░░░░░░│
   │  MCU top centre, IMU beside it        NFC coil      │
   │                                                    │ z ~86
   │       (battery behind this band: SMD parts only)   │ ◄ STDC14 at the middle of the right edge
   │                                                    │ z ~44
   │► motor L (PH6)       DRV8711 + bridges     motor R ◄│
   ├──────────────────────────────────────────────────┤ z 12.5
   │ ○M3  ∘M2     bracket strip: no parts        ∘M2  ○M3│ (axle z 0)
   └──────────────────────────────────────────────────┘ z −12.5
      bracket legs 8.5 mm outside each side edge (x ±51)
```

- **Front:** every SMD part (JLC single-side PCBA), with no parts in the bottom 25 mm strip.
- **Back:** the bracket in the strip, the motors behind it, and the battery above them. No parts.
- **Plate:** 85 mm wide × 130 mm tall × 1.6 mm (D-024).
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
| PCB plate 85 × 130 × 1.6 | 33 g | z 52.5, y −18.8 mm | D-024, FR-4 1.85 g/cm³ |
| Components | 30 g | z 60, y −20.8 mm | ASSUMPTION |
| 3S 1000 mAh LiPo, 75 × 35 × 22 | 85 g | z 61.5, y −7.0 mm (on the back) | ASSUMPTION |
| Battery cradle | 10 g | z 61.5, y −12.8 mm | ASSUMPTION |
| 2 × MG310 + encoder | 2 × 65 g | on the axle | ASSUMPTION |
| WHEELTEC bracket | 64 g | z 0, y −11.7 mm | derived: 8.2 cm³ of steel |
| Screws, cables, XT30 lead, bumpers | 35 g | z 10–100 mm | ASSUMPTION |
| 2 × wheel, Ø65 mm | 2 × 30 g | wheel mass M | owner: 65 mm; mass ASSUMPTION |

Result (S0, `simulation/results/sizing_summary.json`):
- body m = 0.387 kg;
- ℓ = 29.6 mm;
- J about the CoM = 4.59e-4 kg·m²;
- **fall time constant τ = 84 ms**: about 42 updates per τ at 500 Hz.

## Consequences for the firmware

- **Static lean ≈ 17° toward the front.** The bracket puts the axle 18.8 mm behind the plate. The plate and parts
  are in front of it, and even the back-mounted battery is 7 mm in front (battery on the front: 26°).
  - Calibrate the pitch setpoint.
  - Measure the fall limit (REQ-SAFE-002) from that setpoint, not from vertical.
- **Wheel radius 0.0325 m** (65 mm wheels, owner). **Track width ≈ 0.15 m**: wheel centre planes about 24 mm outside
  the 102 mm bracket (shaft, hub and half the wheel width; measure once assembled). This replaces the 0.145 m
  placeholder (`WheelOdometryImpl.hpp:20`).
- **IMU position.** The IMU sits beside the MCU near the top, about 90 mm above the axle (D-029). Its accelerometer
  reads the tangential acceleration r·θ̈ on top of gravity. The firmware must subtract it (r from the layout, θ̈ from the
  gyro) or keep the complementary-filter crossover low.
- **Body inertia:** J about the **centre of mass** (`pendulum-dynamics.md` labels it "about the axle"). The
  reflected rotor inertia, J_R = 2·J_rotor·G² ≈ 8e-4 kg·m² at 1:20, belongs in the plant model (S0).

## Open items

1. Weigh the motors, wheels, bracket and battery; update `mass_budget.csv`; rerun `sizing.py`.
2. Confirm the bracket's 18 mm axis-to-base dimension and which base holes carry the screws.
3. Design the battery cradle on the 4 × M3 holes (`docs/layout.md`). Falling backward lands on the battery,
   so the cradle should have a lip that takes the impact.
4. Bumpers (HW-MEC-004): MH1 top-left and MH2 on the right edge below the NFC coil. Use nylon hardware, because MH2
   is near the NFC coil.
