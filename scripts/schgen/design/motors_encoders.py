"""Sheet 6: MG310 motor + encoder connectors and A/B encoder inputs (ESD -> RC -> Schmitt buffer), D-012, D-028.

One JST PH 6-pin per motor carries the motor and its Hall encoder (MG310 pinout: 1 M-, 2 encoder VCC, 3 A, 4 B,
5 GND, 6 M+). The MG310 has no index, so the buffer's third input is grounded and the index pins read low.
Sources: docs/design-calcs.md (Encoders), SCES470D (SN74LVC3G17), SLVSBO7L (TPD4E05U06), interface-layout s2.
"""

from parts import C, R, active
from schematic import Part, Sheet

SIDES = (("L", "left"), ("R", "right"))


def build(values):
    sheet = Sheet(6, "motors_encoders", "Motor connectors and encoder inputs")
    R(sheet, "0", "+5V", "ENC_SRC", purpose="encoder supply 5V0 (default, D-016)")
    R(sheet, "0", "+3V3", "ENC_SRC", dnp=True, purpose="encoder supply 3V3 option")
    active(sheet, "SMD0805P010TF", "Device:Polyfuse_Small", {"1": "ENC_SRC", "2": "ENC_VCC"},
           "Fuse:Fuse_0805_2012Metric", "F", value="PTC 100mA", purpose="shorted cable can't drop the rail")
    C(sheet, "10u_0603_10V_X5R", "ENC_VCC", "GND", purpose="encoder supply bulk")
    C(sheet, "100n_0603_50V_X7R", "ENC_VCC", "GND", purpose="encoder supply HF")
    for side, name in SIDES:
        sheet.add(Part(sheet.next_ref("J"), "Connector_Generic:Conn_01x06", f"Motor {name}",
                       {"1": f"MOT_{side}_N", "2": "ENC_VCC", "3": f"ENC_{side}_A_RAW", "4": f"ENC_{side}_B_RAW",
                        "5": "GND", "6": f"MOT_{side}_P"},
                       footprint="Connector_JST:JST_PH_S6B-PH-K_1x06_P2.00mm_Horizontal", lcsc="C157920",
                       mpn="S6B-PH-K-S(LF)(SN)",
                       fields={"Purpose": f"{name} MG310: 1 M-, 2 enc VCC, 3 A, 4 B, 5 GND, 6 M+ (D-028); 2 A contacts"}))
        C(sheet, "100n_0603_50V_X7R", f"MOT_{side}_P", f"MOT_{side}_N", dnp=True,
          purpose="optional motor-terminal suppression (fit at the motor preferably)")
        active(sheet, "TPD4E05U06DQAR", "Power_Protection:TPD4E05U06DQA",
               {"1": f"ENC_{side}_A_RAW", "2": f"ENC_{side}_B_RAW", "4": None, "5": "ENC_VCC",
                "3": "GND", "8": "GND", "6": None, "7": None, "9": None, "10": None},
               "Package_SON:USON-10_2.5x1.0mm_P0.5mm", "U", purpose="ESD at the connector, pass-through routing")
        for channel in ("A", "B"):
            raw, filtered = f"ENC_{side}_{channel}_RAW", f"ENC_{side}_{channel}_F"
            R(sheet, "2.2k", raw, "ENC_VCC", dnp=True, purpose="open-collector pull-up option")
            R(sheet, "100", raw, filtered, purpose="series R, f_c 1.59 MHz with 1 nF")
            C(sheet, "1n_0603_50V_X7R", filtered, "GND", purpose="input RC")
        active(sheet, "SN74LVC3G17DCTR", "74xGxx:74LVC3G17",
               {"1": f"ENC_{side}_A_F", "7": f"ENC_{side}_A", "6": f"ENC_{side}_B_F", "2": f"ENC_{side}_B",
                "3": "GND", "5": f"ENC_{side}_Z", "4": "GND", "8": "+3V3"},
               "Package_SO:SSOP-8_2.95x2.8mm_P0.65mm", "U",
               purpose="Schmitt buffer, I_off: 5 V inputs while 3V3 is off; 3rd input grounded (no index, D-028)")
        C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose="buffer bypass")
    return sheet
