"""Sheet 8: status LED, addressable RGB LED chain, Qwiic I2C, I2C EEPROM, NFC tag, test points.

No buttons and no buzzer (D-035): the robot doubles as a toy and the RGB chain is its display.
Sources: docs/design-calcs.md (Status LED, RGB LEDs, Qwiic); WS2812B-2020-V6 datasheet; SCLS378L (SN74AHCT1G125);
SLVA689A; M24C64 DocID16891 Rev 33 (Fig. 2, s2.3-2.4); ST25DV04KC DS13519 Rev 6 (Table 1, Fig. 2); docs/nfc.md.
"""

from parts import C, R, active, nobom, test_points
from sch import Sheet

LED = "LED_SMD:LED_0603_1608Metric"
RGB = "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
RGB_COUNT = 12
RGB_PER_ROW = 6
DY = 27.94


def status_led(sh):
    sh.box(15.24, 20.32, 81.28, 124.46, "Status LED (PB0)")
    r = R(sh, "R801", "470", 43.18, 45.72, "LED_GREEN", "LED_G_A", rot=90, purpose="green ~1.8 mA")
    d = active(sh, "D801", "KT-0603G", "Device:LED", LED, 63.5, 45.72, 180, value="green", purpose="status (PB0)")
    sh.nets(d, {"1": "GND", "2": "LED_G_A"})
    sh.rail("LED_GREEN", 45.72, [r["1"]], label="left", ext=2.54)
    sh.link(r["2"], d["2"], "LED_G_A")
    sh.vrail("GND", 73.66, [d["1"]], tap=(50.8, (0, 1)))
    sh.note(20.32, 66.04, [
        "The firmware's statusLed",
        "(PlatformImpl, PB0) drives it:",
        "it stays 1:1 with the",
        "NUCLEO pin map.",
        "",
        "Green 470 Ohm: ~1.8 mA",
        "(V_F 2.45 V at 2 mA,",
        "KT-0603G p.5)."])


def rgb_chain(sh):
    sh.box(86.36, 20.32, 405.13, 124.46,
           f"RGB LEDs: {RGB_COUNT} x WS2812B-2020-V6 on +5V (PA7 TIM17_CH1 + DMA, D-035)")
    buf = active(sh, "U804", "SN74AHCT1G125DBVR", "74xGxx:74AHCT1G125", "Package_TO_SOT_SMD:SOT-23-5", 132.08, 50.8,
                 value="SN74AHCT1G125", purpose="3.3 V -> 5 V data level shift for the LED chain (D-035)")
    buf.fpos = (5.08, 7.62, "left")
    pull = R(sh, "R803", "10k", 109.22, 57.15, "LED_DATA", "GND",
             purpose="keeps the LED data low while PA7 floats in reset (SCLS378L note 3)")
    term = R(sh, "R802", "33", 157.48, 50.8, "LED_BUF", "LED_D1", rot=90,
             purpose="source termination at the buffer output (mcu-circuit-design s9)")
    sh.rail("LED_DATA", 50.8, [pull["1"], buf["2"]], label="left", ext=7.62)
    sh.rail("GND", 38.1, [buf["1"]], tap=(137.16, (0, 1)))
    sh.net(buf["5"], "+5V")
    sh.net(buf["3"], "GND")
    sh.link(buf["4"], term["1"], "LED_BUF")

    leds = []
    for i in range(RGB_COUNT):
        row, col = divmod(i, RGB_PER_ROW)
        led = active(sh, f"D{802 + i}", "WS2812B-2020-V6", "LED:WS2812B-2020", RGB, 177.8 + 27.94 * col,
                     50.8 + 40.64 * row, value="WS2812B-2020", purpose=f"RGB LED {i + 1} of {RGB_COUNT} (D-035)")
        led.fpos = (2.54, -12.7, "left")
        sh.net(led["4"], "+5V")
        sh.net(led["2"], "GND")
        leds.append(led)
    sh.link(term["2"], leds[0]["3"], "LED_D1")
    for i in range(1, RGB_COUNT):
        net = f"LED_D{i + 1}"
        prev, nxt = leds[i - 1]["1"], leds[i]["3"]
        if i % RGB_PER_ROW:
            sh.link(prev, nxt, net)
        else:
            sh.path(net, [prev, (prev.x + 5.08, prev.y), (prev.x + 5.08, 69.85), (nxt.x - 5.08, 69.85),
                          (nxt.x - 5.08, nxt.y), nxt])
    sh.nc(leds[-1]["1"])

    caps = []
    for i in range(RGB_COUNT):
        row, col = divmod(i, 4)
        caps.append(C(sh, f"C{806 + i}", "100n_0402_16V_X7R", 345.44 + 15.24 * col, 40.64 + 27.94 * row, "+5V", "GND",
                      purpose=f"LED {i + 1} VDD decoupling, at its pin (WS2812B-2020-V6 C_n)"))
    for row in range(3):
        y = 40.64 + 27.94 * row
        group = caps[4 * row:4 * row + 4]
        sh.rail("+5V", y - 7.62, [c["1"] for c in group], tap=(337.82, (0, -1)))
        sh.rail("GND", y + 7.62, [c["2"] for c in group], tap=(397.51, (0, 1)))
    c801 = C(sh, "C801", "100n_0402_16V_X7R", 101.6, 88.9, "+5V", "GND", purpose="buffer VCC bypass")
    c805 = C(sh, "C805", "10u_0805_25V_X5R", 116.84, 88.9, "+5V", "GND", purpose="LED chain local bulk (ASSUMPTION)")
    sh.rail("+5V", 81.28, [c801["1"], c805["1"]], tap=(93.98, (0, -1)))
    sh.rail("GND", 96.52, [c801["2"], c805["2"]], tap=(93.98, (0, 1)))
    sh.note(91.44, 106.68, [
        "12 mA per colour, 36 mA per LED at full white: 432 mA for the chain; +5V budget ~570 mA, well inside the "
        "TPS62933F (3 A) and L201 (I_sat 3.2 A).",
        "LED V_IH is 0.55 VDD = 2.75 V at 5 V; a 3.3 V GPIO gives only 0.15 V margin, so U804 (TTL input, 5 V output) "
        "drives the chain.",
        "WS2812 protocol, GRB order, 800 kHz from TIM17 + DMA; reset >= 280 us.  One 100 nF per LED at its VDD pin "
        "(C806-C817).  Brightness is a firmware choice."])


