"""Sheet 5: DRV8711 driving two brushed motors through four CSD88537ND half-bridges.

Sources: TI SLVSC40 (pin table p.3-4, critical components p.4, sense p.16), docs/design-calcs.md (DRV8711),
S0 sizing (Rsense 50 mOhm, trip 2.0 A, D-027), power-pcb-layout s3.
"""

from parts import C, R, active, nobom
from sch import Sheet

NFET = "Transistor_FET:Q_Dual_NMOS_S1G1S2G2D2D2D1D1"
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
DRV_NETS = {
    "8": "DRV_NSLEEP", "9": "DRV_RESET", "16": "DRV_SCS", "14": "SPI1_SCK_BUS", "15": "SPI1_MOSI",
    "17": "SPI1_MISO", "10": "DRV_AIN1", "11": "DRV_AIN2", "12": "DRV_BIN1", "13": "DRV_BIN2",
    "18": "DRV_NFAULT", "19": "DRV_NSTALL", "20": "DRV_BEMF", "6": "DRV_V5", "7": "DRV_VINT",
    "3": "DRV_VCP", "1": "DRV_CP1", "2": "DRV_CP2",
    "37": "MOT_L_P", "30": "MOT_L_N", "28": "MOT_R_P", "21": "MOT_R_N",
    "36": "A1HS_D", "35": "A1LS_D", "31": "A2HS_D", "32": "A2LS_D",
    "27": "B1HS_D", "26": "B1LS_D", "22": "B2HS_D", "23": "B2LS_D",
    "34": "DRV_AISENP", "33": "DRV_AISENN", "25": "DRV_BISENP", "24": "DRV_BISENN",
}


def half_bridge(sh, name, out, x, y, r_hs, r_ls, q, d):
    """HS FET (unit 1) over LS FET (unit 2) at column x; gate resistors left, clamp diode and output right."""
    purpose = f"half-bridge {name}: FET1 high side, FET2 low side"
    hs = active(sh, q, "CSD88537ND", NFET, SOIC8, x, y, unit=1, purpose=purpose)
    ls = active(sh, q, "CSD88537ND", NFET, SOIC8, x, y + 17.78, unit=2, purpose=purpose)
    hs.fpos = (7.62, -2.54, "left")
    ls.fpos = (7.62, 2.54, "left")
    rh = R(sh, r_hs, "0", x - 20.32, y, f"{name}HS_D", f"{name}HS_G", rot=90,
           purpose=f"{name} high-side gate R (at the FET)")
    rl = R(sh, r_ls, "0", x - 20.32, y + 17.78, f"{name}LS_D", f"{name}LS_G", rot=90,
           purpose=f"{name} low-side gate R (at the FET)")
    sh.link(rh["2"], hs["2"], f"{name}HS_G")
    sh.link(rl["2"], ls["4"], f"{name}LS_G")
    clamp = active(sh, d, "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA", x + 25.4, y + 12.7, 270,
                   purpose="clamps the dead-time freewheel to -0.36 V (DRV8711 phase pin abs max -0.6 V, S2)")
    sh.net(clamp["2"], "GND")
    node = (hs["1"].x, y + 8.89)
    sh.vrail(out, hs["1"].x, [hs["1"], ls["5"], node])
    sh.link(ls["6"], ls["5"], out)
    sh.rail(out, y + 8.89, [node, clamp["1"]], label="right", ext=5.08)
    sh.link(hs["8"], hs["7"], "VBAT")
    return hs, ls


