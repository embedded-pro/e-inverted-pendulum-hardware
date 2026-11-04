"""Sheet 2: 5V0 buck (TPS62933F) and 3V3 LDO (TLV75533P).

Sources: docs/design-calcs.md (TPS62933F, TLV75533P) from TI SLUSEA4 / SBVS320A.
"""

from parts import C, R, active, flag
from schematic import Part, Sheet


def build(values):
    b = values["buck"]
    sheet = Sheet(2, "logic_power", "5V0 buck and 3V3 LDO")
    active(sheet, "TPS62933FDRLR", "Regulator_Switching:TPS62933",
           {"1": "GND", "2": "BUCK_EN", "3": "VBAT", "4": "GND", "5": "BUCK_SW", "6": "BUCK_BST", "7": "BUCK_SS",
            "8": "BUCK_FB"}, "Package_TO_SOT_SMD:SOT-583-8", "U", value="TPS62933F",
           purpose="RT to GND = 1.2 MHz, forced PWM")
    R(sheet, b["en_r1"], "VBAT", "BUCK_EN", purpose="EN UVLO top: start ~9.1 V, stop ~8.5 V")
    R(sheet, b["en_r2"], "BUCK_EN", "GND", purpose="EN UVLO bottom")
    C(sheet, "10u_0805_25V_X5R", "VBAT", "GND", purpose="C_IN")
    C(sheet, "10u_0805_25V_X5R", "VBAT", "GND", purpose="C_IN")
    C(sheet, "100n_0603_50V_X7R", "VBAT", "GND", purpose="C_IN HF at the VIN pin")
    C(sheet, "100n_0402_16V_X7R", "BUCK_BST", "BUCK_SW", purpose="C_BST")
    C(sheet, "47n_0603_50V_X7R", "BUCK_SS", "GND", purpose="soft start 6.8 ms")
    active(sheet, "SWPA4030S4R7MT", "Device:L", {"1": "BUCK_SW", "2": "+5V"},
           "Inductor_SMD:L_Sunlord_SWPA4030S", "L", value="4.7uH", purpose="buck inductor")
    R(sheet, b["rfbt"], "+5V", "BUCK_FB", purpose="R_FBT")
    R(sheet, b["rfbb"], "BUCK_FB", "GND", purpose="R_FBB")
    C(sheet, "22u_0805_25V_X5R", "+5V", "GND", purpose="C_OUT")
    C(sheet, "22u_0805_25V_X5R", "+5V", "GND", purpose="C_OUT")
    C(sheet, "100n_0603_50V_X7R", "+5V", "GND", purpose="C_OUT HF")
    active(sheet, "TLV75533PDBVR", "Regulator_Linear:TLV75533PDBV",
           {"1": "+5V", "2": "GND", "3": "+5V", "4": None, "5": "+3V3"}, "Package_TO_SOT_SMD:SOT-23-5", "U",
           value="TLV75533P", purpose="3V3, 500 mA")
    C(sheet, "1u_0603_50V_X5R", "+5V", "GND", purpose="LDO C_IN")
    C(sheet, "2.2u_0603_25V_X5R", "+3V3", "GND", purpose="LDO C_OUT")
    flag(sheet, "+5V")
    return sheet
