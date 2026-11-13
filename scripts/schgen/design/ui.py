"""Sheet 8: LEDs, user button, buzzer, Qwiic I2C, I2C EEPROM, NFC tag, test points.

Sources: docs/design-calcs.md (LEDs, Buzzer, Button, Qwiic); MLT-8530 p.3; SLVA689A;
M24C64 DocID16891 Rev 33 (Fig. 2, s2.3-2.4); ST25DV04KC DS13519 Rev 6 (Table 1, Fig. 2); docs/nfc.md.
"""

from parts import C, R, active, nobom
from sch import Sheet

LED = "LED_SMD:LED_0603_1608Metric"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"


def leds(sh):
    sh.box(15.24, 20.32, 127.0, 96.52, "Status LEDs")
    rows = (("R801", "470", "LED_GREEN", "LED_G_A", "D801", "KT-0603G", "green", "status (PB0)", "green ~1.8 mA", 43.18),
            ("R802", "680", "LED_RED", "LED_R_A", "D802", "KT-0603R", "red", "fault (PB1)", "red ~2.1 mA", 60.96))
    cathodes = []
    for r_ref, r_val, net, anode, d_ref, mpn, colour, d_purpose, r_purpose, y in rows:
        r = R(sh, r_ref, r_val, 50.8, y, net, anode, rot=90, purpose=r_purpose)
        d = active(sh, d_ref, mpn, "Device:LED", LED, 71.12, y, 180, value=colour, purpose=d_purpose)
        sh.nets(d, {"1": "GND", "2": anode})
        sh.rail(net, y, [r["1"]], label="left", ext=7.62)
        sh.link(r["2"], d["2"], anode)
        cathodes.append(d["1"])
    sh.vrail("GND", 81.28, cathodes, tap=(66.04, (0, 1)))
    sh.note(20.32, 78.74, [
        "Green 470 Ohm: ~1.8 mA (V_F 2.45 V at 2 mA).",
        "Red 680 Ohm: ~2.1 mA (V_F 1.88 V at 2 mA).",
        "KT-0603 IF-VF curve p.5."])


def button(sh, values):
    sh.box(132.08, 20.32, 248.92, 96.52, "User button (PD0, EXTI0)")
    r803 = R(sh, "R803", "10k", 152.4, 40.64, "+3V3", "BTN_RAW", purpose="button pull-up")
    sw = sh.part("Switch:SW_Push", "SW801", "USER", (152.4, 60.96), 270, fp=values["tact_footprint"], lcsc="C318884",
                 mpn="TS-1187A-B-A-B", Purpose="arm/disarm")
    sw.fpos = (-3.81, -1.27, "right")
    r804 = R(sh, "R804", "100", 172.72, 48.26, "BTN_RAW", "BTN_USER", rot=90, purpose="button series R")
    c801 = C(sh, "C801", "100n_0603_50V_X7R", 187.96, 52.07, "BTN_USER", "GND", purpose="debounce, tau 1 ms")
    sh.rail("BTN_RAW", 48.26, [r803["2"], sw["1"], r804["1"]])
    sh.rail("BTN_USER", 48.26, [r804["2"], c801["1"]], label="right", ext=10.16)
    sh.net(sw["2"], "GND")
    sh.note(137.16, 78.74, [
        "10k pull-up, 100 Ohm series, 100 nF at the MCU:",
        "tau 1 ms (mcu-circuit-design s11).  Arm / disarm."])