def sense(sh, bridge, x, y, r_sense, nt, r_p, r_n, c_f):
    """Rsense from SENSE_x to GND with the Kelvin tap NT at its ground pad, filter legs to the DRV8711."""
    rs = active(sh, r_sense, "HoLR1206-1W-50mR-1%-75ppm", "Device:R", "Resistor_SMD:R_1206_3216Metric", x, y + 7.62,
                value="50m", purpose=f"bridge {bridge} Rsense, Kelvin taps from the inner pad edges")
    tie = nobom(sh, nt, "Device:NetTie_2", "NetTie", "NetTie:NetTie-2_SMD_Pad0.5mm", x + 10.16, y + 13.97, 270,
                purpose=f"bridge {bridge} xISENN Kelvin tap at the Rsense ground pad")
    tie.fpos = (2.54, 0, "left")
    sh.nets(rs, {"1": f"SENSE_{bridge}", "2": "GND"})
    sh.nets(tie, {"1": f"KELVIN_{bridge}N", "2": "GND"})
    rp = R(sh, r_p, "0", x + 25.4, y, f"SENSE_{bridge}", f"DRV_{bridge}ISENP", rot=90,
           purpose="sense filter leg (27-33 R if fitted)")
    rn = R(sh, r_n, "0", x + 25.4, y + 11.43, f"KELVIN_{bridge}N", f"DRV_{bridge}ISENN", rot=90,
           purpose="sense filter leg (matched)")
    cf = C(sh, c_f, "1n_0402_50V_C0G", x + 35.56, y + 5.08, f"DRV_{bridge}ISENP", f"DRV_{bridge}ISENN", dnp=True,
           purpose="optional sense filter, RC 50-60 ns (SLVSC40 Fig. 6)")
    sh.rail("GND", y + 16.51, [rs["2"], tie["2"]], tap=(x + 5.08, (0, 1)))
    sh.link(tie["1"], rn["1"], f"KELVIN_{bridge}N")
    sh.rail(f"DRV_{bridge}ISENP", y, [rp["2"], cf["1"]], label="right", ext=5.08)
    sh.rail(f"DRV_{bridge}ISENN", y + 11.43, [rn["2"], cf["2"]], label="right", ext=5.08)
    return rs, rp


def bridge_box(sh, bridge, motor, y0, refs):
    """One H-bridge: two half-bridges, bulk + HF caps on the drains, Rsense and the Kelvin sense network."""
    side = "L" if bridge == "A" else "R"
    sh.box(205.74, y0, 405.13, y0 + 109.22, f"Bridge {bridge}: {motor} MG310 (MOT_{side}_P / MOT_{side}_N)")
    y = y0 + 30.48
    hs1, ls1 = half_bridge(sh, f"{bridge}1", f"MOT_{side}_P", 243.84, y, *refs["h1"])
    hs2, ls2 = half_bridge(sh, f"{bridge}2", f"MOT_{side}_N", 312.42, y, *refs["h2"])
    bulk = C(sh, refs["bulk"], "10u_0805_25V_X5R", 358.14, y - 2.54, "VBAT", "GND",
             purpose=f"bridge {bridge} bulk at the HS drains")
    hf = C(sh, refs["hf"], "100n_0603_50V_X7R", 373.38, y - 2.54, "VBAT", "GND", purpose=f"bridge {bridge} HF hot-loop cap")
    sh.rail("VBAT", y - 10.16, [hs1["7"], hs2["7"], bulk["1"], hf["1"]], tap=(220.98, (0, -1)))
    sh.rail("GND", y + 7.62, [bulk["2"], hf["2"]], tap=(365.76, (0, 1)))
    rs, rp = sense(sh, bridge, 340.36, y + 27.94, *refs["sense"])
    sh.rail(f"SENSE_{bridge}", y + 27.94, [ls1["3"], ls2["3"], rs["1"], rp["1"]])
    sh.note(210.82, y0 + 86.36, [
        f"{bridge}1 / {bridge}2: CSD88537ND, FET1 high side, FET2 low side; 0 Ohm gate R at each FET (edge-rate trim).",
        "SS34 from GND to each phase node: freewheel at -0.36 V, not the -0.73 V body diode (phase pins abs max -0.6 V, S2).",
        f"{refs['sense'][0]} 50 mOhm: the motor current flows straight through it; Kelvin taps from its inner pad edges"
        f" ({refs['sense'][1]} at the GND pad).",
        f"0 Ohm filter legs, {refs['sense'][4]} DNP: fit 27-33 Ohm + 1 nF if noisy (SLVSC40 Fig. 6).  "
        f"{refs['bulk']} + {refs['hf']} at the HS drains: hot loop over L2 GND."])


