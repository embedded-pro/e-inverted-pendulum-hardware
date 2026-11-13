"""Sheet 7: MPU-6500 IMU on SPI2 and W25Q16JV flash on SPI1.

Sources: PS-MPU-6500A-01 Table 10/11 p.19-20; W25Q16JV rev H s4, s6; docs/design-calcs.md.
"""

from parts import C, R, active
from sch import Sheet


def build(project, values):
    sh = Sheet(project, 7, "imu_flash", "IMU and SPI flash")
    sh.desc = ["MPU-6500 6-axis IMU on SPI2, INT to PC6", "W25Q16JV 16 Mbit flash on SPI1",
               "(shared with the DRV8711)"]

    sh.box(15.24, 20.32, 200.66, 165.1, "IMU: MPU-6500 on SPI2 (D-004)")
    c701 = C(sh, "C701", "100n_0402_16V_X7R", 30.48, 40.64, "+3V3", "GND", purpose="C2 VDD (Table 11)")
    c702 = C(sh, "C702", "10n_0603_50V_X7R", 45.72, 40.64, "+3V3", "GND", purpose="C3 VDDIO (Table 11)")
    c703 = C(sh, "C703", "100n_0402_16V_X7R", 83.82, 40.64, "IMU_REGOUT", "GND", purpose="C1 REGOUT (Table 11)")
    r701 = R(sh, "R701", "10k", 63.5, 40.64, "IMU_NCS", "+3V3", rot=180,
             purpose="nCS high before the MCU drives it (SDO high-Z, SPI mode)")
    for c, tag in ((c701, "VDD"), (c702, "VDDIO"), (c703, "REGOUT")):
        sh.text(tag, (c.x - 2.54, 55.88))
    sh.rail("+3V3", 33.02, [c701["1"], c702["1"], r701["2"]], tap=(22.86, (0, -1)))
    sh.rail("GND", 50.8, [c701["2"], c702["2"]], tap=(38.1, (0, 1)))
    sh.rail("IMU_REGOUT", 33.02, [c703["1"]], label="right", ext=5.08)
    u = sh.part("e-inverted-pendulum:MPU-6500", "U701", "MPU-6500", (127.0, 101.6),
                fp="Sensor_Motion:InvenSense_QFN-24_3x3mm_P0.4mm", lcsc="C50278", mpn="MPU-6500",
                Purpose="D-004; rigid, beside the MCU, axes aligned to the body frame (HW-SNS-002, D-029)")
    u.fpos = (-17.78, -24.13, "left")
    sh.vrail("+3V3", 106.68, [u["13"], u["8"]], tap=(81.28, (0, -1)))
    sh.nets(u, {"10": "IMU_REGOUT", "22": "IMU_NCS", "23": "IMU_SCK", "24": "IMU_MOSI", "9": "IMU_MISO", "11": "GND",
                "12": "IMU_INT", "7": None, "21": None})
    sh.vrail("GND", 106.68, [u["18"], u["20"]], tap=(119.38, (0, 1)))
    sh.note(20.32, 132.08, [
        "SPI2: PB13 SCK, PB15 MOSI, PB14 MISO, PB12 nCS (GPIO); INT to PC6 (EXTI6, data ready).",
        "Decoupling per PS-MPU-6500A-01 Table 11: C1 100 nF REGOUT, C2 100 nF VDD, C3 10 nF VDDIO.",
        "R701 holds nCS high until the MCU drives it: SDO stays high-Z and the part stays in SPI mode.",
        "FSYNC unused, tied to GND (Table 10); AUX_DA / AUX_CL unconnected.",
        "Mount rigidly beside the MCU, ~90 mm above the axle, axes x forward / y left / z up (HW-SNS-002, D-029)."])

    sh.box(205.74, 20.32, 405.13, 165.1, "SPI flash: W25Q16JV on SPI1 (D-005)")
    f = active(sh, "U702", "W25Q16JVSSIQ", "Memory_Flash:W25Q16JVSS", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm",
               327.66, 93.98, purpose="D-005; QE = 1 on the IQ variant")
    f.fpos = (5.08, -15.24, "left")
    r702 = R(sh, "R702", "10k", 303.53, 78.74, "FLASH_NCS", "+3V3", rot=180, purpose="/CS tracks VCC at power-up (s10.3)")
    r703 = R(sh, "R703", "10k", 278.13, 78.74, "FLASH_WP", "+3V3", rot=180, purpose="IO2 defined")
    r704 = R(sh, "R704", "10k", 265.43, 78.74, "FLASH_HOLD", "+3V3", rot=180, purpose="IO3 defined")
    c704 = C(sh, "C704", "100n_0402_16V_X7R", 345.44, 88.9, "+3V3", "GND", purpose="flash bypass")
    sh.nets(f, {"6": "SPI1_SCK_BUS", "5": "SPI1_MOSI", "2": "SPI1_MISO"})
    sh.rail("FLASH_NCS", 86.36, [r702["1"], f["1"]], label="left", ext=5.08)
    sh.path("FLASH_WP", [f["3"], (278.13, 96.52), r703["1"]])
    sh.path("FLASH_HOLD", [f["7"], (265.43, 99.06), r704["1"]])
    sh.label("FLASH_WP", (280.67, 96.52))
    sh.label("FLASH_HOLD", (267.97, 99.06))
    sh.rail("+3V3", 68.58, [r704["2"], r703["2"], r702["2"], f["8"], c704["1"]], tap=(337.82, (0, -1)))
    sh.rail("GND", 111.76, [f["4"], c704["2"]], tap=(337.82, (0, 1)))
    sh.note(210.82, 132.08, [
        "W25Q16JVSSIQ, 16 Mbit: SPI1 shared with the DRV8711 (SCK through R301 on the MCU sheet), /CS on PA15.",
        "R702 keeps /CS at VCC through power-up (s10.3).  /WP and /HOLD pulled up so IO2 / IO3 are defined;",
        "the IQ variant ships with QE = 1."])
    return sh
