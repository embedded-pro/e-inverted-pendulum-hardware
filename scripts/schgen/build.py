#!/usr/bin/env python3
"""Build the hierarchical KiCad 10 schematic from scripts/schgen/design/*.py into hardware/e-inverted-pendulum/.

Usage: python3 scripts/schgen/build.py
"""

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "design"))

from schematic import Builder  # noqa: E402
import drive, imu_flash, logic_power, mcu, motors_encoders, power_entry, rf, ui  # noqa: E402,E401

OUT = HERE.parents[1] / "hardware" / "e-inverted-pendulum"
TITLE = "e-inverted-pendulum chassis PCB"


def main():
    values = json.loads((HERE / "values.json").read_text(encoding="utf-8"))
    sheets = [module.build(values) for module in (power_entry, logic_power, mcu, rf, drive, motors_encoders,
                                                   imu_flash, ui)]
    builder = Builder(sheets, TITLE)
    problems = builder.problems()
    for problem in problems:
        print("PROBLEM", problem)
    if problems:
        sys.exit(1)
    builder.write(OUT)
    for path in sorted(OUT.glob("*.kicad_sch")):
        subprocess.run(["kicad-cli", "sch", "upgrade", "--force", str(path)], check=True, capture_output=True)
    count = sum(len(s.parts) for s in sheets)
    print(f"wrote {len(sheets)} sheets, {count} parts to {OUT}")


if __name__ == "__main__":
    main()
