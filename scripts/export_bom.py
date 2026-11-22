#!/usr/bin/env python3
"""Export the schematic BOM: bom/bom.csv (stock-check format) and bom/bom_jlc.csv (JLCPCB assembly format).

A thin wrapper (D-064): runs the hardware-design plugin's hardware-project/scripts/export_bom.py,
pinned in scripts/plugin.py, with the same arguments. `python3 scripts/export_bom.py --help` shows them.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

if __name__ == "__main__":
    sys.exit(plugin.run("hardware-project", "export_bom.py", sys.argv[1:]))
