"""Sheet 8: LEDs, user button, buzzer, Qwiic I2C, I2C EEPROM, NFC tag, test points.

Sources: docs/design-calcs.md (LEDs, Buzzer, Button, Qwiic); MLT-8530 p.3; SLVA689A;
M24C64 DocID16891 Rev 33 (Fig. 2, s2.3-2.4); ST25DV04KC DS13519 Rev 6 (Table 1, Fig. 2); docs/nfc.md.
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
    active(sheet, "M24C64-RMN6TP", "Memory_EEPROM:24LC64",
           {"1": "GND", "2": "GND", "3": "GND", "4": "GND", "5": "QWIIC_SDA", "6": "QWIIC_SCL", "7": "GND", "8": "+3V3"},
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "U", value="M24C64-RMN6TP",
           purpose="I2C EEPROM 64 Kbit at 0x50: E2..E0 low, WC low = writes enabled (D-031)")
    C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose="EEPROM bypass")
    active(sheet, "ST25DV04KC-IE8S3", "e-inverted-pendulum:ST25DV04KC-IE8S3",
           {"1": None, "2": "NFC_AC0", "3": "NFC_AC1", "4": "GND", "5": "QWIIC_SDA", "6": "QWIIC_SCL",
            "7": "NFC_GPO", "8": "+3V3"},
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "U",
           purpose="NFC Type 5 tag on I2C3 (0x53/0x57); V_EH unused; GPO to PA2 (D-030)")
    C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose="NFC tag bypass")
    R(sheet, "10k", "NFC_GPO", "+3V3", purpose="GPO is open drain (DS13519 Fig. 2)")
    C(sheet, "2.7p_0402_50V_C0G", "NFC_AC0", "NFC_AC1", dnp=True,
      purpose="coil trim: f0 14.2 -> 13.56 MHz needs about 2.9 pF (scripts/nfc_coil.py); fit after a phone/VNA check")
    nobom(sheet, "AE", "e-inverted-pendulum:NFC_Coil", "NFC coil", {"1": "NFC_AC0", "2": "NFC_AC1"},
          "e-inverted-pendulum:NFC_Coil_25x21mm", purpose="13.56 MHz printed loop, 10 turns, 25 x 21 mm (docs/nfc.md)")
    for net in ("VBAT", "+5V", "+3V3", "GND", "GND"):
        nobom(sheet, "TP", "Connector:TestPoint", net, {"1": net}, "TestPoint:TestPoint_Pad_D1.0mm",
              purpose="bring-up probe point")
    return sheet
