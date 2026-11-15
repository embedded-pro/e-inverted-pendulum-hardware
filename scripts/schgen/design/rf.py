"""Sheet 4: RF path copied from ST's NUCLEO-WB55 board, MB1355 rev D-01 (D-037).

RF1 -> MLPF-WB55-01E3 -> R401 0R -> antenna match (C401 NF shunt, L401 3.6 nH series, C402 1.2 pF shunt) ->
printed meander antenna. MB1355's SMA branch (R13, C39, L4, C40, J2) is left out: PCB antenna only (D-038).
Values, parts and land patterns are ST's (MB1355 D-01 schematic sheet 3 and BOM); the copper is placed by
scripts/pcb/rf_block.py from scripts/pcb/mb1355_rf.json. Derived from STMicroelectronics MB1355 rev D-01
(Open Platform License, www.st.com/opla). Sources: docs/rf.md, DS12804 (MLPF).
"""

from parts import C, R, nobom
from sch import Sheet

FP = "e-inverted-pendulum:MB1355_"


def not_fitted_cap(sh, ref, x, y, net, purpose):
    part = sh.part("Device:C", ref, "NF", (x, y), fp=FP + "0402_CAP_NPOL", dnp=True, Purpose=purpose)
    sh.net(part["1"], net)
    sh.net(part["2"], "GND")
    return part


def build(project, values):
    sh = Sheet(project, 4, "rf", "2.4 GHz RF path and antenna")
    sh.desc = ["Copied from ST NUCLEO-WB55 MB1355 D-01 (D-037)", "RF1 -> MLPF-WB55-01E3 -> 0R",
               "3.6 nH + 1.2 pF match -> meander antenna", "PCB antenna only, no SMA (D-038)"]

    sh.box(15.24, 20.32, 182.88, 116.84, "2.4 GHz RF path: copy of MB1355 rev D-01 sheet 3 (D-037, docs/rf.md)")
    fl = sh.part("e-inverted-pendulum:MLPF-WB55-01E3", "FL401", "MLPF-WB55-01E3", (60.96, 66.04),
                 fp=FP + "ST_CSP650x58P2x3_160x100x42", lcsc="C2651048", mpn="MLPF-WB55-01E3",
                 Purpose="MB1355 U12: IPD = match + low-pass filter (DS12804)")
    fl.fpos = (-12.7, -12.7, "left")
    r401 = R(sh, "R401", "0", 93.98, 60.96, "RF_50", "RF_MATCH", rot=90, package="0402", fp=FP + "0402_RES",
             purpose="MB1355 R5: 0R in the antenna path, kept as ST laid it out (its SMA alternative is removed, D-038)")
    c401 = not_fitted_cap(sh, "C401", 109.22, 66.04, "RF_MATCH", "MB1355 C36: antenna match shunt, not fitted")
    l401 = sh.part("Device:L", "L401", "3.6nH", (124.46, 60.96), 90, fp=FP + "0402_COIL", lcsc="C19216",
                   mpn="LQG15HS3N6S02D", Purpose="MB1355 L3: antenna match series 3.6 nH +/-0.3 nH")
    l401.fpos = (-3.81, -3.81, "left")
    c402 = C(sh, "C402", "1.2p_0402_50V_C0G", 139.7, 66.04, "RF_ANT", "GND", fp=FP + "0402_CAP_NPOL",
             purpose="MB1355 C37: antenna match shunt 1.2 pF")
    ae = nobom(sh, "AE401", "Device:Antenna", "Meander antenna", FP + "Meander_Antenna", 157.48, 55.88,
               purpose="MB1355 printed meander antenna (ST AN3359 type) on the ground-free tab")
    ae.fpos = (5.08, -5.08, "left")

    sh.rail("RF1", 60.96, [fl["A3"]], label="left", ext=7.62)
    sh.vrail("GND", 45.72, [fl["B3"], fl["B2"]], tap=(73.66, (0, 1)))
    sh.vrail("GND", 76.2, [fl["B1"], fl["A2"]], tap=(73.66, (0, 1)))
    sh.rail("RF_50", 60.96, [fl["A1"], r401["1"]])
    sh.rail("RF_MATCH", 60.96, [r401["2"], c401["1"], l401["1"]])
    sh.rail("RF_ANT", 60.96, [l401["2"], c402["1"], ae["1"]])
    sh.note(20.32, 86.36, [
        "Copy of ST NUCLEO-WB55 (MB1355 rev D-01): values, parts and land patterns as ST's; the copper, the L2 cut-out",
        "under the line (it references L3) and the ground-free antenna tab come from scripts/pcb/mb1355_rf.json.",
        "PCB antenna only: MB1355's SMA branch (R13, C39, L4, C40, J2) is left out (D-038).",
        "C401 not fitted, as on MB1355; tune C401 / C402 with a VNA if the robot detunes the antenna.",
        "Derived from STMicroelectronics MB1355 rev D-01, Open Platform License (www.st.com/opla)."])
    return sh