def qwiic_eeprom(sh):
    sh.box(15.24, 101.6 + DY, 205.74, 198.12 + DY, "Qwiic I2C3 expansion and EEPROM (PB10 SCL, PB11 SDA)")
    j = sh.part("Connector_Generic_MountingPin:Conn_01x04_MountingPin", "J801", "Qwiic", (27.94, 129.54 + DY),
                mirror="y", fp="Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", lcsc="C160404",
                mpn="SM04B-SRSS-TB(LF)(SN)", Purpose="I2C3 expansion (Qwiic pinout)")
    j.fpos = (-5.08, -7.62, "left")
    sh.nets(j, {"1": "GND", "2": "+3V3", "MP": "GND"})
    r808 = R(sh, "R808", "2.2k", 55.88, 123.19 + DY, "QWIIC_SDA", "+3V3", rot=180,
             purpose="I2C pull-up (SLVA689A window 967-3541 ohm)")
    r809 = R(sh, "R809", "2.2k", 68.58, 123.19 + DY, "QWIIC_SCL", "+3V3", rot=180, purpose="I2C pull-up")
    sh.rail("+3V3", 116.84 + DY, [r808["2"], r809["2"]], tap=(76.2, (0, -1)))
    sh.rail("QWIIC_SDA", 132.08 + DY, [j["3"], r808["1"]], label="right", ext=25.4)
    sh.rail("QWIIC_SCL", 134.62 + DY, [j["4"], r809["1"]], label="right", ext=12.7)
    esd = active(sh, "U801", "TPD4E05U06QDQARQ1", "Power_Protection:TPD4E05U06DQA", "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
                 53.34, 157.48 + DY, purpose="Qwiic ESD")
    esd.fpos = (-12.7, -13.97, "left")
    sh.nets(esd, {"1": "QWIIC_SDA", "2": "QWIIC_SCL", "4": "+3V3", "5": None, "3": "GND", "8": "GND",
                  "6": None, "7": None, "9": None, "10": None})

    ee = active(sh, "U802", "M24C64-RMN6TP", "Memory_EEPROM:24LC64", SOIC8, 147.32, 137.16 + DY,
                value="M24C64-RMN6TP", purpose="I2C EEPROM 64 Kbit at 0x50: E2..E0 low, WC low = writes enabled (D-031)")
    ee.fpos = (-10.16, -12.7, "left")
    c802 = C(sh, "C802", "100n_0402_16V_X7R", 185.42, 137.16 + DY, "+3V3", "GND", purpose="EEPROM bypass")
    sh.nets(ee, {"5": "QWIIC_SDA", "6": "QWIIC_SCL"})
    sh.rail("+3V3", 124.46 + DY, [ee["8"], c802["1"]], tap=(172.72, (0, -1)))
    sh.vrail("GND", 134.62, [ee["1"], ee["2"], ee["3"], (134.62, 152.4 + DY)])
    sh.path("GND", [ee["7"], (162.56, 139.7 + DY), (162.56, 152.4 + DY)])
    sh.rail("GND", 152.4 + DY, [(134.62, 152.4 + DY), ee["4"], (162.56, 152.4 + DY), c802["2"]], tap=(172.72, (0, 1)))
    sh.note(20.32, 182.88 + DY, [
        "Qwiic pinout: 1 GND, 2 3V3, 3 SDA, 4 SCL.  2.2k pull-ups: window 967-3541 Ohm, Fast mode, C_b 100 pF (SLVA689A).",
        "U801 ESD at the connector.  U802 M24C64-R at 0x50: E2..E0 low, WC low = writes enabled (D-031)."])


