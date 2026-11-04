"""Sheet 4: RF path: RF1 -> MLPF-WB55-01E3 -> 50 ohm -> DNP pi tuning -> printed IFA; DNP U.FL test port.

Sources: DS12804 (MLPF), rf-layout skill s3 (tuning footprint, conducted test port), D-007.
"""

from parts import C, R, nobom
from schematic import Part, Sheet


def build(values):
    sheet = Sheet(4, "rf", "2.4 GHz RF path and antenna")
    sheet.add(Part(sheet.next_ref("FL"), "e-inverted-pendulum:MLPF-WB55-01E3", "MLPF-WB55-01E3",
                   {"A3": "RF1", "A1": "RF_50", "A2": "GND", "B1": "GND", "B2": "GND", "B3": "GND"},
                   footprint="e-inverted-pendulum:ST_MLPF-WB55-01E3", lcsc="C2651048", mpn="MLPF-WB55-01E3",
                   fields={"Purpose": "IN (A3) 1.5 mm from RF1 per DS12804 Fig. 13"}))
    C(sheet, "100p_0402_50V_C0G", "RF_50", "GND", dnp=True, purpose="pi shunt 1 (tune with VNA)")
    R(sheet, "0", "RF_50", "RF_ANT", package="0402", purpose="pi series element; remove to use the U.FL")
    C(sheet, "100p_0402_50V_C0G", "RF_ANT", "GND", dnp=True, purpose="pi shunt 2 (tune with VNA)")
    R(sheet, "0", "RF_50", "RF_UFL", package="0402", dnp=True, purpose="fit (and remove the series 0R) for conducted tests")
    sheet.add(Part(sheet.next_ref("J"), "Connector:Conn_Coaxial", "U.FL", {"1": "RF_UFL", "2": "GND"},
                   footprint="Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", lcsc="C5137195",
                   mpn="BWU.FL-IPEX1", dnp=True, fields={"Purpose": "conducted test port, DNP in production"}))
    nobom(sheet, "AE", "Device:Antenna_Shield", "SWRA117D IFA", {"1": "RF_ANT", "2": "GND"},
          "RF_Antenna:Texas_SWRA117D_2.4GHz_Left", purpose="printed antenna (TI SWRA117D), keep-out on all layers")
    return sheet
