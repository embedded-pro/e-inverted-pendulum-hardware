#!/usr/bin/env python3
"""Download datasheets for LCSC parts through the JLCPCB parts API and extract their text.

A thin wrapper (D-064): runs the hardware-design plugin's hardware-project/scripts/fetch_datasheet.py,
pinned in scripts/plugin.py, with the same arguments. `python3 scripts/fetch_datasheet.py --help` shows them.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

if __name__ == "__main__":
    sys.exit(plugin.run("hardware-project", "fetch_datasheet.py", sys.argv[1:]))
