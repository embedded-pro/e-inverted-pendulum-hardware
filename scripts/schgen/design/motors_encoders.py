"""Sheet 6: MG310 motor + encoder connectors and A/B encoder inputs (ESD -> RC -> Schmitt buffer), D-012, D-028.

One JST PH 6-pin per motor carries the motor and its Hall encoder (MG310 pinout: 1 M-, 2 encoder VCC, 3 A, 4 B,
5 GND, 6 M+). The MG310 has no index, so the buffer's third input is grounded and the index pins read low.
Sources: docs/design-calcs.md (Encoders), SCES470D (SN74LVC3G17), SLVSCO7A (TPD4E05U06-Q1), interface-layout s2.
"""

from parts import C, R, active, test_points
from sch import Sheet

BUFFER = "74xGxx:74LVC3G17"
SSOP8 = "Package_SO:SSOP-8_2.95x2.8mm_P0.65mm"
BUFFER_PURPOSE = "Schmitt buffer, I_off: 5 V inputs while 3V3 is off; 3rd input grounded (no index, D-028)"


def buffer(sh, ref, x, y, unit):
    part = active(sh, ref, "SN74LVC3G17DCTR", BUFFER, SSOP8, x, y, unit=unit, purpose=BUFFER_PURPOSE)
    part.fpos = (-5.08, -7.62, "left")
    return part


def channel(sh, side, ch, x0, y, unit, pins, refs, buf_ref):
    """One encoder channel row: RAW label -> DNP pull-up -> 100 Ohm -> 1 nF -> Schmitt buffer -> MCU label."""
    raw, filtered, out = f"ENC_{side}_{ch}_RAW", f"ENC_{side}_{ch}_F", f"ENC_{side}_{ch}"
    pull = R(sh, refs[0], "2.2k", x0 + 86.36, y - 7.62, raw, "ENC_VCC", rot=180, dnp=True,
             purpose="open-collector pull-up option")
    series = R(sh, refs[1], "100", x0 + 101.6, y, raw, filtered, rot=90, purpose="series R, f_c 1.59 MHz with 1 nF")
    cap = C(sh, refs[2], "1n_0603_50V_X7R", x0 + 114.3, y + 3.81, filtered, "GND", purpose="input RC")
    buf = buffer(sh, buf_ref, x0 + 142.24, y, unit)
    sh.rail(raw, y, [pull["1"], series["1"]], label="left", ext=7.62)
    sh.rail(filtered, y, [series["2"], cap["1"], buf[pins[0]]])
    sh.net(buf[pins[1]], out)


def side_box(sh, side, name, x0, y0, refs):
    sh.box(x0, y0, x0 + 190.5, y0 + 137.16, f"{name.capitalize()} MG310: motor + Hall encoder ({refs['j']})")
    j = sh.part("Connector_Generic:Conn_01x06", refs["j"], f"Motor {name}", (x0 + 12.7, y0 + 27.94), mirror="y",
                fp="Connector_JST:JST_PH_S6B-PH-K_1x06_P2.00mm_Horizontal", lcsc="C157920", mpn="S6B-PH-K-S(LF)(SN)",
                Purpose=f"{name} MG310: 1 M-, 2 enc VCC, 3 A, 4 B, 5 GND, 6 M+ (D-028); 2 A contacts")
    j.fpos = (-5.08, -10.16, "left")
    sh.nets(j, {"1": f"MOT_{side}_N", "2": "ENC_VCC", "3": f"ENC_{side}_A_RAW", "4": f"ENC_{side}_B_RAW", "5": "GND",
                "6": f"MOT_{side}_P"})
    snub = C(sh, refs["snub"], "100n_0603_50V_X7R", x0 + 12.7, y0 + 58.42, f"MOT_{side}_P", f"MOT_{side}_N", dnp=True,
             purpose="optional motor-terminal suppression (fit at the motor preferably)")
    esd = active(sh, refs["esd"], "TPD4E05U06QDQARQ1", "Power_Protection:TPD4E05U06DQA",
                 "Package_SON:USON-10_2.5x1.0mm_P0.5mm", x0 + 45.72, y0 + 88.9,
                 purpose="ESD at the connector, pass-through routing")
    esd.fpos = (-12.7, -13.97, "left")
    sh.nets(esd, {"1": f"ENC_{side}_A_RAW", "2": f"ENC_{side}_B_RAW", "4": None, "5": "ENC_VCC", "3": "GND",
                  "8": "GND", "6": None, "7": None, "9": None, "10": None})
    channel(sh, side, "A", x0, y0 + 25.4, 1, ("1", "7"), refs["a"], refs["buf"])
    channel(sh, side, "B", x0, y0 + 50.8, 2, ("6", "2"), refs["b"], refs["buf"])
    z = buffer(sh, refs["buf"], x0 + 142.24, y0 + 73.66, 3)
    sh.vrail("GND", x0 + 124.46, [z["3"]], tap=(y0 + 76.2, (0, 1)))
    sh.net(z["5"], f"ENC_{side}_Z")
    pwr = active(sh, refs["buf"], "SN74LVC3G17DCTR", BUFFER, SSOP8, x0 + 167.64, y0 + 101.6, unit=4,
                 purpose=BUFFER_PURPOSE)
    pwr.fpos = (5.08, -5.08, "left")
    byp = C(sh, refs["byp"], "100n_0402_16V_X7R", x0 + 142.24, y0 + 101.6, "+3V3", "GND", purpose="buffer bypass")
    sh.rail("+3V3", y0 + 91.44, [byp["1"], pwr["8"]], tap=(x0 + 154.94, (0, -1)))
    sh.rail("GND", y0 + 111.76, [byp["2"], pwr["4"]], tap=(x0 + 154.94, (0, 1)))
    sh.note(x0 + 5.08, y0 + 119.38, [
        f"{refs['j']}: 1 M-, 2 encoder VCC, 3 A, 4 B, 5 GND, 6 M+ (MG310, D-028).  {refs['snub']} DNP: fit at the motor if needed.",
        f"{refs['esd']} at the connector, pass-through routing.  The third buffer input is grounded: ENC_{side}_Z reads low."])