def buzzer(sh):
    sh.box(254.0, 20.32, 405.13, 96.52, "Buzzer (PA7, TIM17_CH1)")
    r805 = R(sh, "R805", "33", 304.8, 38.1, "+5V", "BUZ_P", purpose="limits the 16 ohm coil to ~96 mA")
    bz = active(sh, "BZ801", "MLT-8530", "Device:Buzzer", "e-inverted-pendulum:Buzzer_MLT-8530_8.5x8.5mm",
                314.96, 50.8, value="MLT-8530", purpose="2.7 kHz transducer")
    flyback = active(sh, "D803", "1N4148WS", "Device:D", "Diode_SMD:D_SOD-323", 292.1, 52.07, 270, purpose="coil flyback")
    flyback.fpos = (-2.54, -1.27, "right")
    q = active(sh, "Q801", "MMBT3904", "Transistor_BJT:MMBT3904", "Package_TO_SOT_SMD:SOT-23", 302.26, 68.58,
               purpose="buzzer low-side switch")
    rb = R(sh, "R806", "470", 284.48, 68.58, "BUZZER_PWM", "BUZ_B", rot=90, purpose="base R per MLT-8530 p.3")
    rpd = R(sh, "R807", "10k", 292.1, 72.39, "BUZ_B", "GND", purpose="off while the MCU is in reset")
    sh.nets(bz, {"1": "BUZ_P", "2": "BUZ_N"})
    sh.nets(flyback, {"1": "BUZ_P", "2": "BUZ_N"})
    sh.nets(q, {"1": "BUZ_B", "2": "GND", "3": "BUZ_N"})
    sh.rail("BUZ_P", 48.26, [flyback["1"], r805["2"], bz["1"]])
    sh.rail("BUZ_N", 55.88, [flyback["2"], q["3"], bz["2"]])
    sh.rail("BUZ_B", 68.58, [rb["2"], rpd["1"], q["1"]])
    sh.rail("BUZZER_PWM", 68.58, [rb["1"]], label="left", ext=7.62)
    sh.note(330.2, 40.64, [
        "+5V -> 33 Ohm -> MLT-8530 (16 Ohm):",
        "peak ~96 mA (rated 95 mA max).",
        "470 Ohm base, 1N4148WS across the coil",
        "(MLT-8530 p.3).  R807 holds Q801 off",
        "while the MCU is in reset.  2.7 kHz."])


def qwiic_eeprom(sh):
    sh.box(15.24, 101.6, 205.74, 198.12, "Qwiic I2C3 expansion and EEPROM (PB10 SCL, PB11 SDA)")
    j = sh.part("Connector_Generic_MountingPin:Conn_01x04_MountingPin", "J801", "Qwiic", (27.94, 129.54), mirror="y",
                fp="Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", lcsc="C160404",
                mpn="SM04B-SRSS-TB(LF)(SN)", Purpose="I2C3 expansion (Qwiic pinout)")
    j.fpos = (-5.08, -7.62, "left")
    sh.nets(j, {"1": "GND", "2": "+3V3", "MP": "GND"})
    r808 = R(sh, "R808", "2.2k", 55.88, 123.19, "QWIIC_SDA", "+3V3", rot=180,
             purpose="I2C pull-up (SLVA689A window 967-3541 ohm)")
    r809 = R(sh, "R809", "2.2k", 68.58, 123.19, "QWIIC_SCL", "+3V3", rot=180, purpose="I2C pull-up")
    sh.rail("+3V3", 116.84, [r808["2"], r809["2"]], tap=(76.2, (0, -1)))
    sh.rail("QWIIC_SDA", 132.08, [j["3"], r808["1"]], label="right", ext=25.4)
    sh.rail("QWIIC_SCL", 134.62, [j["4"], r809["1"]], label="right", ext=12.7)
    esd = active(sh, "U801", "TPD4E05U06DQAR", "Power_Protection:TPD4E05U06DQA", "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
                 53.34, 157.48, purpose="Qwiic ESD")
    esd.fpos = (-12.7, -13.97, "left")
    sh.nets(esd, {"1": "QWIIC_SDA", "2": "QWIIC_SCL", "4": "+3V3", "5": None, "3": "GND", "8": "GND",
                  "6": None, "7": None, "9": None, "10": None})

    ee = active(sh, "U802", "M24C64-RMN6TP", "Memory_EEPROM:24LC64", SOIC8, 147.32, 137.16, value="M24C64-RMN6TP",
                purpose="I2C EEPROM 64 Kbit at 0x50: E2..E0 low, WC low = writes enabled (D-031)")
    ee.fpos = (-10.16, -12.7, "left")
    c802 = C(sh, "C802", "100n_0402_16V_X7R", 185.42, 137.16, "+3V3", "GND", purpose="EEPROM bypass")
    sh.nets(ee, {"5": "QWIIC_SDA", "6": "QWIIC_SCL"})
    sh.rail("+3V3", 124.46, [ee["8"], c802["1"]], tap=(172.72, (0, -1)))
    sh.vrail("GND", 134.62, [ee["1"], ee["2"], ee["3"], (134.62, 152.4)])
    sh.path("GND", [ee["7"], (162.56, 139.7), (162.56, 152.4)])
    sh.rail("GND", 152.4, [(134.62, 152.4), ee["4"], (162.56, 152.4), c802["2"]], tap=(172.72, (0, 1)))
    sh.note(20.32, 182.88, [
        "Qwiic pinout: 1 GND, 2 3V3, 3 SDA, 4 SCL.  2.2k pull-ups: window 967-3541 Ohm, Fast mode, C_b 100 pF (SLVA689A).",
        "U801 ESD at the connector.  U802 M24C64-R at 0x50: E2..E0 low, WC low = writes enabled (D-031)."])


