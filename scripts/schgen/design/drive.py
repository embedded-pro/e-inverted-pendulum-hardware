"""Sheet 5: DRV8711 driving two brushed motors through four CSD88537ND half-bridges.

The power stage is a copy of TI's BOOST-DRV8711 BoosterPack (SLVC575B design files, D-040): TI's parts, values and
land patterns, placed by scripts/pcb/drv_block.py from reference/boost-drv8711/boost_drv8711.json (D-063). Q502 / Q504 are wired as TI's
Q2 / Q4 (FET1 low side, FET2 high side), the Kelvin taps are TI's four net ties, and there are no gate or sense series
resistors. Kept on top of TI's circuit (owner, D-040): the SS34 phase clamps, the per-bridge 10 uF + 100 nF, the 1 nF
sense caps (not fitted) and the logic pulls. Sources: TI SLVSC40H (pin table, s6.1, s10), BOOST-DRV8711 schematic and
BOM, docs/design-calcs.md (DRV8711), S0 sizing (Rsense 50 mOhm, trip 2.0 A, D-027), docs/drive.md.
"""

from parts import C, R, active, nobom, test_points
from sch import Sheet

NFET = "Transistor_FET:Q_Dual_NMOS_S1G1S2G2D2D2D1D1"
TI = "e-inverted-pendulum:BOOST_"
DRV_NETS = {
    "8": "DRV_NSLEEP", "9": "DRV_RESET", "16": "DRV_SCS", "14": "SPI1_SCK_BUS", "15": "SPI1_MOSI",
    "17": "SPI1_MISO", "10": "DRV_AIN1", "11": "DRV_AIN2", "12": "DRV_BIN1", "13": "DRV_BIN2",
    "18": "DRV_NFAULT", "19": "DRV_NSTALL", "20": "DRV_BEMF", "6": "DRV_V5", "7": "DRV_VINT",
    "3": "DRV_VCP", "1": "DRV_CP1", "2": "DRV_CP2",
    "37": "MOT_R_P", "30": "MOT_R_N", "28": "MOT_L_P", "21": "MOT_L_N",
    "36": "A1HS", "35": "A1LS", "31": "A2HS", "32": "A2LS",
    "27": "B1HS", "26": "B1LS", "22": "B2HS", "23": "B2LS",
    "34": "DRV_AISENP", "33": "DRV_AISENN", "25": "DRV_BISENP", "24": "DRV_BISENN",
}
UNIT_PINS = {1: {"s": "1", "g": "2", "d": ("7", "8")}, 2: {"s": "3", "g": "4", "d": ("5", "6")}}


def half_bridge(sh, name, out, x, y, q, d, mirrored=False):
    """HS FET over LS FET at column x, gates labelled straight from the DRV8711 (no series R, as TI's board). Mirrored
    is TI's Q2 / Q4: FET1 (pins 1/2/7/8) is the low side and FET2 (3/4/5/6) the high side."""
    hs_unit, ls_unit = (2, 1) if mirrored else (1, 2)
    purpose = f"half-bridge {name}: FET{hs_unit} high side, FET{ls_unit} low side (BOOST-DRV8711)"
    hs = active(sh, q, "CSD88537ND", NFET, TI + "SO-8", x, y, unit=hs_unit, purpose=purpose)
    ls = active(sh, q, "CSD88537ND", NFET, TI + "SO-8", x, y + 17.78, unit=ls_unit, purpose=purpose)
    hs.fpos = (7.62, -2.54, "left")
    ls.fpos = (7.62, 2.54, "left")
    hp, lp = UNIT_PINS[hs_unit], UNIT_PINS[ls_unit]
    sh.net(hs[hp["g"]], f"{name}HS")
    sh.net(ls[lp["g"]], f"{name}LS")
    clamp = active(sh, d, "SS34", "Device:D_Schottky", "Diode_SMD:D_SMA", x + 25.4, y + 12.7, 270,
                   purpose="clamps the dead-time freewheel to -0.36 V (DRV8711 phase pin abs max -0.6 V, S2)")
    sh.net(clamp["2"], "GND")
    node = (hs[hp["s"]].x, y + 8.89)
    sh.vrail(out, hs[hp["s"]].x, [hs[hp["s"]], ls[lp["d"][0]], node])
    sh.link(ls[lp["d"][1]], ls[lp["d"][0]], out)
    sh.rail(out, y + 8.89, [node, clamp["1"]], label="right", ext=5.08)
    sh.link(hs[hp["d"][1]], hs[hp["d"][0]], "VBAT")
    return hs[hp["d"][0]], ls[lp["s"]]


