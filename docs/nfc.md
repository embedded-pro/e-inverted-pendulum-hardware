# NFC tag and I2C EEPROM

Both sit on I2C3 (PB10 SCL, PB11 SDA) with the Qwiic connector (D-030, D-031). The existing 2.2 kΩ pull-ups serve the
whole bus.

| Device | Part (LCSC) | I2C address (7-bit) | Other pins | Source |
|---|---|---|---|---|
| EEPROM 64 Kbit | M24C64-RMN6TP (C79988) | 0x50 (E2..E0 = 0) | WC low: writes enabled | DocID16891 Rev 33, Fig. 2, s2.3–2.4 |
| NFC tag, Type 5 (ISO 15693), 4 Kbit | ST25DV04KC-IE8S3 (C5221752) | 0x53 user memory and dynamic registers, 0x57 system area | GPO (open drain) → PA2 / EXTI2, 10 kΩ pull-up; V_EH unused | DS13519 Rev 6, Table 1, Fig. 2, device-select table |

External Qwiic devices must avoid 0x50, 0x53 and 0x57.

**Bus loading.** Estimated bus capacitance is about 85 pF, below the 100 pF behind the 2.2 kΩ choice (SLVA689A window
967–3541 Ω at 400 kHz, `docs/design-calcs.md`). **ASSUMPTION:** ≤ 10 pF per IC pin (MCU, EEPROM, NFC tag, ESD), about
1 pF/cm over 15 cm of trace, and 30 pF for one Qwiic device with its cable.

## Coil (`scripts/nfc_coil.py`)

The ST25DV resonates its antenna coil with an internal tuning capacitor, C_TUN = **28.5 pF** typ at 13.56 MHz
(DS13519 Rev 6, RF characteristics).

| Item | Value | Source |
|---|---|---|
| Outline | 25 × 21 mm rectangular spiral, top-right corner of the front | D-029, D-030 |
| Track / gap | 0.15 / 0.15 mm (fab design values) | pcb-design-rules profile |
| Turns | 10 | `nfc_coil.py` |
| Inductance | **4.25 µH** (Greenhouse segment sum); modified Wheeler gives 4.24 µH (−0.2 %) | `nfc_coil.py` |
| Resonance with C_TUN + 1 pF parasitic | **14.2 MHz** | `nfc_coil.py`; parasitic is an ASSUMPTION |
| Trim to 13.56 MHz | about 2.9 pF across AC0–AC1; a DNP 0402 C0G footprint (2.7 pF in the BOM line) | `nfc_coil.py` |

**Why tune high.** The coil is designed slightly above 13.56 MHz on purpose. A parallel capacitor can only pull the
resonance down, and nearby metal (the battery below the coil, screws) lowers it as well. ISO 15693 readers in phones
tolerate a few percent of detuning. Fit the trim capacitor only after a phone read-range check or a VNA/loop-probe
measurement on the assembled robot.

**Methods.**
- **Greenhouse.** H. M. Greenhouse, *IEEE Trans. Parts, Hybrids and Packaging* PHP-10(2), 1974.
  - Segment self-inductance of a rectangular bar.
  - Mutual inductance of every pair of parallel segments, from the Neumann integral for parallel filaments.
  - The B.Cu underpass is included 1.49 mm below.
- **Modified Wheeler.** S. S. Mohan et al., *IEEE JSSC* 34(10), 1999: K1 2.34, K2 2.75. Applied to the square of equal
  area, as a cross-check only.

## Footprint and layout rules

`NFC_Coil_25x21mm` is built like KiCad's SWRA117D antenna footprint:
- the spiral is footprint copper on F.Cu, with a B.Cu underpass from the inner via to an outer via;
- pads 1 (AC0) and 2 (AC1) both sit on the coil's left side, toward the ST25DV;
- `net_tie_pad_groups "1,2"` lets the coil join them.

**Layout rules:**
- **No copper on any layer** inside or under the coil, nor within 1 mm around it (rule area `NFC_COIL_KEEPOUT`), apart
  from the coil itself.
- **No metal behind it:** the battery outline on the back stays at least 5 mm below the coil.
- **Short AC0/AC1:** the ST25DV sits next to the coil terminals, and the two AC traces run as a pair (net class like RF).
- **Spacing from the 2.4 GHz antenna:** at least 5 mm from the IFA keep-out band (different bands, but copper in the
  IFA near field detunes it).

## Open items

1. Read-range check with an Android and an iOS phone (NFC Tools) on the assembled robot; fit the trim capacitor if
   the measured resonance (loop probe and VNA) is above 13.8 MHz.
2. The 1 pF parasitic capacitance is an assumption; the measured f0 replaces it.