def nfc(sh):
    sh.box(210.82, 101.6, 405.13, 198.12, "NFC tag: ST25DV04KC + printed 13.56 MHz coil (D-030)")
    tag = active(sh, "U803", "ST25DV04KC-IE8S3", "e-inverted-pendulum:ST25DV04KC-IE8S3", SOIC8, 325.12, 147.32,
                 purpose="NFC Type 5 tag on I2C3 (0x53/0x57); V_EH unused; GPO to PA2 (D-030)")
    tag.fpos = (2.54, -13.97, "left")
    coil = nobom(sh, "AE801", "e-inverted-pendulum:NFC_Coil", "NFC coil", "e-inverted-pendulum:NFC_Coil_25x21mm",
                 271.78, 147.32, 270, purpose="13.56 MHz printed loop, 10 turns, 25 x 21 mm (docs/nfc.md)")
    coil.fpos = (-3.81, -1.27, "right")
    trim = C(sh, "C804", "2.7p_0402_50V_C0G", 287.02, 147.32, "NFC_AC0", "NFC_AC1", dnp=True,
             purpose="coil trim: f0 14.2 -> 13.56 MHz needs about 2.9 pF (scripts/nfc_coil.py); fit after a phone/VNA check")
    c803 = C(sh, "C803", "100n_0402_16V_X7R", 322.58, 127.0, "+3V3", "GND", purpose="NFC tag bypass")
    gpo = R(sh, "R810", "10k", 365.76, 135.89, "NFC_GPO", "+3V3", rot=180, purpose="GPO is open drain (DS13519 Fig. 2)")
    sh.nc(tag["1"])
    sh.nets(tag, {"5": "QWIIC_SDA", "6": "QWIIC_SCL"})
    sh.rail("NFC_AC0", 134.62, [coil["1"], trim["1"], (302.26, 134.62)])
    sh.path("NFC_AC0", [tag["2"], (302.26, 147.32), (302.26, 134.62)])
    sh.rail("NFC_AC1", 160.02, [coil["2"], trim["2"], (299.72, 160.02)])
    sh.path("NFC_AC1", [tag["3"], (299.72, 149.86), (299.72, 160.02)])
    sh.path("+3V3", [tag["8"], (309.88, 139.7), (309.88, 121.92)])
    sh.rail("+3V3", 121.92, [(309.88, 121.92), c803["1"]], tap=(316.23, (0, -1)))
    sh.net(c803["2"], "GND")
    sh.path("GND", [tag["4"], (309.88, 154.94), (309.88, 165.1)])
    sh.rail("GND", 165.1, [(309.88, 165.1)], tap=(309.88, (0, 1)))
    sh.rail("NFC_GPO", 147.32, [tag["7"], gpo["1"]], label="right", ext=5.08)
    sh.net(gpo["2"], "+3V3")
    sh.note(215.9, 175.26, [
        "ST25DV04KC: ISO 15693 / NFC Type 5 tag on I2C3 (0x53 user, 0x57 system); V_EH unused; GPO open drain -> PA2 (EXTI2).",
        "AE801: 10 turns, 25 x 21 mm, 4.25 uH; f0 14.2 MHz with C_TUN 28.5 pF + 1 pF (scripts/nfc_coil.py, docs/nfc.md).",
        "C804 2.7 pF DNP across AC0-AC1 trims f0 to 13.56 MHz: fit after a phone / VNA check.  Keep metal off the coil."])


def test_points(sh):
    sh.box(15.24, 203.2, 205.74, 246.38, "Bring-up test points")
    for i, (ref, net) in enumerate((("TP801", "VBAT"), ("TP802", "+5V"), ("TP803", "+3V3"), ("TP804", "GND"),
                                    ("TP805", "GND"))):
        up = net != "GND"
        tp = nobom(sh, ref, "Connector:TestPoint", net, "TestPoint:TestPoint_Pad_D1.0mm", 33.02 + 25.4 * i,
                   223.52 if up else 220.98, 180 if up else 0, purpose="bring-up probe point")
        tp.fpos = (2.54, 2.54 if up else -3.81, "left")
        sh.net(tp["1"], net)


def build(project, values):
    sh = Sheet(project, 8, "ui", "User interface, expansion, test points")
    sh.desc = ["Status LEDs, user button, buzzer", "Qwiic I2C3 + ESD, M24C64 EEPROM",
               "ST25DV04KC NFC tag + printed coil", "Bring-up test points"]
    leds(sh)
    button(sh, values)
    buzzer(sh)
    qwiic_eeprom(sh)
    nfc(sh)
    test_points(sh)
    return sh
