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
| DRV8711 | PWMMODE = 1; **ISGAIN 20, TORQUE 186 (I_trip 2.0 A with 50 mΩ)**; IDRIVEP = IDRIVEN = 00; TBLANK ≥ 1.2 µs; DTIME 850 ns as today; 0.5 A continuous motor rating enforced by an I²t model | S0 (D-027), S2 (D-022); SLVSC40 p.7, p.11 |
| Flash | JEDEC ID EFh 4015h; wait 5 ms after power-up before writes | W25Q16JV s9.1, s10.3 |
| Battery | VBAT = ADC(PC1) / 0.2126, sampled at ≤ 100 Hz; per-board calibration stored in flash (needed for ±50 mV/cell); arm only above 9.9 V; undervoltage fault and disarm below ~9.5 V under load (hardware cut-off at 8.47 V) | `docs/design-calcs.md`; S3, S5 |
| Power switch | Switching off takes ~100 ms (soft gate); stop the motors before the switch is turned off | S1 (D-021) |
| Encoders | MG310 Hall A/B only: **no index**, so REQ-ODOM-005 can't be met with this motor (PC5/PC3 read low). Gear 20; CPR = 4 × 13 × 20 = **1040** counts per wheel revolution (13 PPR ASSUMED, count at bring-up); LPTIM1 clocked from PCLK/HSI16 | S0; D-027, D-028 |
| UI | Green status LED PB0 (active high, unchanged). **12 × WS2812B-2020-V6 RGB LEDs on PA7 (`LED_DATA`, TIM17_CH1 PWM + DMA)**: WS2812 protocol, GRB order, MSB first, 1.25 µs bit, reset ≥ 280 µs; PA7 idles low (10k pull-down). The hardware is sized for all 12 at full white (432 mA on +5V); brightness is a firmware choice. No buttons, no buzzer (D-035); PD0 and PB1 unused. BOOT0: no button, use the boot option bytes over SWD or bridge TP302 to +3V3 at reset | `docs/pinmap.md`; WS2812B-2020-V6 datasheet p.4–5; D-035 |
| Expansion | Qwiic on I2C3 (PB10 SCL, PB11 SDA), 3V3 | `docs/pinmap.md` |
| Model | m 0.387 kg, ℓ 28.6 mm, J 4.35e-04 kg·m² about the CoM, τ 83 ms; **pitch setpoint about 18° toward the front**; fall limit measured from the setpoint; wheel r **0.0325 m**; track width about 0.15 m; include the reflected rotor inertia (≈ 8e-4 kg·m²) | `docs/mechanical.md`; S0 |
| Motor voltage | Cap the **average motor voltage at 7.4 V** (duty ≤ 7.4 / VBAT): the MG310 is a 7.4 V motor on a 3S bus | S0 (D-027) |
| IMU position | IMU about 90 mm above the axle, beside the MCU: subtract the tangential acceleration r·θ̈ from the accelerometer (θ̈ from the gyro) or keep the complementary-filter crossover low; publish the axis map once the layout fixes the orientation | D-029; `docs/mechanical.md` |
| I2C3 devices | Qwiic expansion plus **M24C64 EEPROM at 0x50** (E2..E0 = 0, WC low: writes enabled; 32-byte pages, 5 ms write cycle) and **ST25DV04KC NFC tag** at 0x53 (user memory) / 0x57 (system); keep external Qwiic devices off these addresses | D-030, D-031; M24C64 and ST25DV04KC datasheets |
| NFC GPO | ST25DV04KC GPO on **PA2 (EXTI2)**: RF field / RF write interrupt; configure the GPO in the tag's system area | D-030 |
