# RF design: 2.4 GHz path, antenna and layout rules

Chip-down radio with no certification (D-007). The path is
RF1 → MLPF-WB55-01E3 IPD → 50 Ω GCPW → DNP pi tuning network → TI SWRA117D printed IFA, with a DNP U.FL
conducted test port. The `rf-layout` skill governs this document; its section numbers are cited as rf-layout §n.

**Sources.**
- STM32WB55 datasheet DS11929.
- MLPF-WB55-01E3 datasheet DS12804 Rev 2 (land pattern Fig. 13, stack-up Fig. 14).
- TI SWRA117D (AN043, the antenna).
- The `rf-layout` skill.
- ST AN5165 and AN2867 can't be reached from this environment (st.com blocks automated requests). Their rules are taken
  from the skill's summary and must be checked against the notes before the layout is frozen (open item 1).

## Stack-up and the 50 Ω line

| Item | Value | Source |
|---|---|---|
| Stack-up | JLC04161H-7628, 1.6 mm, L1 over a solid L2 GND; JLCPCB only (D-036) | D-008, D-036 |
| L1 → L2 | 0.2104 mm 7628 prepreg, Dk 4.4 (≤ 0.8 mm per rf-layout §2) | JLCPCB stack-up |
| Line type | GCPW (rf-layout §2: less sensitive to thickness, isolates better) | AN928.2, AN91445 |
| **50 Ω GCPW** | **0.27 mm track, 0.15 mm gap** to top-layer GND (49.8 Ω; solder mask, ignored by the model, lowers it by about 1–2 Ω) | `scripts/gcpw.py` |
| Tolerance corners | 42.7–57.3 Ω (width ±0.03 mm, h ±10 %, Dk ±5 %): return loss ≥ 22 dB | `scripts/gcpw.py` |
| Guided wavelength | λg ≈ 72 mm at 2.45 GHz (ε_eff 2.90) | `scripts/gcpw.py` |

**Calculator check.** `gcpw.py` reproduces ST's own line: DS12804 Fig. 13 OUT, 450 µm with 106.4 µm gaps on the
Fig. 14 stack-up (1.507 mm FR-4, 48 µm copper), comes out at 47.9 Ω. Without the ground plane underneath, the same
formulas reduce to microstrip, which needs 0.40 mm on our stack-up.

**The DS12804 widths are not copied for the 50 Ω section.** ST's 450 µm line is 50 Ω on a 2-layer 1.5 mm
board. On our 0.21 mm prepreg it would be about 30 Ω. The 50 Ω section is recalculated (above); the matching section
from RF1 is copied (next section).

**GCPW rules (rf-layout §2).**
- Gap 0.15 mm, smaller than h = 0.21 mm.
- Top GND pour on both sides at least 1 mm wide. Width and gap stay constant.
- L1 only: no vias, stubs, branches or test points on the line. Bends at 135° or curved.
- Nothing on L2 except solid GND under the line, its pads and the MLPF.
- Via fence on both sides: 0.3 mm drill / 0.6 mm pad, 0.3 mm from the gap edge, **pitch 1.0–1.3 mm**.
- Solder mask stays on the line (it lowers Z0 by about 1–2 Ω and keeps paste out of the 0.15 mm gaps). Pads are
  mask-defined per DS12804.
- Confirm with JLC's impedance calculator, and order with impedance control (50 Ω ±10 % on the L1 GCPW over L2); JLC
  adjusts the width to its stack-up (open item 2).

## MLPF-WB55-01E3 and the matching trace

The IPD is both the match and the harmonic filter (rf-layout §3). Copy FL401's surroundings **geometrically** from DS12804 Fig. 13:
- **IN (A3) is 1.5 mm from the RF1 pad** (pin 31), along a 200 µm trace with 104 µm gaps. This trace is part of the match.
  On our stack-up it is 52.1 Ω instead of 58.6 Ω, over 1.5 mm (0.02 λg). The shift is small, and the VNA tuning covers it.
- **OUT (A1)** starts the 50 Ω GCPW (0.27 / 0.15 mm), tapered from the 300 µm pad.
- **GND1–GND4** (A2, B1–B3): pads 200 µm on a 500 × 587 µm grid, each with its own via to L2. The top pour stays
  about 0.3–0.6 mm away from the IN and OUT pads (rf-layout §3).
