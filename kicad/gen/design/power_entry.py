"""Sheet 1: battery input, fuse, back-to-back P-FET switch (D-011), TVS, VBAT sense.

Sources: docs/design-calcs.md (Power path, VBAT sense); Littelfuse SMBJ p.2; AO4805 datasheet p.1-2.
"""

from parts import C, R, active, flag
from schematic import Part, Sheet


def build(values):
    sheet = Sheet(1, "power_entry", "Battery input and protection")
    sheet.add(Part(sheet.next_ref("J"), "Connector_Generic:Conn_01x02", "XT30 battery", {"1": "BAT_P", "2": "GND"},
                   footprint="e-inverted-pendulum:AMASS_XT30UPB-F_1x02_P5.00mm_Vertical", lcsc="C108769",
                   mpn="XT30UPB-F30.G.Y", fields={"Purpose": "3S LiPo input, pad 1 = +"}))
    active(sheet, "1206FA-4A", "Device:Fuse", {"1": "BAT_P", "2": "BAT_F"}, "Fuse:Fuse_1206_3216Metric", "F",
           value="4A fast", purpose="300 A @ 24 V breaking capacity")
    active(sheet, "AO4805", "Transistor_FET:Q_Dual_PMOS_S1G1S2G2D2D2D1D1",
           {"1": "PP_S", "2": "PP_G", "7": "BAT_F", "8": "BAT_F", "3": "PP_S", "4": "PP_G", "5": "VBAT", "6": "VBAT"},
           "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "Q",
           purpose="FET1 (D1 to battery) blocks reverse polarity; FET2 (D2 to VBAT) switches the load")
    R(sheet, "100k", "PP_G", "PP_S", purpose="gate off when the switch is open")
    active(sheet, "BZT52C15", "Device:D_Zener", {"1": "PP_S", "2": "PP_G"}, "Diode_SMD:D_SOD-123", "D",
           purpose="V_GS clamp 13.8-15.6 V < 20 V")
    R(sheet, "10k", "PP_G", "SW_ON", purpose="switch on: V_GS = -VBAT x 100k/110k")
    active(sheet, "SS-12D10L5", "Switch:SW_SPDT", {"1": "GND", "2": "SW_ON", "3": None},
           "e-inverted-pendulum:SW_Slide_SPDT_SS-12D10L5_P4.70mm", "SW", purpose="power switch (gate current only)")
    R(sheet, "1k", "PP_G", "PP_SS", purpose="Miller soft start series R")
    C(sheet, "220n_0603_25V_X7R", "PP_SS", "VBAT", purpose="Miller soft start: ~4.4 V/ms, ~1.2 A inrush")
    active(sheet, "SMBJ15A", "Device:D_Zener", {"1": "VBAT", "2": "GND"}, "Diode_SMD:D_SMB", "D",
           value="SMBJ15A", purpose="TVS after the FETs: V_RWM 15 V, V_C 24.4 V")
    R(sheet, "100k", "VBAT", "VBAT_SENSE", purpose="VBAT divider top (ratio 0.2126)")
    R(sheet, "27k", "VBAT_SENSE", "GND", purpose="VBAT divider bottom")
    C(sheet, "100n_0603_50V_X7R", "VBAT_SENSE", "GND", purpose="ADC charge bucket (>> 20 x 5 pF)")
    flag(sheet, "VBAT")
    flag(sheet, "GND")
    return sheet
