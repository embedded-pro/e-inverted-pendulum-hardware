"""Sheet 5: DRV8711 driving two brushed motors through four CSD88537ND half-bridges.

Sources: TI SLVSC40 (pin table p.3-4, critical components p.4, sense p.16), docs/design-calcs.md (DRV8711),
S0 sizing (Rsense 50 mOhm, trip 1.3 A), power-pcb-layout s3.
"""

from parts import C, R, active, nobom
from schematic import Part, Sheet

BRIDGES = (
    ("A", "1", "MOT_L_P"), ("A", "2", "MOT_L_N"),
    ("B", "1", "MOT_R_P"), ("B", "2", "MOT_R_N"),
)


def build(values):
    sheet = Sheet(5, "drive", "Motor drive (DRV8711 + external FETs)")
    nets = {
        "8": "DRV_NSLEEP", "9": "DRV_RESET", "16": "DRV_SCS", "14": "SPI1_SCK_BUS", "15": "SPI1_MOSI",
        "17": "SPI1_MISO", "10": "DRV_AIN1", "11": "DRV_AIN2", "12": "DRV_BIN1", "13": "DRV_BIN2",
        "18": "DRV_NFAULT", "19": "DRV_NSTALL", "20": "DRV_BEMF", "6": "DRV_V5", "7": "DRV_VINT",
        "5": "GND", "29": "GND", "38": "GND", "39": "GND",
        "4": "VBAT", "3": "DRV_VCP", "1": "DRV_CP1", "2": "DRV_CP2",
        "37": "MOT_L_P", "30": "MOT_L_N", "28": "MOT_R_P", "21": "MOT_R_N",
        "36": "A1HS_D", "35": "A1LS_D", "31": "A2HS_D", "32": "A2LS_D",
        "27": "B1HS_D", "26": "B1LS_D", "22": "B2HS_D", "23": "B2LS_D",
        "34": "DRV_AISENP", "33": "DRV_AISENN", "25": "DRV_BISENP", "24": "DRV_BISENN",
    }
    sheet.add(Part(sheet.next_ref("U"), "e-inverted-pendulum:DRV8711", "DRV8711", nets,
                   footprint="Package_SO:HTSSOP-38-1EP_4.4x9.7mm_P0.5mm_EP2.74x4.75mm_ThermalVias",
                   lcsc="C60013", mpn="DRV8711DCPR", fields={"Purpose": "PWMMODE = 1 (indexer bypass), D-002"}))

    for bridge, leg, out in BRIDGES:
        name = f"{bridge}{leg}"
        R(sheet, "0", f"{name}HS_D", f"{name}HS_G", purpose=f"{name} high-side gate R (at the FET)")
        R(sheet, "0", f"{name}LS_D", f"{name}LS_G", purpose=f"{name} low-side gate R (at the FET)")
        active(sheet, "CSD88537ND", "Transistor_FET:Q_Dual_NMOS_S1G1S2G2D2D2D1D1",
               {"7": "VBAT", "8": "VBAT", "1": out, "2": f"{name}HS_G",
                "5": out, "6": out, "3": f"SENSE_{bridge}", "4": f"{name}LS_G"},
               "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Q",
               purpose=f"half-bridge {name}: FET1 high side, FET2 low side")

    for bridge in ("A", "B"):
        active(sheet, "HoLR1206-1W-50mR-1%-75ppm", "Device:R", {"1": f"SENSE_{bridge}", "2": "GND"},
               "Resistor_SMD:R_1206_3216Metric", "R", value="50m",
               purpose=f"bridge {bridge} Rsense, Kelvin taps from the inner pad edges")
        nobom(sheet, "NT", "Device:NetTie_2", "NetTie", {"1": f"KELVIN_{bridge}N", "2": "GND"},
              "NetTie:NetTie-2_SMD_Pad0.5mm", purpose=f"bridge {bridge} xISENN Kelvin tap at the Rsense ground pad")
        R(sheet, "0", f"SENSE_{bridge}", f"DRV_{bridge}ISENP", purpose="sense filter leg (27-33 R if fitted)")
        R(sheet, "0", f"KELVIN_{bridge}N", f"DRV_{bridge}ISENN", purpose="sense filter leg (matched)")
        C(sheet, "1n_0402_50V_C0G", f"DRV_{bridge}ISENP", f"DRV_{bridge}ISENN", dnp=True,
          purpose="optional sense filter, RC 50-60 ns (SLVSC40 Fig. 6)")
        C(sheet, "10u_0805_25V_X5R", "VBAT", "GND", purpose=f"bridge {bridge} bulk at the HS drains")
        C(sheet, "100n_0603_50V_X7R", "VBAT", "GND", purpose=f"bridge {bridge} HF hot-loop cap")

    active(sheet, "EEEFK1V221P", "Device:C_Polarized", {"1": "VBAT", "2": "GND"}, "Capacitor_SMD:CP_Elec_8x10", "C",
           value="220u 35V", purpose="VM bulk (>= 100 uF per SLVSC40), 600 mA ripple rating")
    C(sheet, "10n_0603_50V_X7R", "VBAT", "GND", purpose="VM ceramic 0.01 uF at the pin")
    C(sheet, "1u_0603_50V_X5R", "DRV_VCP", "VBAT", purpose="VCP to VM, 1 uF >= 16 V")
    C(sheet, "100n_0603_50V_X7R", "DRV_CP1", "DRV_CP2", purpose="charge pump flying cap, >= VM + 12 V")
    C(sheet, "100n_0402_16V_X7R", "DRV_V5", "GND", purpose="V5 bypass")
    C(sheet, "1u_0603_50V_X5R", "DRV_VINT", "GND", purpose="VINT bypass")
    C(sheet, "1n_0402_50V_C0G", "DRV_BEMF", "GND", purpose="BEMF 1 nF low leakage")
    R(sheet, "10k", "DRV_NFAULT", "+3V3", purpose="nFAULT open-drain pull-up")
    R(sheet, "10k", "DRV_NSTALL", "+3V3", purpose="nSTALL open-drain pull-up")
    R(sheet, "2.2k", "SPI1_MISO", "+3V3", purpose="SDATO open-drain pull-up on the shared MISO")
    R(sheet, "10k", "DRV_NSLEEP", "GND", purpose="sleep while the MCU is in reset (no internal pull)")
    return sheet
