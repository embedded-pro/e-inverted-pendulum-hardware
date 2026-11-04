# Pin map: STM32WB55RGV6 (VFQFPN68)

- **Source of truth:** `pin-data/pinmap.csv`.
- **Validation:** `scripts/check_pinmap.py --firmware ../e-inverted-pendulum`.
- **Package data:** `pin-data/stm32wb55rgvx_vfqfpn68.csv`, extracted by
  `scripts/extract_pin_data.py` from KiCad 9's `MCU_ST_STM32WB:STM32WB55RGVx` symbol, which is
  generated from ST's STM32_open_pin_data. Spot-checked against DS11929 Rev 11 Tables 16 and 18.

The plan called for a CubeMX `.ioc`. STM32CubeMX can't run in this environment, so the script
replaces it for bonding, alternate functions, EXTI uniqueness and firmware parity. Generating the
`.ioc` (clock tree, SMPS, LSE) is left for someone with CubeMX installed. It doesn't block the
schematic.

## What the check enforces

1. Every pin is bonded on VFQFPN68.
2. Every alternate function or ADC channel exists on its pin.
3. One signal per pin. The only shared net is `DRV_NFAULT`, which reaches PA6 (TIM1_BKIN) and
   PC4 (EXTI4), as the firmware expects.
4. Unique EXTI lines. In use: 0 (button), 3 and 5 (encoder index), 4 (driver fault),
   6 (IMU data-ready).
5. Firmware parity: all 26 pins declared in `targets/platform_implementations/st/*.hpp` sit
   on the same pins.

## Firmware-visible changes

None to existing pins. New signals for the firmware's board target:

| Signal | Pin | Use |
|---|---|---|
| FLASH_CS | PA15 | W25Q16 on SPI1 (shared with the DRV8711; mode 0 suits both) |
| VBAT_SENSE | PC1 / ADC1_IN2 | battery voltage, 100 k/27 k divider |
| BUZZER | PA7 / TIM17_CH1 | buzzer via NPN |
| LED_FAULT | PB1 | red LED (green stays on PB0) |
| USER_BUTTON | PD0 / EXTI0 | user button (NUCLEO SW2 pin) |
| I2C3 SCL/SDA | PB10 / PB11 | Qwiic expansion |
| DRV_STALLN | PB2 | optional DRV8711 nSTALL input |

## Consequences

- **No SWO:** PB3 is SPI1_SCK.
- **No USB:** PA11 is TIM1_CH4 (D-009).
- **SWD only:** PA15 (JTDI) is FLASH_CS, so firmware must not enable JTAG.
- **Reset-safe bridge:** PA8–PA11 and PB8 get pull-downs so the bridge stays tri-stated and the
  driver asleep while the MCU is in reset (HW-DRV-005).
