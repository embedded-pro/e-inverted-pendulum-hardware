# Power map and net classes

Built per `power-pcb-layout` §2 before placement. The net classes in `kicad/e-inverted-pendulum.kicad_pro`
come from this table (`kicad/gen/board.py`, `NET_CLASSES`), not the other way round.

**Track widths:** IPC-2221, ΔT 10 °C, 1 oz outer / 0.5 oz inner (D-008), using the skill's `width_mm()`:
- 4.2 A (two MG310s at the 2.0 A trip plus logic, D-027): 2.17 mm outer, 11.3 mm inner;
- 2.0 A: 0.78 mm outer;
- 0.5 A: 0.12 mm outer.

**Vias:** about 1 A each (0.3 mm drill), so every layer change needs ≥ I/1 A vias. **Clearance:** everything is ≤ 30 V
(3S, TVS-clamped), so IPC-2221 B2 needs 0.1 mm. The fab design value of 0.15 mm governs. The bus and motor nets get 0.2 mm. The switch nodes keep 0.15 mm, because SMPS_LX sits on the MCU's 0.4 mm-pitch pins.

| Net / group | Kind | I cont / peak | V max | Rule | Class |
|---|---|---|---|---|---|
| BAT_P → F101 → BAT_F → Q101 → PP_S → VBAT | high current | 1.2 A / 4.2 A | 12.6 V (SMBJ15A clamp 24 V) | Pours on L1 + L3; ≥ 5 vias per layer change; no necks below 2.2 mm outer | `PWR_BUS` |
| VBAT at the bridges (HS drains; C502/C503 bridge A, C505/C506 bridge B, C507 bulk, C508 VM) | hot-loop member | 1.0 A / 4.0 A | 12.6 V | Pour on L1. The HF cap (100 nF) sits closest to each FET pair's drain and LS source; L2 GND directly under | `PWR_BUS` |
| MOT_L_P, MOT_L_N, MOT_R_P, MOT_R_N | switch node (25 kHz, IDRIVE 00) | 0.5 A / 2.0 A | 12.6 V | 0.8 mm. Only the copper the current needs, from the FET to the SS34 and the PH 6-pin connector (2 A contacts, D-028). No sense or encoder trace beside or under it on any layer | `MOTOR` |
| SENSE_A, SENSE_B (LS sources → Rsense) | hot-loop member | 0.5 A / 2.0 A | < 0.1 V | Short and wide (≥ 0.8 mm). The current flows straight through R509/R512 | `MOTOR` |
| xHS_D/G, xLS_D/G (8 + 8 nets), PP_G | gate drive | mA / ~100 mA pulses | VBAT + 12 V | 0.3 mm. Gate R at the FET. Each route paired with its return: the phase node for HS, SENSE_x/GND for LS | `GATE` |
| DRV_xISENP/N, KELVIN_xN | sense / Kelvin | µA | < 0.1 V | From the inner pad edges of Rsense (NT501/NT502 at the GND pad). Tight pair, filter at the DRV8711 | `SENSE` |
| VBAT_SENSE | analog, high impedance | µA | 2.7 V | Divider and 100 nF at the ADC pin (PC1); away from switch nodes | `SENSE` |
| BUCK_SW | switch node (1.2 MHz) | 0.5 A / 1 A | 12.6 V | Minimal copper U201 → L201; nothing under it on L3/L4; FB away from it | `SWITCH` |
| BUCK_BST, BUCK_FB, BUCK_SS, BUCK_EN | bootstrap / feedback | µA–mA | 12.6 V | BST cap at the pins; FB divider at the IC, sensing at the output cap | Default |
| SMPS_LX, SMPS_MID, VFBSMPS | MCU SMPS switch node (4 MHz) | 50 mA | 3.6 V | L301 + L302 at pins 41–44, small copper area, orthogonal to the RF line (`docs/rf.md`) | `SWITCH` |
| +5V | supply | 0.3 A / 0.6 A | 5.0 V | Pour on L3 or 0.5 mm | `SUPPLY` |
| +3V3, VDDA, ENC_VCC, DRV_V5, DRV_VINT, DRV_VCP | supply | ≤ 0.2 A | 3.3–24 V | 0.5 mm or a pour on L3; decoupling at each pin with its own via | `SUPPLY` |
| DRV_CP1, DRV_CP2 | charge-pump switch node | mA | 24 V | Flying cap at the pins, short | `GATE` |
| RF1, RF_50, RF_ANT, RF_UFL | RF 50 Ω | — | — | GCPW 0.27 / 0.15 mm (RF1 trace 0.2 / 0.104 mm per DS12804); L1 only, no vias; via fence 1.0–1.3 mm (`docs/rf.md`) | `RF` |
| HSE_IN/OUT, OSC32_IN/OUT | crystal | µA | 3.3 V | At the pins, short and symmetric, GND guard, no vias | `CRYSTAL` |
| ENC_* (raw, filtered, buffered) | off-board digital input | mA | 5 V | Away from MOT_* on every layer; ESD part at the connector, pass-through | Default |
| GND | plane | — | — | L2 solid and never cut; GND fill on L1/L4; stitching about every 5 mm | — |
| Everything else | digital | mA | 3.3 V | 0.2 mm, 0.15 mm clearance | Default |

| Class | Track (mm) | Clearance (mm) | Via (mm, drill / pad) | Diff pair (mm, width / gap) |
|---|---|---|---|---|
| Default | 0.20 | 0.15 | 0.30 / 0.60 | — |
| `PWR_BUS` | 2.20 | 0.20 | 0.30 / 0.60 | — |
| `MOTOR` | 0.80 | 0.20 | 0.30 / 0.60 | — |
| `GATE` | 0.30 | 0.15 | 0.30 / 0.60 | — |
| `SENSE` | 0.20 | 0.15 | 0.30 / 0.60 | 0.20 / 0.20 |
| `SWITCH` | 0.50 | 0.15 | 0.30 / 0.60 | — |
| `SUPPLY` | 0.50 | 0.15 | 0.30 / 0.60 | — |
| `RF` | 0.27 | 0.15 | — (no vias on the line) | — |
| `CRYSTAL` | 0.20 | 0.15 | — | — |

The RF1 matching trace (200 µm wide, 104 µm gap, 1.5 mm long, DS12804 Fig. 13) is below the class values. A custom
rule in `e-inverted-pendulum.kicad_dru` allows 0.10 mm clearance on RF1 only. That is above JLC's 0.09 mm floor.