- The direction mark (IN toward the MCU) is on the silkscreen; the part is asymmetric (rf-layout §11 item 7).
- VDDRF (pin 33) and VSSRF (pin 32) are decoupled at the pin, each capacitor with its own via (rf-layout §5).

## Antenna

- **TI SWRA117D meandered IFA** (AE401), 15.2 × 5.7 mm, as an exact copy (KiCad `RF_Antenna:Texas_SWRA117D_2.4GHz_Left`).
  - The feed is pad 1; pad 2 is the shorting leg to GND.
  - The antenna stays under solder mask (rf-layout §2).
- **Top edge, centred above RF1** (feed at x 0, D-029). The MCU sits at the top centre, rotated so RF1 faces the
  antenna. RF1 → MLPF → pi → feed is one straight vertical run, with 6.8 mm from MLPF OUT to the feed.
- **Keep-out on all four layers:** a **full-width band** from the GND edge (z 111.1) to the top edge (z 117.5). It holds no
  copper, traces, parts, screws or silkscreen (rule areas `ANTENNA_KEEPOUT` and `ANTENNA_BASE`; rf-layout §4).
  This mirrors SWRA117D's own board, where the antenna sits at the board end with ground below it only.
  - The radiating trace stays ≥ 0.5 mm and the shorting leg ≥ 1.0 mm from the board edge (AN1088).
- **Ground plane:** the rest of the 85 × 130 mm board, ≫ λ/4 (rf-layout §4).
- **Board thickness:** SWRA117D does not state its reference board thickness, and says to shorten the antenna on a thicker
  board and lengthen it on a thinner one. The DNP pi network covers the mismatch; trimming covers any frequency shift (open item 3).
- **Near field:** no metal within about 5 mm of the keep-out.
  - The bumper screws (MH1 at the top-left, MH2 on the right edge) are ≥ 18 mm from the band.
  - The NFC coil's copper (`docs/nfc.md`) stays 5 mm below the band and 13 mm sideways from the antenna's end.
  - The battery is on the back, top edge at z 75, 36 mm below the band (`docs/mechanical.md`).
  - The STDC14 cable (right edge) and the motor and encoder leads (side edges, low) don't cross it.

## Tuning and test footprints

- **Pi network at the feed** (rf-layout §3):
  - shunt C401 (DNP);
  - series R401 0 Ω (fitted);
  - shunt C402 (DNP);
  - all 0402 C0G, on the GCPW, each shunt with ≥ 2 vias to L2.
- **Conducted test port:**
  - DNP U.FL (J401) on a DNP 0 Ω (R402) whose pad sits on the RF_50 line, so the stub is the pad alone;
  - all layers clear under the U.FL (rf-layout §4);
  - fit R402 and remove R401 for conducted tests.
- **VNA tuning** in the final assembly (battery, motors, wheels fitted, no enclosure), per rf-layout §3. Target SWR ≤ 2
  across 2400–2483.5 MHz.

## Supplies, clocks and noise near the radio

- **STM32WB SMPS:**
  - the 10 µH + 10 nH inductors and the VDDSMPS capacitor sit at pins 41–44;
  - small copper area, return over solid L2, inductor orthogonal to the RF line (rf-layout §5).
- **Buck:** TPS62933F (1.2 MHz) sits mid-left (z ≈ 60), about 50 mm from the antenna (rf-layout §5).
- **HSE 32 MHz:** harmonics at 2432 and 2464 MHz fall in band (rf-layout §6), as on every STM32WB design. Keep the crystal at
  pins 34/35 with a short, symmetric loop, ground straight to L2 and no GPIO nearby. HSETUNE is set per batch
  (`docs/firmware-interface.md`).
- **Stitching:** GND vias about every 5 mm along the board edges and around the RF section. Inside the RF section, use
  the 1.0–1.3 mm fence pitch.

## Open items

1. Check this document against ST AN5165 (RF hardware for STM32WB) and AN2867 (oscillators) once they can be read.
2. Confirm 0.27 / 0.15 mm with JLC's impedance calculator for JLC04161H-7628 and enable impedance control on the order.
3. VNA-tune the pi network on the assembled robot. If resonance is off by more than the pi can fix, trim the antenna.
