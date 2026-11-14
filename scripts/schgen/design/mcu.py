"""Sheet 3: STM32WB55RGV6, supplies, SMPS, clocks, reset/boot, debug (STDC14).

Sources: DS11929 Rev 11 Fig. 16 (power scheme), Table 6 (SMPS parts), Table 16 note 6 (AT0/AT1),
section 3.7 (VDDUSB to VDD when unused); mcu-circuit-design skill sections 2-5.
Pin nets come from pin-data/pinmap.csv so the schematic can't drift from the validated pin map.
"""

import csv
import pathlib

from parts import C, R, active, test_points
from sch import Sheet

ROOT = pathlib.Path(__file__).resolve().parents[3]
QFN68 = "Package_DFN_QFN:QFN-68-1EP_8x8mm_P0.4mm_EP6.4x6.4mm"


def pin_map():
    with open(ROOT / "pin-data" / "pinmap.csv", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def pin_nets():
    by_name = {row["pin"]: row["net"] for row in pin_map()}
    with open(ROOT / "pin-data" / "stm32wb55rgvx_vfqfpn68.csv", encoding="utf-8") as handle:
        package = list(csv.DictReader(handle))
    fixed = {
        "VBAT": "+3V3", "NRST": "NRST", "VREF+": "VDDA", "VDDA": "VDDA", "VDD": "+3V3", "RF1": "RF1",
        "VSSRF": "GND", "VDDRF": "+3V3", "OSC_OUT": "HSE_OUT", "OSC_IN": "HSE_IN", "AT0": None, "AT1": None,
        "VFBSMPS": "VFBSMPS", "VSSSMPS": "GND", "VLXSMPS": "SMPS_LX", "VDDSMPS": "+3V3", "VDDUSB": "+3V3",
        "VSS": "GND", "PC14": "OSC32_IN", "PC15": "OSC32_OUT",
    }
    return {row["number"]: fixed[row["name"]] if row["name"] in fixed else by_name.get(row["name"])
            for row in package}


def build(project, values):
    v = values
    sh = Sheet(project, 3, "mcu", "MCU, clocks, supplies, debug")
    sh.desc = ["STM32WB55RGV6 (BLE 5), pin map from", "pin-data/pinmap.csv; core SMPS, HSE 32 MHz,",
               "LSE 32.768 kHz, NRST / BOOT0 pads,", "STDC14 SWD + virtual COM port"]

    sh.box(15.24, 20.32, 284.48, 76.2, "Supplies and decoupling (DS11929 Fig. 16)")
    decoupling = [
        ("C301", "100n_0402_16V_X7R", "VDD pin 30", "VDD 30"), ("C302", "100n_0402_16V_X7R", "VDD pin 45", "VDD 45"),
        ("C303", "100n_0402_16V_X7R", "VDD pin 68", "VDD 68"), ("C304", "100n_0402_16V_X7R", "VBAT pin 1", "VBAT 1"),
        ("C305", "100n_0402_16V_X7R", "VDDUSB pin 55", "VDDUSB 55"), ("C306", "4.7u_0402_10V_X5R", "VDD bulk", "VDD bulk"),
        ("C307", "100n_0402_16V_X7R", "VDDRF", "VDDRF 33"), ("C308", "100p_0402_50V_C0G", "VDDRF HF", "VDDRF 33"),
        ("C309", "4.7u_0402_10V_X5R", "VDDSMPS", "VDDSMPS 44"),
    ]
    caps = []
    for i, (ref, key, purpose, tag) in enumerate(decoupling):
        x = 30.48 + 15.24 * i
        caps.append(C(sh, ref, key, x, 40.64, "+3V3", "GND", purpose=f"{purpose}: DS11929 Fig. 16"))
        sh.text(tag, (x - 2.54, 55.88))
    fb = sh.part("Device:FerriteBead_Small", "FB301", "BLM18PG221SN1D", (167.64, 33.02), 90,
                 fp="Inductor_SMD:L_0603_1608Metric", lcsc=v["vdda_ferrite"]["lcsc"], mpn="BLM18PG221SN1D",
                 Purpose="VDDA filter: mcu-circuit-design s2")
    fb.fpos = (-3.81, -3.81, "left")
    analog = [C(sh, "C310", "10n_0603_50V_X7R", 182.88, 40.64, "VDDA", "GND", purpose="VDDA: DS11929 Fig. 16"),
              C(sh, "C311", "1u_0603_50V_X5R", 198.12, 40.64, "VDDA", "GND", purpose="VDDA: DS11929 Fig. 16"),
              C(sh, "C312", "100n_0402_16V_X7R", 213.36, 40.64, "VDDA", "GND", purpose="VREF+: DS11929 Fig. 16"),
              C(sh, "C313", "1u_0603_50V_X5R", 228.6, 40.64, "VDDA", "GND", purpose="VREF+: DS11929 Fig. 16")]
    for c, tag in zip(analog, ("VDDA 14", "VDDA 14", "VREF+ 13", "VREF+ 13")):
        sh.text(tag, (c.x - 2.54, 55.88))
    fa = sh.flag("VDDA", (241.3, 33.02), label=False)
    sh.rail("+3V3", 33.02, [c["1"] for c in caps] + [fb["1"]], tap=(22.86, (0, -1)))
    sh.rail("VDDA", 33.02, [fb["2"]] + [c["1"] for c in analog] + [fa["1"]], tap=(248.92, (0, -1)))
    sh.rail("GND", 50.8, [c["2"] for c in caps + analog], tap=(167.64, (0, 1)))
    sh.note(20.32, 60.96, [
        "One 100 nF per supply pin, at the pin, each with its own via; 4.7 uF bulk on VDD.  VDDRF 100 nF + 100 pF at pin 33.",
        "VDDA and VREF+ through FB301: 10 nF + 1 uF on VDDA, 100 nF + 1 uF on VREF+ (mcu-circuit-design s2).",
        "VDDUSB to VDD: USB unused (DS11929 s3.7).  VBAT to VDD: no backup domain battery."])

    sh.box(157.48, 81.28, 284.48, 200.66, "STM32WB55RGV6 (UFQFPN-68)")
    u = active(sh, "U301", "STM32WB55RGV6", "MCU_ST_STM32WB:STM32WB55RGVx", QFN68, 220.98, 139.7, purpose="D-001")
    u.fpos = (-22.86, -53.34, "left")
    sh.nets(u, pin_nets())

    sh.box(15.24, 81.28, 152.4, 124.46, "Core SMPS (DS11929 Table 6)")
    l301 = sh.part("Device:L", "L301", "10uH", (50.8, 96.52), 90, fp="Inductor_SMD:L_0805_2012Metric", lcsc="C162582",
                   mpn="LQM21FN100M80L", Purpose="SMPS L1, 4 MHz: DS11929 Table 6")
    l302 = sh.part("Device:L", "L302", "10nH", (71.12, 96.52), 90, fp="Inductor_SMD:L_0402_1005Metric", lcsc="C77103",
                   mpn="LQG15HS10NJ02D", Purpose="series 10 nH for RX performance: DS11929 Table 6 note 2")
    c314 = C(sh, "C314", "4.7u_0402_10V_X5R", 88.9, 102.87, "VFBSMPS", "GND", purpose="SMPS output C2: DS11929 Table 6")
    fl = sh.flag("SMPS_LX", (38.1, 96.52), label=False)
    sh.rail("SMPS_LX", 96.52, [fl["1"], l301["1"]], label="left", ext=7.62)
    sh.link(l301["2"], l302["1"], "SMPS_MID")
    sh.rail("VFBSMPS", 96.52, [l302["2"], c314["1"]], label="right", ext=7.62)
    sh.net(c314["2"], "GND")
    sh.note(20.32, 114.3, [
        "L301 10 uH + L302 10 nH (RX performance) + C314 4.7 uF: DS11929 Table 6.",
        "L301 / L302 at pins 41-44, small loop, orthogonal to the RF line (docs/rf.md)."])

    sh.box(15.24, 129.54, 152.4, 180.34, "Clocks: HSE 32 MHz, LSE 32.768 kHz")
    hse = sh.part("Device:Crystal_GND24", "Y301", "32MHz", (38.1, 147.32), fp="Crystal:Crystal_SMD_2016-4Pin_2.0x1.6mm",
                  lcsc="C5441424", mpn="NX2016SA-32MHZ-EXS00A-CS06654",
                  Purpose="HSE, internal load caps trimmed by HSETUNE (no external caps)")
    hse.fpos = (-3.81, -7.62, "left")
    sh.nets(hse, {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"})
    lse = sh.part("Device:Crystal", "Y302", "32.768kHz", (101.6, 144.78), fp="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm",
                  lcsc="C156244", mpn="NX3215SA-32.768K-STD-MUA-14", Purpose="LSE, C_L 6 pF")
    lse.fpos = (-3.81, -7.62, "left")
    c315 = C(sh, "C315", v["lse_cap"]["key"], 88.9, 152.4, "OSC32_IN", "GND", purpose=v["lse_cap"]["source"])
    c316 = C(sh, "C316", v["lse_cap"]["key"], 114.3, 152.4, "OSC32_OUT", "GND", purpose=v["lse_cap"]["source"])
    sh.rail("OSC32_IN", 144.78, [c315["1"], lse["1"]], label="left", ext=7.62)
    sh.rail("OSC32_OUT", 144.78, [lse["2"], c316["1"]], label="right", ext=7.62)
    sh.rail("GND", 160.02, [c315["2"], c316["2"]], tap=(101.6, (0, 1)))
    sh.note(20.32, 165.1, [
        "HSE NX2016SA: no external caps, load trimmed by HSETUNE (DS11929 Table 5 note 1).",
        "LSE NX3215SA, C_L 6 pF: 2 x 6.8 pF C0G (AN2867); LSEDRV = 10, margin ~2.5 (Table 54)."])

    sh.box(15.24, 185.42, 152.4, 243.84, "Reset, boot and SPI1 clock termination")
    c317 = C(sh, "C317", "100n_0402_16V_X7R", 30.48, 204.47, "NRST", "GND",
             purpose="NRST: DS11929 Fig. 24 (0.1 uF close to the pin)")
    sh.rail("NRST", 198.12, [c317["1"]], label="left", ext=7.62)
    r302 = R(sh, "R302", "10k", 58.42, 204.47, "BOOT0", "GND", purpose="BOOT0 must not float: mcu-circuit-design s3")
    sh.rail("BOOT0", 198.12, [r302["1"]], label="left", ext=7.62)
    r301 = R(sh, "R301", "33", 132.08, 198.12, "SPI1_SCK", "SPI1_SCK_BUS", rot=90,
             purpose="SCK source termination, shared DRV8711 + flash bus (mcu-circuit-design s9)")
    sh.rail("SPI1_SCK", 198.12, [r301["1"]], label="left", ext=7.62)
    sh.rail("SPI1_SCK_BUS", 198.12, [r301["2"]], label="right", ext=2.54)
    sh.note(20.32, 220.98, [
        "NRST: 100 nF at the pin (DS11929 Fig. 24); the STDC14 probe drives it too.",
        "BOOT0 (PH3): 10k pull-down, no button (D-035): TP302 to +3V3 at reset, or the boot option bytes over SWD.",
        "R301 33 Ohm at PB3: source termination of the SCK shared by the DRV8711 and the flash (s9)."])

    sh.box(289.56, 20.32, 405.13, 106.68, "Debug and virtual COM port: STDC14 (D-009)")
    j = sh.part("Connector:Conn_ST_STDC14", "J301", "STDC14", (325.12, 60.96), fp=v["stdc14_footprint"], lcsc="C5307809",
                mpn="FTSH-107-01-L-DV-K", Purpose="D-009; SWO (pin 8) unused because PB3 is SPI1_SCK")
    sh.nets(j, {"1": None, "2": None, "3": "+3V3", "4": "SWDIO", "5": "GND", "6": "SWCLK", "7": "GND", "8": None,
                "9": None, "10": None, "11": "GND", "12": "NRST", "13": "VCP_RX", "14": "VCP_TX"})
    sh.note(294.64, 88.9, [
        "STLINK-V3 STDC14 (1.27 mm): SWD + virtual COM port on USART1 (PB6 TX, PB7 RX).",
        "SWO (pin 8) unused: PB3 is SPI1_SCK.  Pin 3 is the target VCC reference for the probe."])

    sh.box(157.48, 205.74, 284.48, 246.38, "Test points")
    test_points(sh, 172.72, 233.68, [("TP301", "NRST"), ("TP302", "BOOT0"), ("TP303", "VDDA"), ("TP304", "VFBSMPS")],
                pitch=25.4)

    sh.box(289.56, 111.76, 405.13, 246.38, "Pin plan (pin-data/pinmap.csv, checked by scripts/check_pinmap.py)")
    rows = pin_map()
    half = (len(rows) + 1) // 2
    for x0, chunk in ((294.64, rows[:half]), (350.52, rows[half:])):
        for dx, key in ((0, "pin"), (8.89, "function"), (31.75, "net")):
            sh.note(x0 + dx, 119.38, [r[key] for r in chunk])
    return sh
