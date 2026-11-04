#!/usr/bin/env python3
"""Run the whole Phase 2 suite (S0-S5) and write results/summary.json. Exit 1 if any check fails."""

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = ["sizing.py", "power_entry.py", "bridge.py", "bus.py", "rails.py", "analog.py"]


def main():
    summary = {}
    for script in SCRIPTS:
        print(f"== {script}", flush=True)
        result = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE)
        summary[script] = "pass" if result.returncode == 0 else "fail"
    checks = {}
    for path in sorted((HERE / "results").glob("s[1-5]_*.json")):
        data = json.loads(path.read_text())
        found = data.get("checks") or data.get("proposed", {}).get("checks", {})
        checks[path.stem] = found
    (HERE / "results" / "summary.json").write_text(json.dumps({"scripts": summary, "checks": checks}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    sys.exit(0 if all(v == "pass" for v in summary.values()) else 1)


if __name__ == "__main__":
    main()
