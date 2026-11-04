"""Sheet 3: STM32WB55RGV6, supplies, SMPS, clocks, reset/boot, debug (STDC14).

Sources: DS11929 Rev 11 Fig. 16 (power scheme), Table 6 (SMPS parts), Table 16 note 6 (AT0/AT1),
section 3.7 (VDDUSB to VDD when unused); mcu-circuit-design skill sections 2-5.
Pin nets come from pin-data/pinmap.csv so the schematic can't drift from the validated pin map.
"""

import csv
import pathlib

from parts import C, R, active, flag
from schematic import Part, Sheet

ROOT = pathlib.Path(__file__).resolve().parents[3]
QFN68 = "Package_DFN_QFN:QFN-68-1EP_8x8mm_P0.4mm_EP6.4x6.4mm"


def pin_nets(values):
    with open(ROOT / "pin-data" / "pinmap.csv", encoding="utf-8") as handle:
        by_name = {row["pin"]: row["net"] for row in csv.DictReader(handle)}
    with open(ROOT / "pin-data" / "stm32wb55rgvx_vfqfpn68.csv", encoding="utf-8") as handle:
        package = list(csv.DictReader(handle))
    fixed = {
        "VBAT": "+3V3", "NRST": "NRST", "VREF+": "VDDA", "VDDA": "VDDA", "VDD": "+3V3", "RF1": "RF1",
        "VSSRF": "GND", "VDDRF": "+3V3", "OSC_OUT": "HSE_OUT", "OSC_IN": "HSE_IN", "AT0": None, "AT1": None,
        "VFBSMPS": "VFBSMPS", "VSSSMPS": "GND", "VLXSMPS": "SMPS_LX", "VDDSMPS": "+3V3", "VDDUSB": "+3V3",
        "VSS": "GND", "PC14": "OSC32_IN", "PC15": "OSC32_OUT",
    }
    nets = {}
    for row in package:
        name = row["name"]
        nets[row["number"]] = fixed[name] if name in fixed else by_name.get(name)
    return nets


def build(values):
    sheet = Sheet(3, "mcu", "MCU, clocks, supplies, debug")
    v = values
    active(sheet, "STM32WB55RGV6", "MCU_ST_STM32WB:STM32WB55RGVx", pin_nets(values), QFN68, "U",
           purpose="D-001")

    for pin_group in ("VDD pin 30", "VDD pin 45", "VDD pin 68", "VBAT pin 1", "VDDUSB pin 55"):
        C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose=f"{pin_group}: DS11929 Fig. 16")
    C(sheet, "4.7u_0402_10V_X5R", "+3V3", "GND", purpose="VDD bulk: DS11929 Fig. 16")
    C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose="VDDRF: DS11929 Fig. 16")
    C(sheet, "100p_0402_50V_C0G", "+3V3", "GND", purpose="VDDRF HF: DS11929 Fig. 16")
    C(sheet, "4.7u_0402_10V_X5R", "+3V3", "GND", purpose="VDDSMPS: DS11929 Fig. 16")

    sheet.add(Part(sheet.next_ref("FB"), "Device:FerriteBead_Small", "BLM18PG221SN1D", {"1": "+3V3", "2": "VDDA"},
                   footprint="Inductor_SMD:L_0603_1608Metric", lcsc=v["vdda_ferrite"]["lcsc"],
                   mpn="BLM18PG221SN1D", fields={"Purpose": "VDDA filter: mcu-circuit-design s2"}))
    C(sheet, "10n_0603_50V_X7R", "VDDA", "GND", purpose="VDDA: DS11929 Fig. 16")
    C(sheet, "1u_0603_50V_X5R", "VDDA", "GND", purpose="VDDA: DS11929 Fig. 16")
    C(sheet, "100n_0402_16V_X7R", "VDDA", "GND", purpose="VREF+: DS11929 Fig. 16")
    C(sheet, "1u_0603_50V_X5R", "VDDA", "GND", purpose="VREF+: DS11929 Fig. 16")

    sheet.add(Part(sheet.next_ref("L"), "Device:L", "10uH", {"1": "SMPS_LX", "2": "SMPS_MID"},
                   footprint="Inductor_SMD:L_0805_2012Metric", lcsc="C162582", mpn="LQM21FN100M80L",
                   fields={"Purpose": "SMPS L1, 4 MHz: DS11929 Table 6"}))
    sheet.add(Part(sheet.next_ref("L"), "Device:L", "10nH", {"1": "SMPS_MID", "2": "VFBSMPS"},
                   footprint="Inductor_SMD:L_0402_1005Metric", lcsc="C77103", mpn="LQG15HS10NJ02D",
                   fields={"Purpose": "series 10 nH for RX performance: DS11929 Table 6 note 2"}))
    C(sheet, "4.7u_0402_10V_X5R", "VFBSMPS", "GND", purpose="SMPS output C2: DS11929 Table 6")
    flag(sheet, "VDDA")
    flag(sheet, "SMPS_LX")

    sheet.add(Part(sheet.next_ref("Y"), "Device:Crystal_GND24", "32MHz",
                   {"1": "HSE_IN", "2": "GND", "3": "HSE_OUT", "4": "GND"},
                   footprint="Crystal:Crystal_SMD_2016-4Pin_2.0x1.6mm", lcsc="C5441424",
                   mpn="NX2016SA-32MHZ-EXS00A-CS06654",
                   fields={"Purpose": "HSE, internal load caps trimmed by HSETUNE (no external caps)"}))
    sheet.add(Part(sheet.next_ref("Y"), "Device:Crystal", "32.768kHz", {"1": "OSC32_IN", "2": "OSC32_OUT"},
                   footprint="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm", lcsc="C156244",
                   mpn="NX3215SA-32.768K-STD-MUA-14", fields={"Purpose": "LSE, C_L 6 pF"}))
    C(sheet, v["lse_cap"]["key"], "OSC32_IN", "GND", purpose=v["lse_cap"]["source"])
    C(sheet, v["lse_cap"]["key"], "OSC32_OUT", "GND", purpose=v["lse_cap"]["source"])

    C(sheet, "100n_0402_16V_X7R", "NRST", "GND", purpose="NRST: DS11929 Fig. 24 (0.1 uF close to the pin)")
    R(sheet, "33", "SPI1_SCK", "SPI1_SCK_BUS", purpose="SCK source termination, shared DRV8711 + flash bus (mcu-circuit-design s9)")
    R(sheet, "10k", "BOOT0", "GND", purpose="BOOT0 must not float: mcu-circuit-design s3")
    R(sheet, "1k", "BOOT0", "BOOT0_BTN", purpose="BOOT0 button series resistor")
    sheet.add(Part(sheet.next_ref("SW"), "Switch:SW_Push", "BOOT0", {"1": "+3V3", "2": "BOOT0_BTN"},
                   footprint=v["tact_footprint"], lcsc="C318884", mpn="TS-1187A-B-A-B",
                   fields={"Purpose": "hold at reset to enter the ROM bootloader"}))

    sheet.add(Part(sheet.next_ref("J"), "Connector:Conn_ST_STDC14", "STDC14",
                   {"1": None, "2": None, "3": "+3V3", "4": "SWDIO", "5": "GND", "6": "SWCLK", "7": "GND",
                    "8": None, "9": None, "10": None, "11": "GND", "12": "NRST", "13": "VCP_RX", "14": "VCP_TX"},
                   footprint=v["stdc14_footprint"], lcsc="C5307809", mpn="FTSH-107-01-L-DV-K",
                   fields={"Purpose": "D-009; SWO (pin 8) unused because PB3 is SPI1_SCK"}))
    return sheet
