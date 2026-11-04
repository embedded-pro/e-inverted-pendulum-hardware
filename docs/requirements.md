# Hardware requirements

Every requirement traces to a firmware requirement (`REQ-*`, in
`e-inverted-pendulum/documentation/requirements/*.yaml`), a firmware design fact (file:line in
that repo), or a decision in `docs/decisions.md`.

Verification methods:
- **R**: design review against the schematic or layout;
- **S**: simulation in `simulation/` (S0–S5, see `docs/plan.md`);
- **B**: bring-up test in `docs/bringup.md`.

## Power

| ID | Requirement | Source | Verify |
|---|---|---|---|
| HW-PWR-001 | The board shall run from a 3S LiPo over 9.0–12.6 V and survive 13.5 V (a pack charged with a mis-set charger) without damage. | D-003 | R, S1 |
| HW-PWR-002 | The motor bus (VM) shall stay ≥ 8.0 V, the DRV8711 VM minimum (TI SLVSC40), at the lowest battery voltage under peak motor current. | D-003 | S1, S3 |
| HW-PWR-003 | Reverse battery connection shall neither damage the board nor apply more than 1 mA to any load. | `mcu-circuit-design` §11 | S1, B |
| HW-PWR-004 | When the board is switched off while the wheels turn, regenerated energy shall not raise VM above 24 V. The TVS clamp must stay under the lowest absolute maximum on the bus: 30 V (TPS62933 VIN). | D-011 | S1 |
| HW-PWR-005 | 3V3 ripple at VDDRF shall stay within ST AN5165 limits. | `rf-layout` §5 | S4, B |
| HW-PWR-006 | Battery voltage shall be measurable by the MCU ADC with ±50 mV/cell accuracy (3σ). This closes the open undervoltage item in the firmware's `safety-supervisor.md`. | firmware `safety-supervisor.md` "Open items" | S5, B |
| HW-PWR-007 | A single switch shall disconnect every load from the battery. Off-state drain ≤ 10 µA. | D-011 | R, B |

## Motor drive

| ID | Requirement | Source | Verify |
|---|---|---|---|
| HW-DRV-001 | One DRV8711 shall drive two brushed DC motors, bridge A = left and bridge B = right, through its xIN inputs with the indexer bypassed. | REQ-DRIVE-002, `motion-actuation.md` Part A | R |
| HW-DRV-002 | The four bridge inputs AIN1/AIN2/BIN1/BIN2 shall connect to PA8/PA9/PA10/PA11 (TIM1 CH1–CH4). | `MotorDriverStm.cpp:19-28` | R (`check_pinmap.py`) |
| HW-DRV-003 | DRV8711 nFAULT shall connect to both PA6 (TIM1_BKIN) and PC4 (EXTI4), so a fault tri-states all four inputs in hardware. | REQ-DRIVE-004, REQ-SAFE-006, `MotorDriverStm.hpp:34-35` | R, B |
| HW-DRV-004 | The DRV8711 shall be configurable and readable over SPI1 (PB3/PB4/PB5, CS PA4 active-high). SLEEPn = PB8, RESET = PB9. | REQ-DRIVE-001, REQ-SYS-003 | R, B |
| HW-DRV-005 | With the MCU in reset or unpowered, the bridges shall be tri-stated: every xIN low and SLEEPn asserted, using pull-downs. | REQ-SYS-002, REQ-SAFE-009 | R, B |
| HW-DRV-006 | Rsense shall let the configured trip current span from below the motor's rated current up to its stall current, with TORQUE ≤ 255 at the chosen ISGAIN (`Drv8711DriverConfiguration.cpp:10-19`). | REQ-DRIVE-005 | S0, S2 |
| HW-DRV-007 | The bridges shall switch at 25 kHz centre-aligned. Current ripple shall be within the S0 bound for the motor's electrical time constant. | REQ-DRIVE-007, `MotionActuationImpl.hpp:18` | S0, S2 |
| HW-DRV-008 | FET junction temperature shall stay < 100 °C at the worst-case continuous current and 40 °C ambient. | `power-pcb-layout` §3.7 | S2, B |
| HW-DRV-009 | Motor connectors shall carry the trip current continuously. | D-002 | R |

## Sensing

| ID | Requirement | Source | Verify |
|---|---|---|---|
| HW-SNS-001 | The IMU (MPU-6500) shall be on SPI2 (PB13/PB14/PB15, CS PB12), with data-ready on PC6 (EXTI6). | REQ-IMU-001, `InertialSensorStm.hpp:31-38` | R |
| HW-SNS-002 | The IMU shall be mounted rigidly on the body's sagittal centreline, axes aligned to the body frame (x forward, y left, z up). The mounting-to-body axis map is published for the firmware. | REQ-IMU-007, `imu-sensing.md` | R |
| HW-SNS-003 | Left encoder A/B/Z = PC0 (LPTIM1_IN1) / PC2 (LPTIM1_IN2) / PC5. Right encoder A/B/Z = PA0 (TIM2_CH1) / PA1 (TIM2_CH2) / PC3. | REQ-ODOM-001, REQ-ODOM-005, `WheelEncodersStm.hpp:23-29` | R (`check_pinmap.py`) |
| HW-SNS-004 | Encoder inputs shall carry clean edges up to the maximum edge rate from S0 with ≥ 2× margin. They shall not back-power the MCU while 3V3 is off. | REQ-ODOM-001, D-012 | S5, B |
| HW-SNS-005 | The index (Z) lines shall reach EXTI-capable pins with unique EXTI line numbers. | REQ-ODOM-005, `imu-sensing.md` (EXTI uniqueness) | R (`check_pinmap.py`) |

## Radio, clocks, storage, interfaces

| ID | Requirement | Source | Verify |
|---|---|---|---|
| HW-RF-001 | The BLE link shall work through an on-board antenna with the battery and motors fitted. | REQ-LINK-001 | B (VNA, RSSI) |
| HW-RF-002 | HSE 32 MHz with total error ≤ ±50 ppm after trim. LSE 32.768 kHz within ±500 ppm (BLE sleep clock). | `rf-layout` §6, `PlatformImpl.cpp:3`, `PlatformImpl.hpp:88` | R, B |
| HW-MEM-001 | Non-volatile storage for parameters and bonds: W25Q16 on SPI1 with CS on PA15. | REQ-TUNE-007, D-005 | R, B |
| HW-IF-001 | USART1 (PB6 TX / PB7 RX) console, SWD and NRST on an STDC14 connector. | `PlatformImpl.hpp:61-65`, D-009 | R, B |
| HW-IF-002 | A user button, two LEDs and a buzzer for local status. | firmware has none; added by D-009 review | R |
| HW-IF-003 | Every off-board signal shall have ESD protection at its connector. | `mcu-circuit-design` §6, `interface-layout` §2 | R |

## Mechanical

| ID | Requirement | Source | Verify |
|---|---|---|---|
| HW-MEC-001 | The PCB shall be the pendulum body. It carries both motors (bracket holes), the battery (strap slots) and every electronic part. | D-006 | R |
| HW-MEC-002 | Wheel radius about 0.034 m and track width about 0.145 m, as the firmware's placeholders. Final values are measured and fed back to the firmware. | `WheelOdometryImpl.hpp:19-20` | R |
| HW-MEC-003 | Mass, CoM height ℓ and inertia J shall be computed from the CAD/mass budget and published for the firmware model. | `pendulum-dynamics.md` | S0 |
| HW-MEC-004 | A fall shall not strike the antenna edge: bumpers on both faces near the top. | D-007 | R |
