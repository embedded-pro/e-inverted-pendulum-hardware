"""Sheet 8: LEDs, user button, buzzer, Qwiic I2C, test points.

Sources: docs/design-calcs.md (LEDs, Buzzer, Button, Qwiic); MLT-8530 p.3; SLVA689A.
"""

from parts import C, R, active, nobom
from schematic import Part, Sheet


def build(values):
    sheet = Sheet(8, "ui", "User interface, expansion, test points")
    R(sheet, "470", "LED_GREEN", "LED_G_A", purpose="green ~1.8 mA")
    active(sheet, "KT-0603G", "Device:LED", {"1": "GND", "2": "LED_G_A"}, "LED_SMD:LED_0603_1608Metric", "D",
           value="green", purpose="status (PB0)")
    R(sheet, "680", "LED_RED", "LED_R_A", purpose="red ~2.1 mA")
    active(sheet, "KT-0603R", "Device:LED", {"1": "GND", "2": "LED_R_A"}, "LED_SMD:LED_0603_1608Metric", "D",
           value="red", purpose="fault (PB1)")
    R(sheet, "10k", "+3V3", "BTN_RAW", purpose="button pull-up")
    R(sheet, "100", "BTN_RAW", "BTN_USER", purpose="button series R")
    C(sheet, "100n_0603_50V_X7R", "BTN_USER", "GND", purpose="debounce, tau 1 ms")
    sheet.add(Part(sheet.next_ref("SW"), "Switch:SW_Push", "USER", {"1": "BTN_RAW", "2": "GND"},
                   footprint=values["tact_footprint"], lcsc="C318884", mpn="TS-1187A-B-A-B",
                   fields={"Purpose": "arm/disarm"}))
    R(sheet, "33", "+5V", "BUZ_P", purpose="limits the 16 ohm coil to ~96 mA")
    active(sheet, "MLT-8530", "Device:Buzzer", {"1": "BUZ_P", "2": "BUZ_N"},
           "e-inverted-pendulum:Buzzer_MLT-8530_8.5x8.5mm", "BZ", value="MLT-8530", purpose="2.7 kHz transducer")
    active(sheet, "1N4148WS", "Device:D", {"1": "BUZ_P", "2": "BUZ_N"}, "Diode_SMD:D_SOD-323", "D",
           purpose="coil flyback")
    active(sheet, "MMBT3904", "Transistor_BJT:MMBT3904", {"1": "BUZ_B", "2": "GND", "3": "BUZ_N"},
           "Package_TO_SOT_SMD:SOT-23", "Q", purpose="buzzer low-side switch")
    R(sheet, "470", "BUZZER_PWM", "BUZ_B", purpose="base R per MLT-8530 p.3")
    R(sheet, "10k", "BUZ_B", "GND", purpose="off while the MCU is in reset")
    sheet.add(Part(sheet.next_ref("J"), "Connector_Generic_MountingPin:Conn_01x04_MountingPin", "Qwiic",
                   {"1": "GND", "2": "+3V3", "3": "QWIIC_SDA", "4": "QWIIC_SCL", "MP": "GND"},
                   footprint="Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", lcsc="C160404",
                   mpn="SM04B-SRSS-TB(LF)(SN)", fields={"Purpose": "I2C3 expansion (Qwiic pinout)"}))
    active(sheet, "TPD4E05U06DQAR", "Power_Protection:TPD4E05U06DQA",
           {"1": "QWIIC_SDA", "2": "QWIIC_SCL", "4": "+3V3", "5": None, "3": "GND", "8": "GND",
            "6": None, "7": None, "9": None, "10": None},
           "Package_SON:USON-10_2.5x1.0mm_P0.5mm", "U", purpose="Qwiic ESD")
    R(sheet, "2.2k", "QWIIC_SDA", "+3V3", purpose="I2C pull-up (SLVA689A window 967-3541 ohm)")
    R(sheet, "2.2k", "QWIIC_SCL", "+3V3", purpose="I2C pull-up")
    for net in ("VBAT", "+5V", "+3V3", "GND", "GND"):
        nobom(sheet, "TP", "Connector:TestPoint", net, {"1": net}, "TestPoint:TestPoint_Pad_D1.0mm",
              purpose="bring-up probe point")
    return sheet
