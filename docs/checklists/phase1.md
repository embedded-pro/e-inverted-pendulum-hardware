# Phase 1 gate: schematic checklist

Evidence key:
- **ERC** = `kicad-cli sch erc --severity-all` (0 errors, 0 warnings).
- **NET** = `scripts/check_netlist.py` (MCU pins match `pin-data/pinmap.csv`; supply pins on their rails; no single-pin nets; LCSC, MPN and footprint present on every BOM part).
- **LIB** = `scripts/check_library.py` (every symbol pin ↔ footprint pad, 171 pairs).
- **BOM** = `scripts/jlc_stock.py bom/bom.csv --boards 5` (64 lines, all in stock).
- **CALC** = `docs/design-calcs.md`.

Status legend: ✅ done · ⚠️ open (reason given) · ➖ not applicable.

## mcu-circuit-design §12

| Item | Status | Evidence |
|---|---|---|
| Design guide, datasheet, errata and eval board in hand | ⚠️ | DS11929 Rev 11 (via C404023) and Rev 4 (via C401505) are in `datasheets/`. AN5165, AN2867 and the STM32WB55 errata are **not**: st.com is unreachable from this environment. Needed before layout. |
| Every power pin with its capacitors per the datasheet | ✅ | DS11929 Fig. 16/14: VDD 3 × 100 nF + 4.7 µF; VDDA/VREF+ 10 nF + 1 µF + 100 nF + 1 µF behind a ferrite; VDDRF 100 nF + 100 pF; VDDSMPS 4.7 µF; VBAT and VDDUSB on VDD with 100 nF; NET checks the rails |
| SMPS parts per datasheet | ✅ | 10 µH LQM21FN100M80L + 10 nH LQG15HS10NJ02D + 4.7 µF (DS11929 Rev 11 Table 6 and note 2). PWR_FLAG on SMPS_LX. |
| Reset: pin type, vendor parts, on the debug header | ✅ | NRST 100 nF (DS11929 Fig. 24), STDC14 pin 12 |
| Boot selection defined, bootloader reachable | ✅ | BOOT0 (PH3): 10 k pull-down, plus a button to 3V3 through 1 k |
| Crystal: C_L maths, margin, drive | ✅ | HSE: NX2016SA CS06654 (ST reference part, C_L 8 pF, ≤ 100 µW), no external caps (HSETUNE). LSE: C_L 6 pF, 2 × 6.8 pF, LSEDRV = 10 for gain margin ≈ 2.5 (CALC). |
| Debug: standard connector, pulls per vendor | ⚠️ | STDC14 pinout from KiCad's `Conn_ST_STDC14` (ST). SWO unavailable (PB3 = SPI1_SCK). **The footprint is the generic 2×07 1.27 mm SMD header; the Samtec FTSH-107-01-L-DV-K SMT land pattern still has to be checked against Samtec's drawing** (the LCSC PDF covers only the through-hole series). |
| Off-board signals: series R/RC, clamp at the connector | ✅ | Encoders: TPD4E05U06, 100 Ω + 1 nF, Schmitt buffer. Qwiic: TPD4E05U06. Battery: SMBJ15A. Waivers: motor outputs rely on the bridge FET body diodes and the VBAT TVS; STDC14 is an internal service port with no ESD part. |
| Injection and unpowered limits | ✅ | Encoder inputs go through SN74LVC3G17 (I_off), so 5V0 never reaches FT pins while 3V3 is off (D-012) |
| Unused pins in the vendor's preferred state | ⚠️ | Unused GPIOs are no-connects; the firmware must set them to analog mode (`docs/firmware-interface.md`) |
| TVS: working voltage, clamp, polarity | ✅ | SMBJ15A V_RWM 15 V > 13.5 V, V_C 24.4 V < 30 V; downstream of the reverse-polarity FETs |
| USB | ➖ | No USB (D-009) |
| I2C pull-ups per SLVA689A | ✅ | 2.2 k inside the 967–3541 Ω window |
| Coils suppressed | ✅ | Buzzer: 1N4148WS across the coil. Motors: optional DNP RC at the connector. |
| Reverse polarity on the board input | ✅ | AO4805 back-to-back P-FETs (D-011); off-state leakage limited to FET I_DSS + zener I_R (≤ 1.1 µA by datasheet) |

