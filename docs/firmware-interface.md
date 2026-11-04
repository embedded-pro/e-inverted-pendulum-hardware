# Firmware interface: what the board needs from the firmware

The firmware's board target for this PCB (a copy of `targets/platform_implementations/st/`) must
apply these settings. Every existing pin is unchanged (`docs/pinmap.md`).

| Area | Requirement | Source |
|---|---|---|
| Clocks | LSE drive LSEDRV = 10 (medium-high) | DS11929 Table 54; `docs/design-calcs.md` |
| Clocks | HSE trim (HSETUNE): median of a sample of boards, stored in OTP | AN5042; rf-layout s6 |
| Power | SMPS may be enabled (10 µH + 10 nH fitted); bypass for precision ADC reads if needed | DS11929 s3.7 |
| Debug | SWD only; PA15 (JTDI) is FLASH_CS, so JTAG must stay off | `docs/pinmap.md` |
| Unused pins | Every unconnected GPIO in analog mode | mcu-circuit-design s6 |
| IMU | MPU-6500: accept WHO_AM_I 0x70; set I2C_IF_DIS right after start-up; SPI ≤ 1 MHz for config, ≤ 20 MHz for sensor reads; INT active-high push-pull pulse | PS-MPU-6500A-01 s6.1, Table 5 |
| IMU axes | Board mounted vertically: publish the body-frame axis map once the layout fixes the IMU orientation (REQ-IMU-007) | HW-SNS-002 |
| SPI1 | Shared by the DRV8711 (CS PA4, active-high, mode 0, ≤ 4 MHz) and the W25Q16 (CS PA15, active-low, mode 0, ≤ 133 MHz); per-device prescaler | SLVSC40 p.8; W25Q16JV s6.1 |
| DRV8711 | PWMMODE = 1; ISGAIN 40, TORQUE 242 (I_trip 1.30 A with 50 mΩ); TBLANK ≥ 1.2 µs; DTIME 850 ns as today; continuous motor rating enforced by an I²t model (D-014) | S0; SLVSC40 p.7, p.11 |
| Flash | JEDEC ID EFh 4015h; wait 5 ms after power-up before writes | W25Q16JV s9.1, s10.3 |
| Battery | VBAT = ADC(PC1) / 0.2126; calibrate per board; arm only above 9.9 V; logic cuts at about 8.5 V in hardware | `docs/design-calcs.md` |
| Encoders | A/B/Z unchanged; index on EXTI5 (left) / EXTI3 (right) for REQ-ODOM-005; gear 9.6; CPR = 4 × lines × 9.6; LPTIM1 clocked from PCLK/HSI16 | S0; D-013 |
| UI | Green LED PB0, red LED PB1 (active high); buzzer PA7 TIM17_CH1 at about 2.7 kHz; user button PD0 (active low, EXTI0) | `docs/pinmap.md`; MLT-8530 |
| Expansion | Qwiic on I2C3 (PB10 SCL, PB11 SDA), 3V3 | `docs/pinmap.md` |
| Model | Pitch setpoint about 7°; track width about 0.19 m; include reflected rotor inertia; J about the CoM | `docs/mechanical.md`; S0 |