def sense(sh, bridge, x, y, r_sense, nt_p, nt_n, c_f):
    """TI's Kelvin sense: Rsense from SENSE_x to GND, xISENP tied to its SENSE pad and xISENN to its GND pad by net ties
    (TI's NT1-NT4); our 1 nF across xISENP / xISENN, not fitted."""
    rs = active(sh, r_sense, "CRA2512-FZ-R050ELF", "Device:R", TI + "2512M", x, y + 7.62, value="50m",
                purpose=f"bridge {bridge} Rsense (BOOST-DRV8711 R1 / R2): the motor current flows straight through it")
    tie_p = nobom(sh, nt_p, "Device:NetTie_2", "NetTie", TI + "Net-Tie_10mil", x + 15.24, y, 180,
                  purpose=f"bridge {bridge} xISENP Kelvin tap at the Rsense SENSE pad (TI's net tie, bottom side)")
    tie_n = nobom(sh, nt_n, "Device:NetTie_2", "NetTie", TI + "Net-Tie_10mil", x + 15.24, y + 11.43, 180,
                  purpose=f"bridge {bridge} xISENN Kelvin tap at the Rsense GND pad (TI's net tie, bottom side)")
    tie_p.fpos = (0, -3.81, "left")
    tie_n.fpos = (0, 3.81, "left")
    sh.net(rs["2"], "GND")
    sh.net(tie_n["2"], "GND")
    cf = C(sh, c_f, "1n_0402_50V_C0G", x + 30.48, y + 5.715, f"DRV_{bridge}ISENP", f"DRV_{bridge}ISENN", dnp=True,
           purpose="optional sense filter across the DRV8711 inputs, not fitted (our extra, D-040)")
    sh.rail(f"DRV_{bridge}ISENP", y, [tie_p["1"], cf["1"]], label="right", ext=5.08)
    sh.rail(f"DRV_{bridge}ISENN", y + 11.43, [tie_n["1"], cf["2"]], label="right", ext=5.08)
    return rs, tie_p


def bridge_box(sh, bridge, motor, y0, refs):
    """One H-bridge: two half-bridges (the second mirrored, as TI's), bulk + HF caps on the drains, Rsense and TI's
    Kelvin net ties."""
    side = "L" if motor == "left" else "R"
    sh.box(205.74, y0, 405.13, y0 + 109.22, f"Bridge {bridge}: {motor} MG310 (MOT_{side}_P / MOT_{side}_N)")
    y = y0 + 30.48
    drain1, source1 = half_bridge(sh, f"{bridge}1", f"MOT_{side}_P", 243.84, y, *refs["h1"])
    drain2, source2 = half_bridge(sh, f"{bridge}2", f"MOT_{side}_N", 312.42, y, *refs["h2"], mirrored=True)
    bulk = C(sh, refs["bulk"], "10u_0805_25V_X5R", 358.14, y - 2.54, "VBAT", "GND",
             purpose=f"bridge {bridge} bulk at the HS drains (our extra, D-040)")
    hf = C(sh, refs["hf"], "100n_0603_50V_X7R", 373.38, y - 2.54, "VBAT", "GND",
           purpose=f"bridge {bridge} HF hot-loop cap (our extra, D-040)")
    sh.rail("VBAT", y - 10.16, [drain1, drain2, bulk["1"], hf["1"]], tap=(220.98, (0, -1)))
    sh.rail("GND", y + 7.62, [bulk["2"], hf["2"]], tap=(365.76, (0, 1)))
    rs, tie_p = sense(sh, bridge, 335.28, y + 27.94, *refs["sense"])
    sh.rail(f"SENSE_{bridge}", y + 27.94, [source1, source2, rs["1"], tie_p["2"]])
    q1, q2 = refs["h1"][0], refs["h2"][0]
    sh.note(210.82, y0 + 86.36, [
        f"BOOST-DRV8711 copy (D-040): {q1} FET1 high side, {q2} FET1 low side (TI's Q2 / Q4 wiring); gates straight from"
        " the DRV8711.",
        "SS34 from GND to each phase node: freewheel at -0.36 V, not the -0.73 V body diode (phase pins abs max -0.6 V, S2).",
        f"{refs['sense'][0]} 50 mOhm 2512: the motor current flows straight through it; Kelvin taps {refs['sense'][1]} /"
        f" {refs['sense'][2]} at its pads (TI's net ties).",
        f"{refs['sense'][3]} 1 nF not fitted.  {refs['bulk']} + {refs['hf']} at the HS drains: our extras on TI's layout."])