def build(project, values):
    sh = Sheet(project, 6, "motors_encoders", "Motor connectors and encoder inputs")
    sh.desc = ["Two JST PH 6-pin (MG310 motor + Hall A/B)", "ESD -> 100 Ohm + 1 nF -> SN74LVC3G17",
               "Encoder supply 5V0 (or 3V3) via 100 mA PTC", "Third buffer input grounded (no index)"]

    sh.box(15.24, 20.32, 205.74, 76.2, "Encoder supply (D-016)")
    r601 = R(sh, "R601", "0", 33.02, 43.18, "+5V", "ENC_SRC", purpose="encoder supply 5V0 (default, D-016)")
    r602 = R(sh, "R602", "0", 50.8, 43.18, "+3V3", "ENC_SRC", dnp=True, purpose="encoder supply 3V3 option")
    ptc = active(sh, "F601", "SMD0805P010TF", "Device:Polyfuse_Small", "Fuse:Fuse_0805_2012Metric", 71.12, 50.8, 90,
                 value="PTC 100mA", purpose="shorted cable can't drop the rail")
    c601 = C(sh, "C601", "10u_0603_10V_X5R", 88.9, 54.61, "ENC_VCC", "GND", purpose="encoder supply bulk")
    c602 = C(sh, "C602", "100n_0603_50V_X7R", 104.14, 54.61, "ENC_VCC", "GND", purpose="encoder supply HF")
    sh.rail("ENC_SRC", 50.8, [r601["2"], r602["2"], ptc["1"]])
    sh.rail("ENC_VCC", 50.8, [ptc["2"], c601["1"], c602["1"]], label="right", ext=7.62)
    sh.rail("GND", 63.5, [c601["2"], c602["2"]], tap=(96.52, (0, 1)))
    sh.note(127.0, 35.56, [
        "ENC_VCC: 5V0 through R601 (default, D-016)",
        "or 3V3 through R602 (DNP).",
        "F601 100 mA PTC: a shorted encoder cable",
        "can't pull the rail down."])

    sh.box(210.82, 20.32, 405.13, 76.2, "Encoder input chain (D-012, docs/design-calcs.md)")
    sh.note(215.9, 27.94, [
        "Per channel: ESD at the connector -> 2.2k open-collector pull-up (DNP, for open-collector encoders)",
        "-> 100 Ohm + 1 nF: f_c 1.59 MHz > 2 x 105 kHz max channel rate, rise 220 ns",
        "-> SN74LVC3G17 Schmitt buffer at 3V3: V_T+ <= 1.87 V, 5.5 V tolerant inputs with I_off (SCES470D)",
        "-> LPTIM1 (left) / TIM2 (right) encoder inputs.",
        "The MG310 has no index: the third input is grounded, PC5 / PC3 read low (D-028).",
        "Layout: MOT_x away from every ENC_* trace on all layers (docs/power-map.md)."])

    side_box(sh, "L", "left", 15.24, 81.28, {"j": "J601", "snub": "C603", "esd": "U601", "buf": "U602", "byp": "C606",
                                             "a": ("R603", "R604", "C604"), "b": ("R605", "R606", "C605")})
    side_box(sh, "R", "right", 214.63, 81.28, {"j": "J602", "snub": "C607", "esd": "U603", "buf": "U604", "byp": "C610",
                                               "a": ("R607", "R608", "C608"), "b": ("R609", "R610", "C609")})

    sh.box(15.24, 223.52, 205.74, 264.16, "Test points: buffered encoder outputs")
    test_points(sh, 30.48, 251.46, [("TP601", "ENC_L_A"), ("TP602", "ENC_L_B"), ("TP603", "ENC_R_A"),
                                    ("TP604", "ENC_R_B"), ("TP605", "ENC_VCC"), ("TP606", "GND")], pitch=25.4)
    return sh
