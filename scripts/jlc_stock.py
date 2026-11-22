#!/usr/bin/env python3
"""Check every LCSC part in a BOM CSV against JLCPCB's live parts library.

A thin wrapper (D-064): runs the hardware-design plugin's hardware-project/scripts/jlc_stock.py,
pinned in scripts/plugin.py, with the same arguments. `python3 scripts/jlc_stock.py --help` shows them.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

if __name__ == "__main__":
    sys.exit(plugin.run("hardware-project", "jlc_stock.py", sys.argv[1:]))
