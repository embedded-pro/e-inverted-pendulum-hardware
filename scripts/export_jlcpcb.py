#!/usr/bin/env python3
"""Export a JLCPCB fabrication + assembly package for the board.

A thin wrapper (D-064): runs the hardware-design plugin's hardware-project/scripts/export_jlcpcb.py,
pinned in scripts/plugin.py, with the same arguments. `python3 scripts/export_jlcpcb.py --help` shows them.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

if __name__ == "__main__":
    sys.exit(plugin.run("hardware-project", "export_jlcpcb.py", sys.argv[1:]))
