# Power map and net classes

Built per `power-pcb-layout` §2 before placement. The net classes in `hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pro`
come from this table (`scripts/pcb/board.py`, `NET_CLASSES`), not the other way round. Since D-062 they are the
hardware-design plugin's standard classes (`pcb-copper` skill): the name says what sizes the class, `netclasses.py apply`
writes the values and `netclasses.py check` gates them. Every net with two or more pads has a class; `board.py` gives
an exact SIGNAL pattern to each net no other class covers.

**Track widths:** IPC-2221, ΔT 10 °C, 1 oz outer / 0.5 oz inner (D-008), using the skill's `width_mm()`:
- 4.2 A (two MG310s at the 2.0 A trip plus logic, D-027): 2.17 mm outer, 11.3 mm inner (IPC-2221 internal chart);
- 2.0 A: 0.78 mm outer;
- 0.5 A: 0.12 mm outer.

The class values (`netclasses.py size`, D-062) use the external-chart fit on every layer's own copper (35 µm outer,
15.2 µm inner, per IPC-2152's finding that inner layers run no hotter): 4.2 A 2.174 / 5.007 mm, 2 A 0.781 / 1.799 mm,
1 A 0.300 / 0.692 mm, 0.6 A 0.15 (design minimum) / 0.342 mm, 0.2 A 0.15 mm. The L3 VBAT corridor keeps its ≥ 11.3 mm
(D-056), above both.

**Vias:** about 1 A each (0.3 mm drill), so every layer change needs ≥ I/1 A vias. **Clearance:** everything is ≤ 30 V
(3S, TVS-clamped), so IPC-2221 B2 needs 0.1 mm. The fab design value of 0.15 mm governs, and every class uses it (D-062; until then the bus and motor classes had 0.2 mm, which the routers still keep from those nets). The switch nodes keep 0.15 mm, because SMPS_LX sits on the MCU's 0.4 mm-pitch pins.

