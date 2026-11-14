"""Sheet 2: 5V0 buck (TPS62933F) and 3V3 LDO (TLV75533P).

Sources: docs/design-calcs.md (TPS62933F, TLV75533P) from TI SLUSEA4 / SBVS320A.
"""

from parts import C, R, active, test_points
from sch import Sheet


def build(project, values):
    b = values["buck"]
    sh = Sheet(project, 2, "logic_power", "5V0 buck and 3V3 LDO")
    sh.desc = ["TPS62933F buck VBAT -> +5V, 1.2 MHz", "EN UVLO: start 9.1 V, stop 8.5 V", "TLV75533P LDO +5V -> +3V3, 500 mA"]

    sh.box(15.24, 20.32, 233.68, 129.54, "5V0 buck (TPS62933F, 1.2 MHz, forced PWM)")
    u = active(sh, "U201", "TPS62933FDRLR", "Regulator_Switching:TPS62933", "Package_TO_SOT_SMD:SOT-583-8",
               114.3, 66.04, value="TPS62933F", purpose="RT to GND = 1.2 MHz, forced PWM")
    u.fpos = (-7.62, -13.97, "left")
    cin = [C(sh, "C201", "10u_0805_25V_X5R", 30.48, 55.88, "VBAT", "GND", purpose="C_IN"),
           C(sh, "C202", "10u_0805_25V_X5R", 45.72, 55.88, "VBAT", "GND", purpose="C_IN"),
           C(sh, "C203", "100n_0603_50V_X7R", 60.96, 55.88, "VBAT", "GND", purpose="C_IN HF at the VIN pin")]
    r201 = R(sh, "R201", b["en_r1"], 76.2, 53.34, "VBAT", "BUCK_EN", purpose="EN UVLO top: start ~9.1 V, stop ~8.5 V")
    r202 = R(sh, "R202", b["en_r2"], 76.2, 68.58, "BUCK_EN", "GND", purpose="EN UVLO bottom")
    c205 = C(sh, "C205", "47n_0603_50V_X7R", 88.9, 72.39, "BUCK_SS", "GND", purpose="soft start 6.8 ms")
    c204 = C(sh, "C204", "100n_0402_16V_X7R", 129.54, 62.23, "BUCK_BST", "BUCK_SW", purpose="C_BST")
    lout = active(sh, "L201", "SWPA4030S4R7MT", "Device:L", "Inductor_SMD:L_Sunlord_SWPA4030S", 149.86, 66.04, 90,
                  value="4.7uH", purpose="buck inductor")
    r203 = R(sh, "R203", b["rfbt"], 162.56, 72.39, "+5V", "BUCK_FB", purpose="R_FBT")
    r204 = R(sh, "R204", b["rfbb"], 162.56, 87.63, "BUCK_FB", "GND", purpose="R_FBB")
    cout = [C(sh, "C206", "22u_0805_25V_X5R", 177.8, 72.39, "+5V", "GND", purpose="C_OUT"),
            C(sh, "C207", "22u_0805_25V_X5R", 193.04, 72.39, "+5V", "GND", purpose="C_OUT"),
            C(sh, "C208", "100n_0603_50V_X7R", 208.28, 72.39, "+5V", "GND", purpose="C_OUT HF")]
    f5 = sh.flag("+5V", (220.98, 66.04), label=False)

    sh.rail("VBAT", 48.26, [c["1"] for c in cin] + [r201["1"], (101.6, 48.26)], label="left")
    sh.path("VBAT", [u["3"], (101.6, 58.42), (101.6, 48.26)])
    sh.rail("GND", 63.5, [c["2"] for c in cin], tap=(53.34, (0, 1)))
    sh.rail("BUCK_EN", 60.96, [r201["2"], r202["1"], u["2"]])
    sh.link(c205["1"], u["7"], "BUCK_SS")
    sh.path("GND", [u["1"], (104.14, 71.12), (104.14, 96.52)])
    sh.link(u["6"], c204["1"], "BUCK_BST")
    sh.rail("BUCK_SW", 66.04, [u["5"], c204["2"], lout["1"]])
    sh.rail("+5V", 66.04, [lout["2"], r203["1"]] + [c["1"] for c in cout] + [f5["1"]], tap=(226.06, (0, -1)))
    sh.path("BUCK_FB", [u["8"], (139.7, 73.66), (139.7, 80.01)])
    sh.rail("BUCK_FB", 80.01, [(139.7, 80.01), r203["2"], r204["1"]])
    sh.rail("GND", 96.52, [r202["2"], c205["2"], (104.14, 96.52), u["4"], r204["2"]] + [c["2"] for c in cout],
            tap=(149.86, (0, 1)))
    sh.note(20.32, 104.14, [
        "VOUT = 0.8 V x (1 + 52.3k / 10k) = 4.98 V (4.88-5.08 V over the V_FB tolerance); RT to GND sets 1.2 MHz.",
        "L201 4.7 uH (I_sat 3.2 A): ripple 0.39 A at 9 V, 0.53 A at 12.6 V.  C_OUT 2 x 22 uF + 100 nF (~22 uF at 5 V).",
        "EN UVLO R201 / R202: start 9.11 V, stop 8.47 V (~2.8 V per cell protects the pack).  C205 47 nF: t_SS 6.8 ms.",
        "Layout: C203 at the VIN pin; minimal BUCK_SW copper, nothing under it on L3/L4; FB divider at the IC,",
        "sensing at the output caps (docs/power-map.md)."])

    sh.box(238.76, 20.32, 340.36, 129.54, "3V3 LDO (TLV75533P)")
    ldo = active(sh, "U202", "TLV75533PDBVR", "Regulator_Linear:TLV75533PDBV", "Package_TO_SOT_SMD:SOT-23-5",
                 279.4, 68.58, value="TLV75533P", purpose="3V3, 500 mA")
    sh.nc(ldo["4"])
    c209 = C(sh, "C209", "1u_0603_50V_X5R", 259.08, 72.39, "+5V", "GND", purpose="LDO C_IN")
    c210 = C(sh, "C210", "2.2u_0603_25V_X5R", 302.26, 72.39, "+3V3", "GND", purpose="LDO C_OUT")
    sh.rail("+5V", 66.04, [c209["1"], ldo["1"]], tap=(248.92, (0, -1)))
    sh.link(ldo["3"], ldo["1"], "+5V")
    sh.rail("+3V3", 66.04, [ldo["5"], c210["1"]], tap=(314.96, (0, -1)))
    sh.rail("GND", 83.82, [c209["2"], ldo["2"], c210["2"]], tap=(289.56, (0, 1)))
    sh.note(243.84, 104.14, [
        "TLV75533P: 3.3 V, 500 mA, EN tied to IN.",
        "C_IN 1 uF, C_OUT 2.2 uF (>= 0.47 uF effective,",
        "SBVS320A s6.3, s8.1.1).",
        "0.20 W at 115 mA -> +45 C (R_thJA 231 C/W)."])

    sh.box(15.24, 134.62, 233.68, 175.26, "Test points")
    test_points(sh, 30.48, 162.56, [("TP201", "+5V"), ("TP202", "+3V3"), ("TP203", "GND")], pitch=25.4)
    return sh