def build(project, values):
    sh = Sheet(project, 5, "drive", "Motor drive (DRV8711 + external FETs)")
    sh.desc = ["DRV8711, PWMMODE 1 (indexer bypass)", "Four CSD88537ND half-bridges, SS34 clamps",
               "Rsense 50 mOhm + Kelvin taps, trip 2.0 A", "VM bulk 220 uF, charge pump, pull-ups"]

    sh.box(15.24, 20.32, 200.66, 243.84, "DRV8711 gate driver (PWMMODE 1, D-002)")
    u = sh.part("e-inverted-pendulum:DRV8711", "U501", "DRV8711", (104.14, 116.84),
                fp="Package_SO:HTSSOP-38-1EP_4.4x9.7mm_P0.5mm_EP2.74x4.75mm_ThermalVias", lcsc="C60013",
                mpn="DRV8711DCPR", Purpose="PWMMODE = 1 (indexer bypass), D-002")
    u.fpos = (-24.13, -34.29, "left")
    sh.nets(u, DRV_NETS)
    sh.vrail("GND", 77.47, [u["5"], u["29"], u["38"], u["39"]], tap=(147.32, (0, 1)))
    sh.vrail("VBAT", 130.81, [u["4"]], tap=(86.36, (0, -1)))

    c507 = active(sh, "C507", "EEEFK1V221P", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10", 33.02, 45.72,
                  value="220u 35V", purpose="VM bulk (>= 100 uF per SLVSC40), 600 mA ripple rating")
    c508 = C(sh, "C508", "10n_0603_50V_X7R", 48.26, 45.72, "VBAT", "GND", purpose="VM ceramic 0.01 uF at the pin")
    c509 = C(sh, "C509", "1u_0603_50V_X5R", 63.5, 45.72, "DRV_VCP", "VBAT", rot=180, purpose="VCP to VM, 1 uF >= 16 V")
    c510 = C(sh, "C510", "100n_0603_50V_X7R", 88.9, 45.72, "DRV_CP1", "DRV_CP2",
             purpose="charge pump flying cap, >= VM + 12 V")
    c511 = C(sh, "C511", "100n_0402_16V_X7R", 116.84, 45.72, "DRV_V5", "GND", purpose="V5 bypass")
    c512 = C(sh, "C512", "1u_0603_50V_X5R", 142.24, 45.72, "DRV_VINT", "GND", purpose="VINT bypass")
    c513 = C(sh, "C513", "1n_0402_50V_C0G", 167.64, 45.72, "DRV_BEMF", "GND", purpose="BEMF 1 nF low leakage")
    sh.nets(c507, {"1": "VBAT", "2": "GND"})
    sh.rail("VBAT", 38.1, [c507["1"], c508["1"], c509["2"]], tap=(22.86, (0, -1)))
    sh.rail("GND", 55.88, [c507["2"], c508["2"]], tap=(40.64, (0, 1)))
    sh.note(20.32, 63.5, [
        "VM (pin 4): C507 220 uF bulk (>= 100 uF, 600 mA ripple) + C508 10 nF at the pin.  VCP: C509 1 uF to VM.",
        "CP1-CP2: C510 100 nF, >= VM + 12 V.  V5 100 nF, VINT 1 uF, BEMF 1 nF C0G (SLVSC40 p.3-4)."])

    pulls = [R(sh, "R515", "10k", 33.02, 177.8, "DRV_NFAULT", "+3V3", rot=180, purpose="nFAULT open-drain pull-up"),
             R(sh, "R516", "10k", 55.88, 177.8, "DRV_NSTALL", "+3V3", rot=180, purpose="nSTALL open-drain pull-up"),
             R(sh, "R517", "2.2k", 78.74, 177.8, "SPI1_MISO", "+3V3", rot=180,
               purpose="SDATO open-drain pull-up on the shared MISO")]
    sh.rail("+3V3", 170.18, [p["2"] for p in pulls], tap=(22.86, (0, -1)))
    R(sh, "R518", "10k", 109.22, 177.8, "DRV_NSLEEP", "GND", purpose="sleep while the MCU is in reset (no internal pull)")
    sh.note(20.32, 203.2, [
        "nFAULT, nSTALL: open drain, 10k to +3V3.  SDATO is open drain on the shared MISO: 2.2k (tau ~66 ns, SPI <= 4 MHz).",
        "nSLEEP: 10k pull-down, no internal pull, so the driver sleeps while the MCU is in reset (SLVSC40 p.3).",
        "PWMMODE 1: TIM1 drives AIN1/AIN2/BIN1/BIN2 directly (indexer bypassed).  Firmware: IDRIVE 00,",
        "TBLANK >= 1.2 us, SCLK <= 4 MHz, SCS active high.  Trip 2.0 A: ISGAIN 20, TORQUE 186 (D-027, S0)."])

    bridge_box(sh, "A", "left", 20.32, {"h1": ("R501", "R502", "Q501", "D501"), "h2": ("R503", "R504", "Q502", "D502"),
                                        "bulk": "C502", "hf": "C503",
                                        "sense": ("R509", "NT501", "R510", "R511", "C501")})
    bridge_box(sh, "B", "right", 134.62, {"h1": ("R505", "R506", "Q503", "D503"), "h2": ("R507", "R508", "Q504", "D504"),
                                          "bulk": "C505", "hf": "C506",
                                          "sense": ("R512", "NT502", "R513", "R514", "C504")})
    return sh
