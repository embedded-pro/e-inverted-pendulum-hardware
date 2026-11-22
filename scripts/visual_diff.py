#!/usr/bin/env python3
"""Visual diff of a KiCad board between two checkouts (old vs new), per board.

A thin wrapper (D-064): runs the hardware-design plugin's hardware-project/scripts/visual_diff.py,
pinned in scripts/plugin.py, with the same arguments. `python3 scripts/visual_diff.py --help` shows them.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

if __name__ == "__main__":
    sys.exit(plugin.run("hardware-project", "visual_diff.py", sys.argv[1:]))
