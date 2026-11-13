"""Sheet 4: RF path: RF1 -> MLPF-WB55-01E3 -> 50 ohm -> DNP pi tuning -> printed IFA; DNP U.FL test port.

Sources: DS12804 (MLPF), rf-layout skill s3 (tuning footprint, conducted test port), D-007, docs/rf.md.
"""

from parts import C, R, nobom
from sch import Sheet


def build(project, values):
    sh = Sheet(project, 4, "rf", "2.4 GHz RF path and antenna")
    sh.desc = ["RF1 -> MLPF-WB55-01E3 filter / match", "50 Ohm GCPW -> pi tuning (DNP shunts)",
               "Printed IFA (TI SWRA117D)", "DNP U.FL conducted test port"]

    sh.box(15.24, 20.32, 182.88, 134.62, "2.4 GHz RF path (DS12804, D-007, docs/rf.md)")
    fl = sh.part("e-inverted-pendulum:MLPF-WB55-01E3", "FL401", "MLPF-WB55-01E3", (60.96, 66.04),
                 fp="e-inverted-pendulum:ST_MLPF-WB55-01E3", lcsc="C2651048", mpn="MLPF-WB55-01E3",
                 Purpose="IN (A3) 1.5 mm from RF1 per DS12804 Fig. 13")
    fl.fpos = (-12.7, -12.7, "left")
    c401 = C(sh, "C401", "100p_0402_50V_C0G", 88.9, 66.04, "RF_50", "GND", dnp=True,
             purpose="pi shunt 1 (tune with VNA)")
    r401 = R(sh, "R401", "0", 106.68, 60.96, "RF_50", "RF_ANT", rot=90, package="0402",
             purpose="pi series element; remove to use the U.FL")
    c402 = C(sh, "C402", "100p_0402_50V_C0G", 124.46, 66.04, "RF_ANT", "GND", dnp=True,
             purpose="pi shunt 2 (tune with VNA)")
    ae = nobom(sh, "AE401", "Device:Antenna_Shield", "SWRA117D IFA", "RF_Antenna:Texas_SWRA117D_2.4GHz_Left",
               142.24, 55.88, purpose="printed antenna (TI SWRA117D), keep-out on all layers")
    ae.fpos = (5.08, -5.08, "left")
    r402 = R(sh, "R402", "0", 96.52, 76.2, "RF_50", "RF_UFL", package="0402", dnp=True,
             purpose="fit (and remove the series 0R) for conducted tests")
    j = sh.part("Connector:Conn_Coaxial", "J401", "U.FL", (114.3, 86.36), fp="Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical",
                lcsc="C5137195", mpn="BWU.FL-IPEX1", dnp=True, Purpose="conducted test port, DNP in production")
    j.fpos = (3.81, 1.27, "left")

    sh.rail("RF1", 60.96, [fl["A3"]], label="left", ext=7.62)
    sh.vrail("GND", 45.72, [fl["B3"], fl["B2"]], tap=(73.66, (0, 1)))
    sh.vrail("GND", 76.2, [fl["B1"], fl["A2"]], tap=(73.66, (0, 1)))
    sh.rail("RF_50", 60.96, [fl["A1"], c401["1"], r402["1"], r401["1"]])
    sh.rail("RF_ANT", 60.96, [r401["2"], c402["1"], ae["1"]])
    sh.net(ae["2"], "GND")
    sh.link(r402["2"], j["1"], "RF_UFL")
    sh.net(j["2"], "GND")
    sh.note(20.32, 99.06, [
        "RF1 (pin 31) -> FL401 MLPF-WB55-01E3: harmonic filter + match, IN 1.5 mm from RF1 (DS12804 Fig. 13).",
        "RF_50: 50 Ohm GCPW 0.27 / 0.15 mm on L1 over the solid L2 GND (scripts/gcpw.py, docs/rf.md).",
        "Pi tuning: C401 / C402 DNP, R401 0R; tune with a VNA at the antenna feed (rf-layout s3).",
        "Conducted test: fit R402, remove R401 -> J401 U.FL (DNP in production).",
        "Layout: L1 only, no vias on the line, via fence 1.0-1.3 mm; antenna keep-out on all layers;",
        "keep the SMPS (L301 / L302) away and orthogonal to the line."])
    return sh
