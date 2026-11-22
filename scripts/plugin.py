#!/usr/bin/env python3
"""Run a script of the hardware-design plugin (github.com/gabrielfrasantos/claude-hardware-skills), pinned (D-064).

The export, BOM, stock and datasheet scripts under scripts/ are thin wrappers around the plugin's hardware-project
scripts, so fixes land in one place. The plugin is found as:
  1. $HW: a skills directory (<plugin checkout>/plugins/hardware-design/skills), as the plugin's own docs use it;
  2. .hw/claude-hardware-skills at PLUGIN_TAG (gitignored), cloned on first use (needs git and the network).
The scripts run with HW_PROJECT_ROOT set to this repo, so they work from any directory.

    python3 scripts/plugin.py <skill> <script.py> [args...]     # e.g. pcb-copper netclasses.py check <board>
    python3 scripts/plugin.py --where                           # print the skills directory in use
"""
import json
import os
import pathlib
import subprocess
import sys

PLUGIN_REPO = "https://github.com/gabrielfrasantos/claude-hardware-skills.git"
PLUGIN_TAG = "v0.1.0"
ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKOUT = ROOT / ".hw" / "claude-hardware-skills"


def skills_dir():
    env = os.environ.get("HW")
    if env:
        path = pathlib.Path(env).expanduser().resolve()
        if not (path / "hardware-project").is_dir():
            sys.exit(f"$HW={env} is not the plugin's skills directory (no hardware-project/ in it)")
        return path
    skills = CHECKOUT / "plugins" / "hardware-design" / "skills"
    if not skills.is_dir():
        CHECKOUT.parent.mkdir(exist_ok=True)
        print(f"plugin.py: fetching the hardware-design plugin {PLUGIN_TAG} into {CHECKOUT.relative_to(ROOT)}",
              file=sys.stderr)
        subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--branch", PLUGIN_TAG, PLUGIN_REPO, str(CHECKOUT)],
                       check=True)
    manifest = CHECKOUT / "plugins" / "hardware-design" / ".claude-plugin" / "plugin.json"
    version = json.loads(manifest.read_text(encoding="utf-8")).get("version")
    if f"v{version}" != PLUGIN_TAG:
        print(f"plugin.py: {CHECKOUT.relative_to(ROOT)} is plugin {version}, this repo pins {PLUGIN_TAG}; delete the "
              "folder to fetch the pinned one", file=sys.stderr)
    return skills


def run(skill, script, args):
    path = skills_dir() / skill / "scripts" / script
    if not path.exists():
        sys.exit(f"the plugin has no {skill}/scripts/{script}")
    env = dict(os.environ, HW_PROJECT_ROOT=str(ROOT))
    return subprocess.run([sys.executable, str(path), *args], env=env).returncode


def main():
    if sys.argv[1:] == ["--where"]:
        print(skills_dir())
        return 0
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    return run(sys.argv[1], sys.argv[2], sys.argv[3:])


if __name__ == "__main__":
    sys.exit(main())