def nfc(sh):
    sh.box(210.82, 101.6 + DY, 405.13, 198.12 + DY, "NFC tag: ST25DV04KC + printed 13.56 MHz coil (D-030)")
    tag = active(sh, "U803", "ST25DV04KC-IE8S3", "e-inverted-pendulum:ST25DV04KC-IE8S3", SOIC8, 325.12, 147.32 + DY,
                 purpose="NFC Type 5 tag on I2C3 (0x53/0x57); V_EH unused; GPO to PA2 (D-030)")
    tag.fpos = (2.54, -13.97, "left")
    coil = nobom(sh, "AE801", "e-inverted-pendulum:NFC_Coil", "NFC coil", "e-inverted-pendulum:NFC_Coil_25x21mm",
                 271.78, 147.32 + DY, 270, purpose="13.56 MHz printed loop, 10 turns, 25 x 21 mm (docs/nfc.md)")
    coil.fpos = (-3.81, -1.27, "right")
    trim = C(sh, "C804", "2.7p_0402_50V_C0G", 287.02, 147.32 + DY, "NFC_AC0", "NFC_AC1", dnp=True,
             purpose="coil trim: f0 14.2 -> 13.56 MHz needs about 2.9 pF (scripts/nfc_coil.py); fit after a phone/VNA check")
    c803 = C(sh, "C803", "100n_0402_16V_X7R", 322.58, 127.0 + DY, "+3V3", "GND", purpose="NFC tag bypass")
    gpo = R(sh, "R810", "10k", 365.76, 135.89 + DY, "NFC_GPO", "+3V3", rot=180,
            purpose="GPO is open drain (DS13519 Fig. 2)")
    sh.nc(tag["1"])
    sh.nets(tag, {"5": "QWIIC_SDA", "6": "QWIIC_SCL"})
    sh.rail("NFC_AC0", 134.62 + DY, [coil["1"], trim["1"], (302.26, 134.62 + DY)])
    sh.path("NFC_AC0", [tag["2"], (302.26, 147.32 + DY), (302.26, 134.62 + DY)])
    sh.rail("NFC_AC1", 160.02 + DY, [coil["2"], trim["2"], (299.72, 160.02 + DY)])
    sh.path("NFC_AC1", [tag["3"], (299.72, 149.86 + DY), (299.72, 160.02 + DY)])
    sh.path("+3V3", [tag["8"], (309.88, 139.7 + DY), (309.88, 121.92 + DY)])
    sh.rail("+3V3", 121.92 + DY, [(309.88, 121.92 + DY), c803["1"]], tap=(316.23, (0, -1)))
    sh.net(c803["2"], "GND")
    sh.path("GND", [tag["4"], (309.88, 154.94 + DY), (309.88, 165.1 + DY)])
    sh.rail("GND", 165.1 + DY, [(309.88, 165.1 + DY)], tap=(309.88, (0, 1)))
    sh.rail("NFC_GPO", 147.32 + DY, [tag["7"], gpo["1"]], label="right", ext=5.08)
    sh.net(gpo["2"], "+3V3")
    sh.note(215.9, 175.26 + DY, [
        "ST25DV04KC: ISO 15693 / NFC Type 5 tag on I2C3 (0x53 user, 0x57 system); V_EH unused; GPO open drain -> PA2 (EXTI2).",
        "AE801: 10 turns, 25 x 21 mm, 4.25 uH; f0 14.2 MHz with C_TUN 28.5 pF + 1 pF (scripts/nfc_coil.py, docs/nfc.md).",
        "C804 2.7 pF DNP across AC0-AC1 trims f0 to 13.56 MHz: fit after a phone / VNA check.  Keep metal off the coil."])


def build(project, values):
    sh = Sheet(project, 8, "ui", "User interface, expansion, test points")
    sh.desc = ["Status LED (PB0) + 12 RGB LEDs (PA7)", "Qwiic I2C3 + ESD, M24C64 EEPROM",
               "ST25DV04KC NFC tag + printed coil", "No buttons, no buzzer (D-035)"]
    status_led(sh)
    rgb_chain(sh)
    qwiic_eeprom(sh)
    nfc(sh)
    sh.box(15.24, 231.14, 205.74, 271.78, "Test points")
    test_points(sh, 30.48, 259.08, [("TP801", "LED_DATA"), ("TP802", "QWIIC_SDA"), ("TP803", "QWIIC_SCL"),
                                    ("TP804", "GND")], pitch=25.4)
    return sh
