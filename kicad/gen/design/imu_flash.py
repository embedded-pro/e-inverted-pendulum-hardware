"""Sheet 7: MPU-6500 IMU on SPI2 and W25Q16JV flash on SPI1.

Sources: PS-MPU-6500A-01 Table 10/11 p.19-20; W25Q16JV rev H s4, s6; docs/design-calcs.md.
"""

from parts import C, R, active
from schematic import Part, Sheet


def build(values):
    sheet = Sheet(7, "imu_flash", "IMU and SPI flash")
    sheet.add(Part(sheet.next_ref("U"), "e-inverted-pendulum:MPU-6500", "MPU-6500",
                   {"13": "+3V3", "8": "+3V3", "10": "IMU_REGOUT", "22": "IMU_NCS", "23": "IMU_SCK",
                    "24": "IMU_MOSI", "9": "IMU_MISO", "11": "GND", "12": "IMU_INT", "18": "GND", "20": "GND",
                    "7": None, "21": None},
                   footprint="Sensor_Motion:InvenSense_QFN-24_3x3mm_P0.4mm", lcsc="C50278", mpn="MPU-6500",
                   fields={"Purpose": "D-004; mount on the sagittal centreline near the axle (HW-SNS-002)"}))
    C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose="C2 VDD (Table 11)")
    C(sheet, "10n_0603_50V_X7R", "+3V3", "GND", purpose="C3 VDDIO (Table 11)")
    C(sheet, "100n_0402_16V_X7R", "IMU_REGOUT", "GND", purpose="C1 REGOUT (Table 11)")
    R(sheet, "10k", "IMU_NCS", "+3V3", purpose="nCS high before the MCU drives it (SDO high-Z, SPI mode)")
    active(sheet, "W25Q16JVSSIQ", "Memory_Flash:W25Q16JVSS",
           {"1": "FLASH_NCS", "2": "SPI1_MISO", "3": "FLASH_WP", "4": "GND", "5": "SPI1_MOSI", "6": "SPI1_SCK_BUS",
            "7": "FLASH_HOLD", "8": "+3V3"}, "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", "U",
           purpose="D-005; QE = 1 on the IQ variant")
    C(sheet, "100n_0402_16V_X7R", "+3V3", "GND", purpose="flash bypass")
    R(sheet, "10k", "FLASH_NCS", "+3V3", purpose="/CS tracks VCC at power-up (s10.3)")
    R(sheet, "10k", "FLASH_WP", "+3V3", purpose="IO2 defined")
    R(sheet, "10k", "FLASH_HOLD", "+3V3", purpose="IO3 defined")
    return sheet