| Net / group | Kind | I cont / peak | V max | Rule | Class |
|---|---|---|---|---|---|
| BAT_P → F101 → BAT_F → Q101 → PP_S → VBAT | high current | 1.2 A / 4.2 A | 12.6 V (SMBJ15A clamp 24 V) | Pours on L1 + L3; ≥ 5 vias per layer change; no necks below 2.2 mm outer. Done (D-056): VBAT on L3 as one ≥ 11.3 mm corridor, L1 pours at Q101 and the buck input with 5 + 2 vias; the entry hops (BAT_P, BAT_F, PP_S, < 6 mm) on L1 only, each ≥ 2.2 mm | `PWR_4.2A` |
| VBAT at the bridges (HS drains; C502/C503 bridge A, C505/C506 bridge B, C507 bulk, C508 / C514 VM) | hot-loop member | 1.0 A / 4.0 A | 12.6 V | TI's BOOST-DRV8711 VM pours on L1 / L4 (D-040, `docs/drive.md`); L2 GND directly under | `PWR_4.2A` |
| MOT_L_P, MOT_L_N, MOT_R_P, MOT_R_N | switch node (25 kHz, IDRIVE 00) | 0.5 A / 2.0 A | 12.6 V | 0.8 mm. Only the copper the current needs, from the FET to the SS34 and the PH 6-pin connector (2 A contacts, D-028). No sense or encoder trace beside or under it on any layer Done (D-060): each motor's pair on F.Cu at 0.8 mm across the top of the bracket strip, two vias where it crosses the connector's pins | `PWR_2A` |
| SENSE_A, SENSE_B (LS sources → Rsense) | hot-loop member | 0.5 A / 2.0 A | < 0.1 V | TI's GND_A / GND_B pours; the current flows straight through R509/R512 (D-040) | `PWR_2A` |
| A1HS … B2LS (8 nets), PP_G | gate drive | mA / ~100 mA pulses | VBAT + 12 V | TI's gate traces, straight from the DRV8711 (no series R, D-040); PP_G 0.3 mm | `SIGNAL` |
| DRV_xISENP/N | sense / Kelvin | µA | < 0.1 V | TI's net ties at the shunt pads (NT501 / NT502 SENSE side, NT503 / NT504 GND side, on B.Cu, D-040) | `SENSE` |
| VBAT_SENSE | analog, high impedance | µA | 2.7 V | Divider and 100 nF at the ADC pin (PC1); away from switch nodes | `ANALOG` |
| BUCK_SW | switch node (1.2 MHz) | 0.5 A / 1 A | 12.6 V | Minimal copper U201 → L201; nothing under it on L3/L4; FB away from it | `PWR_1A` |
| BUCK_BST, BUCK_FB, BUCK_SS, BUCK_EN | bootstrap / feedback | µA–mA | 12.6 V | BST cap at the pins; FB divider at the IC, sensing at the output cap | `SIGNAL` |
| SMPS_LX, SMPS_MID (VFBSMPS: `SIGNAL`) | MCU SMPS switch node (4 MHz) | 50 mA | 3.6 V | L301 + L302 at pins 41–44, small copper area, orthogonal to the RF line (`docs/rf.md`) | `PWR_0.2A` |
| +5V | supply | 0.3 A / 0.6 A | 5.0 V | Pour on L3 or 0.5 mm | `PWR_0.6A` |
| +3V3, VDDA, ENC_VCC, DRV_V5, DRV_VINT, DRV_VCP | supply | ≤ 0.2 A | 3.3–24 V | 0.5 mm or a pour on L3; decoupling at each pin with its own via | `PWR_0.2A` |
| DRV_CP1, DRV_CP2 | charge-pump switch node | mA | 24 V | Flying cap at the pins, short | `SIGNAL` |
| RF1, RF_50, RF_MATCH, RF_ANT | RF (MB1355 copy) | — | — | MB1355's 0.6 mm L1 line, 0.2 mm gaps, referenced to L3 (L2 cut out); RF1 fan-out 0.265 mm (`docs/rf.md`, D-037) | `RF_50` |
| HSE_IN/OUT, OSC32_IN/OUT | crystal | µA | 3.3 V | At the pins, short and symmetric, GND guard, no vias | `CLK` |
| ENC_* (raw, filtered, buffered) | off-board digital input | mA | 5 V | Away from MOT_* on every layer; ESD part at the connector, pass-through | `SIGNAL` |
| GND | plane | — | — | L2 solid and never cut; L3 GND outside the VBAT corridor (D-056); GND fill on L1/L4; stitching about every 5 mm | `GND` |
| Everything else | digital | mA | 3.3 V | 0.15 mm, 0.15 mm clearance | `SIGNAL` |

| Class | Track outer / inner (mm) | Clearance (mm) | Via (mm, drill / pad) | Note |
|---|---|---|---|---|
| `PWR_4.2A` | 2.174 / 5.007 | 0.15 | 0.30 / 0.60 | a pour (≥ the 3 A width on 1 oz); ≥ 5 vias per layer change |
| `PWR_2A` | 0.781 / 1.799 | 0.15 | 0.30 / 0.60 | ≥ 2 vias per layer change |
| `PWR_1A` | 0.300 / 0.692 | 0.15 | 0.30 / 0.60 | |
| `PWR_0.6A` | 0.15 / 0.342 | 0.15 | 0.30 / 0.60 | |
| `PWR_0.2A` | 0.15 | 0.15 | 0.30 / 0.60 | |
| `SENSE` | 0.15 | 0.15 | 0.30 / 0.60 | Kelvin pair, 0.20 / 0.20 diff pair |
| `ANALOG`, `CLK`, `GND`, `SIGNAL` | 0.15 | 0.15 | 0.30 / 0.60 | the fab's design values |
| `RF_50` | 0.6 (set by hand, MB1355) | 0.15 (the L1 fill keeps 0.2) | — (no vias on the line) | impedance class |

The scripts keep 0.2 mm from other copper to `PWR_4.2A`, `PWR_2A` and `RF_50` when they route (`maze.py`
`WIDE_CLASSES`), as for the old PWR_BUS / MOTOR / RF.

The RF1 matching trace (200 µm wide, 104 µm gap, 1.5 mm long, DS12804 Fig. 13) is below the class values. A custom
rule in `e-inverted-pendulum.kicad_dru` allows 0.104 mm clearance on RF1 only. That is above JLC's 0.09 mm floor.