def build(project, values):
    sh = Sheet(project, 5, "drive", "Motor drive (DRV8711 + external FETs)")
    sh.desc = ["Copy of TI BOOST-DRV8711 (D-040), PWMMODE 1", "Four CSD88537ND half-bridges, SS34 clamps",
               "Rsense 50 mOhm 2512 + Kelvin net ties, trip 2.0 A", "VM bulk 220 uF, charge pump, pull-ups"]

    sh.box(15.24, 20.32, 200.66, 218.44, "DRV8711 gate driver (PWMMODE 1, D-002)")
    u = sh.part("e-inverted-pendulum:DRV8711", "U501", "DRV8711", (104.14, 116.84),
                fp=TI + "R-PDSO-G38", lcsc="C60013", mpn="DRV8711DCPR",
                Purpose="BOOST-DRV8711 U1; PWMMODE = 1 (indexer bypass), D-002")
    u.fpos = (-24.13, -34.29, "left")
    sh.nets(u, DRV_NETS)
    sh.vrail("GND", 77.47, [u["5"], u["29"], u["38"], u["39"]], tap=(147.32, (0, 1)))
    sh.vrail("VBAT", 130.81, [u["4"]], tap=(86.36, (0, -1)))

    c507 = active(sh, "C507", "EEEFK1V221P", "Device:C_Polarized", "Capacitor_SMD:CP_Elec_8x10", 33.02, 45.72,
                  value="220u 35V", purpose="VM bulk at BOOST-DRV8711 C1's spot (TI: 100 uF 100 V THT; SMD here, D-040)")
    c508 = C(sh, "C508", "10n_0603_100V_X7R", 48.26, 45.72, "VBAT", "GND", fp=TI + "0603L",
             purpose="BOOST-DRV8711 C2: VM 10 nF at the pin")
    c509 = C(sh, "C509", "1u_0805_50V_X7R", 63.5, 45.72, "DRV_VCP", "VBAT", rot=180, fp=TI + "0805L",
             purpose="BOOST-DRV8711 C4: VCP to VM 1 uF")
    c514 = C(sh, "C514", "1u_1206_100V_X7R", 76.2, 45.72, "VBAT", "GND", fp=TI + "1206L",
             purpose="BOOST-DRV8711 C8: VM 1 uF (TI's HMK316B7105KL-T not stocked; same 100 V X7R 1206)")
    c510 = C(sh, "C510", "100n_0603_100V_X7R", 88.9, 45.72, "DRV_CP1", "DRV_CP2", fp=TI + "0603L",
             purpose="BOOST-DRV8711 C3: charge pump flying cap 100 nF 100 V")
    c511 = C(sh, "C511", "100n_0603_25V_X7R", 116.84, 45.72, "DRV_V5", "GND", fp=TI + "0603L",
             purpose="BOOST-DRV8711 C5: V5 bypass 100 nF")
    c512 = C(sh, "C512", "1u_0603_16V_X7R", 142.24, 45.72, "DRV_VINT", "GND", fp=TI + "0603L",
             purpose="BOOST-DRV8711 C6: VINT bypass 1 uF")
    c513 = C(sh, "C513", "1n_0603_16V_X7R", 167.64, 45.72, "DRV_BEMF", "GND", fp=TI + "0603L",
             purpose="BOOST-DRV8711 C7: BEMF 1 nF")
    sh.nets(c507, {"1": "VBAT", "2": "GND"})
    sh.rail("VBAT", 38.1, [c507["1"], c508["1"], c509["2"], c514["1"]], tap=(22.86, (0, -1)))
    sh.rail("GND", 55.88, [c507["2"], c508["2"]], tap=(40.64, (0, 1)))
    sh.note(20.32, 63.5, [
        "BOOST-DRV8711 values and lands (D-040): VM C507 220 uF bulk at TI's C1 spot + C508 10 nF + C514 1 uF;",
        "VCP C509 1 uF to VM; CP1-CP2 C510 100 nF 100 V; V5 C511 100 nF; VINT C512 1 uF; BEMF C513 1 nF (SLVSC40H pin table)."])

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

    bridge_box(sh, "A", "right", 20.32, {"h1": ("Q501", "D501"), "h2": ("Q502", "D502"), "bulk": "C502", "hf": "C503",
                                        "sense": ("R509", "NT501", "NT503", "C501")})
    bridge_box(sh, "B", "left", 134.62, {"h1": ("Q503", "D503"), "h2": ("Q504", "D504"), "bulk": "C505", "hf": "C506",
                                          "sense": ("R512", "NT502", "NT504", "C504")})

    sh.box(15.24, 223.52, 200.66, 264.16, "Test points: motor current, phases, PWM, SPI")
    nets = ["SENSE_A", "SENSE_B", "MOT_L_P", "MOT_L_N", "MOT_R_P", "MOT_R_N", "DRV_AIN1", "DRV_AIN2", "DRV_BIN1",
            "DRV_BIN2", "DRV_NFAULT", "DRV_SCS", "SPI1_SCK_BUS", "SPI1_MOSI", "SPI1_MISO", "GND", "GND"]
    test_points(sh, 25.4, 254.0, [(f"TP{501 + i}", net) for i, net in enumerate(nets)], pitch=10.16)
    return sh