## analog-circuit-design §10

| Item | Status | Evidence |
|---|---|---|
| Requirements as numbers | ✅ | HW-PWR-006: ±50 mV/cell 3σ (`docs/requirements.md`) |
| Inputs from outside the board: fault current, clamps | ✅ | VBAT divider sits after the switch; 13.5 V gives 2.87 V < VDDA; 100 k limits any fault current to < 0.15 mA |
| ADC drive: bucket ≥ 20 × C_sample, settling | ✅ | 100 nF ≫ 100 pF; 21.3 kΩ source < 50 kΩ R_AIN max (DS11929 Table 73) |
| Error budget | ⚠️ | ±1.57 % worst case with 1 % resistors (CALC). Meeting the 3σ target needs per-board calibration plus VREFINT; Monte Carlo is S5 in Phase 2. |
| Op amps, references | ➖ | None |

## rf-layout (schematic items)

| Item | Status | Evidence |
|---|---|---|
| Module vs chip-down decided | ✅ | Chip-down with MLPF-WB55-01E3 IPD (D-007) |
| Match/filter per vendor; direction | ✅ | DS12804 Table 6: IN (A3) to RF1, OUT (A1) to the antenna; footprint from Fig. 13 |
| DNP tuning network at the antenna | ✅ | Pi: 2 × DNP shunt, 0 Ω series |
| Conducted test port | ✅ | U.FL (DNP) through a DNP 0 Ω |
| SMPS parts and decoupling per vendor | ✅ | See above |
| Crystal ppm budget | ⚠️ | ±10 ppm initial, then trimmed by HSETUNE (AN5042). Temperature and ageing figures for CS06654 are not in the catalog page. Trim plan is in bring-up. |
| Clock harmonics vs used channels | ⚠️ | 32 MHz HSE lands at 2432/2464 MHz (inherent to STM32WB); buck 1.2 MHz FCCM; SMPS 4 MHz. Pre-compliance scan is out of scope (no certification, D-007). |
| Antenna and stack-up match | ⚠️ | TI SWRA117D antenna footprint from KiCad. Its reference board thickness has to be checked against 1.6 mm, and the 50 Ω GCPW width computed for JLC04161H-7628, in Phase 3. |

## interface-layout §2 (connector ESD)

| Item | Status | Evidence |
|---|---|---|
| TVS at the connector, pass-through | ✅ (schematic) | TPD4E05U06 per connector; pass-through routing is a Phase 3 layout rule (SLVSBO7L Fig. 24) |
| Low-capacitance parts on fast lines | ✅ | 0.5 pF/channel |

## Safety chain (HW-DRV-005, REQ-SYS-002, REQ-SAFE-009)

| Item | Status | Evidence |
|---|---|---|
| Bridge inputs low while the MCU is in reset | ✅ | DRV8711 internal pull-downs on AIN1/AIN2/BIN1/BIN2/RESET/SCS (SLVSC40 p.3) |
| Driver asleep while the MCU is in reset | ✅ | SLEEPn 10 k pull-down (no internal pull) |
| nFAULT reaches TIM1_BKIN and EXTI | ✅ | Net DRV_NFAULT on PA6 and PC4 (NET) |
| Logic shuts down before over-discharge | ✅ | TPS62933F EN UVLO: start 9.11 V, stop 8.47 V (CALC) |

## Open before the Phase 3 layout

1. Get the Samtec FTSH-107-01-L-DV-K SMT drawing and confirm or replace the STDC14 footprint.
2. Get ST AN5165, AN2867 and the STM32WB55 errata.
3. Get TI SWRA117D; check the antenna's reference thickness and ground clearance.
4. Confirm the motor/encoder cable pinout against the purchased parts (D-016) and re-pin J601–J604 if needed.
5. Confirm the XT30UPB-F polarity marking and the MLT-8530 pad view (top or bottom) against the physical parts.
