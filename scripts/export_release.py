#!/usr/bin/env python3
"""Build a release bundle for a board: ONE zip per project containing everything a

A thin wrapper (D-064): runs the hardware-design plugin's hardware-project/scripts/export_release.py,
pinned in scripts/plugin.py, with the same arguments. `python3 scripts/export_release.py --help` shows them.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

if __name__ == "__main__":
    sys.exit(plugin.run("hardware-project", "export_release.py", sys.argv[1:]))
