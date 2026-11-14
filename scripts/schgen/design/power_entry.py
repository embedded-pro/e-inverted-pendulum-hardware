"""Sheet 1: battery input, fuse, back-to-back P-FET switch with soft start (D-011, D-021), TVS, VBAT sense.

Sources: docs/design-calcs.md (Power path, VBAT sense); Littelfuse SMBJ p.2; AO4805 datasheet p.1-2; S1.
"""

from parts import C, R, active, test_points
from sch import Sheet

PFET = "Transistor_FET:Q_Dual_PMOS_S1G1S2G2D2D2D1D1"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"


def build(project, values):
    sh = Sheet(project, 1, "power_entry", "Battery input and protection")
    sh.desc = ["XT30 3S LiPo input, 4 A fuse", "AO4805 back-to-back P-FET switch:", "reverse polarity, soft start, SW101",
               "SMBJ15A clamp, VBAT sense divider"]

    sh.box(15.24, 20.32, 182.88, 129.54, "Input, fuse and power switch (D-011, D-021)")
    j = sh.part("Connector_Generic:Conn_01x02", "J101", "XT30 battery", (25.4, 50.8), mirror="y",
                fp="e-inverted-pendulum:AMASS_XT30UPB-F_1x02_P5.00mm_Vertical", lcsc="C108769",
                mpn="XT30UPB-F30.G.Y", Purpose="3S LiPo input, pad 1 = +")
    j.fpos = (-5.08, 8.89, "left")
    f = active(sh, "F101", "1206FA-4A", "Device:Fuse", "Fuse:Fuse_1206_3216Metric", 40.64, 50.8, 90,
               value="4A fast", purpose="300 A @ 24 V breaking capacity")
    qa = active(sh, "Q101", "AO4805", PFET, SOIC8, 60.96, 53.34, 90, unit=1,
                purpose="FET1 (D1 to battery) blocks reverse polarity; FET2 (D2 to VBAT) switches the load")
    qb = active(sh, "Q101", "AO4805", PFET, SOIC8, 119.38, 53.34, 90, unit=2, mirror="y",
                purpose="FET1 (D1 to battery) blocks reverse polarity; FET2 (D2 to VBAT) switches the load")
    qa.fpos = (-3.81, -10.16, "left")
    qb.fpos = (-3.81, -10.16, "left")
    r101 = R(sh, "R101", "100k", 73.66, 58.42, "PP_G", "PP_S", rot=180, purpose="gate off when the switch is open")
    d101 = active(sh, "D101", "BZT52C15", "Device:D_Zener", "Diode_SMD:D_SOD-123", 83.82, 58.42, 270,
                  purpose="V_GS clamp 13.8-15.6 V < 20 V")
    sh.nets(d101, {"1": "PP_S", "2": "PP_G"})
    c102 = C(sh, "C102", "1u_0603_50V_X5R", 99.06, 58.42, "PP_G", "PP_S", rot=180,
             purpose="holds V_GS ~ -0.5 V on hot plug with the switch off (S1)")
    r102 = R(sh, "R102", "100k", 68.58, 73.66, "PP_G", "SW_ON",
             purpose="switch on: V_GS = -VBAT/2 (-4.5 V at 9 V); 0.08 mA Miller current (S1)")
    sw = active(sh, "SW101", "SS-12D10L5", "Switch:SW_SPDT", "e-inverted-pendulum:SW_Slide_SPDT_SS-12D10L5_P4.70mm",
                83.82, 85.09, purpose="power switch (gate current only)")
    sh.nc(sw["3"])
    r103 = R(sh, "R103", "1k", 129.54, 66.04, "PP_G", "PP_SS", rot=90, purpose="Miller soft start series R")
    c101 = C(sh, "C101", "47n_0603_50V_X7R", 137.16, 58.42, "PP_SS", "VBAT", rot=180,
             purpose="Miller soft start: ~1.7 V/ms, ~0.7 A inrush (S1)")
    d102 = active(sh, "D102", "SMBJ15A", "Device:D_Zener", "Diode_SMD:D_SMB", 152.4, 58.42, 270, value="SMBJ15A",
                  purpose="TVS after the FETs: V_RWM 15 V, V_C 24.4 V")
    fv = sh.flag("VBAT", (165.1, 50.8), label=False)
    fg = sh.flag("GND", (165.1, 99.06), label=False)

    sh.link(j["1"], f["1"], "BAT_P")
    sh.link(f["2"], qa["7"], "BAT_F")
    sh.link(qa["8"], qa["7"], "BAT_F")
    sh.rail("PP_S", 50.8, [qa["1"], r101["2"], d101["1"], c102["2"], qb["3"]])
    sh.rail("PP_G", 66.04, [qa["2"], r101["1"], r102["1"], d101["2"], c102["1"], qb["4"], r103["1"]])
    sh.link(r102["2"], sw["2"], "SW_ON")
    sh.link(r103["2"], c101["1"], "PP_SS")
    sh.link(qb["6"], qb["5"], "VBAT")
    sh.rail("VBAT", 50.8, [qb["5"], c101["2"], d102["1"], fv["1"]], tap=(172.72, (0, -1)))
    sh.path("GND", [j["2"], (33.02, 53.34), (33.02, 99.06)])
    sh.path("GND", [sw["1"], (96.52, 82.55), (96.52, 99.06)])
    sh.rail("GND", 99.06, [(33.02, 99.06), (96.52, 99.06), d102["2"], fg["1"]], tap=(172.72, (0, 1)))
    sh.note(20.32, 104.14, [
        "J101 XT30: 3S LiPo, 9.0-12.6 V, pad 1 = +.  F101 4 A fast, 300 A at 24 V breaking capacity.",
        "Q101 AO4805 (D-011): FET A (drain to the battery) blocks a reversed pack; FET B switches the load.",
        "SW101 on: R102 pulls PP_G low, V_GS = -VBAT/2 (-4.5 V at 9.0 V, -6.8 V at 13.5 V); D101 keeps |V_GS| < 20 V.",
        "SW101 off: R101 holds the gates off; C102 limits the hot-plug V_GS step to -0.57 V (< |V_th| 1.0 V) (S1).",
        "Soft start (D-021): R103 + C101 Miller integrator, ~1.7 V/ms, inrush ~0.7 A for ~7 ms (S1); turn-off tau 105 ms.",
        "D102 SMBJ15A after the FETs: V_RWM 15 V > 13.5 V, V_C 24.4 V < 30 V (AO4805) and 32 V (TPS62933).",
        "It must never sit before the FETs: a reversed pack would forward-bias it through the fuse."])

    sh.box(187.96, 20.32, 279.4, 129.54, "VBAT sense (ADC PC1)")
    r104 = R(sh, "R104", "100k", 205.74, 58.42, "VBAT", "VBAT_SENSE", purpose="VBAT divider top (ratio 0.2126)")
    r105 = R(sh, "R105", "27k", 205.74, 73.66, "VBAT_SENSE", "GND", purpose="VBAT divider bottom")
    c103 = C(sh, "C103", "100n_0603_50V_X7R", 218.44, 73.66, "VBAT_SENSE", "GND",
             purpose="ADC charge bucket (>> 20 x 5 pF)")
    sh.net(r104["1"], "VBAT")
    sh.rail("VBAT_SENSE", 66.04, [r104["2"], r105["1"], c103["1"]], label="right", ext=10.16)
    sh.rail("GND", 82.55, [r105["2"], c103["2"]], tap=(212.09, (0, 1)))
    sh.note(193.04, 99.06, [
        "VBAT_SENSE = VBAT x 27k / 127k = 0.2126 VBAT",
        "(12.6 V -> 2.68 V, 13.5 V -> 2.87 V < VDDA).",
        "Source 21.3 kOhm < 50 kOhm R_AIN max; C103 100 nF",
        ">> 20 x 5 pF C_ADC, tau 2.1 ms (DS11929 Table 73).",
        "+/-1.57 % ratio error with 1 % parts:",
        "calibrate per board against VREFINT."])

    sh.box(15.24, 134.62, 182.88, 175.26, "Test points")
    test_points(sh, 30.48, 162.56, [("TP101", "VBAT"), ("TP102", "BAT_F"), ("TP103", "PP_G"),
                                    ("TP104", "VBAT_SENSE"), ("TP105", "GND")], pitch=25.4)
    return sh
