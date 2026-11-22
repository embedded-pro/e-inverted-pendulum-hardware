#!/usr/bin/env python3
"""The hardware-design plugin's gates on this board, as CI runs them (D-064, plugin plan §9 gate C).

  - pcb-copper netclasses.py check: every net in a standard class, class values current, tracks at their class width;
  - pcb-design-rules pcb_rules.py check --no-drc: shorts, clearance, routing geometry, teardrops, pours, ground;
  - design-review review.py: the scripted review (decoupling, pull-ups, ratings, ESD, assembly spacing, ...).

Gates that fail today have LIMITS at today's count: a ratchet. CI fails when a count rises; lower the limit when a
fix lands, never raise it without a decision. KiCad's DRC is not run here: it has one known error (the AE801 short,
C3) and the release workflow runs it with kicad-bot; switch to the full check when it is clean.
Reports go to plugin-gates/ (gitignored).

Run: python3 scripts/plugin_gates.py        (needs shapely, numpy, scipy; the plugin is fetched by scripts/plugin.py)
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plugin  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BOARD = "hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pcb"
OUT = ROOT / "plugin-gates"

# Ratchet limits, the counts at f3e1fbb (2026-11-22). Each one is a C3 finding (docs/decisions.md D-064).
LIMITS = {
    "netclasses": {"tracks_below_class_width": 50},     # TI's 0.254 / 0.508 mm copy traces, BAT_F 0.3 mm
    "rules": {"jogs": 1, "teardrops_disabled": 289, "zone_necks": 1, "gnd_plane_splits": 4, "unstitched_ground": 6},
}
REVIEW_FAIL_ON = "BLOCKER"


def gates(name):
    return [arg for k, v in LIMITS[name].items() for arg in ("--gate", f"{k}={v}")]


def main():
    OUT.mkdir(exist_ok=True)
    steps = [
        ("net classes", "pcb-copper", "netclasses.py",
         ["check", str(ROOT / BOARD), "--report", str(OUT / "netclasses.md"), *gates("netclasses")]),
        ("rules and geometry", "pcb-design-rules", "pcb_rules.py",
         ["check", str(ROOT / BOARD), "--no-drc", "--report", str(OUT / "rules.md"), "--json", str(OUT / "rules.json"),
          *gates("rules")]),
        ("design review", "design-review", "review.py",
         [str(ROOT / "hardware" / "e-inverted-pendulum"), "--out", str(OUT / "review"), "--skip", "erc,stock",
          "--fail-on", REVIEW_FAIL_ON]),
    ]
    failed = []
    for title, skill, script, args in steps:
        print(f"\n=== {title} ({skill}/{script})", flush=True)
        if plugin.run(skill, script, args) != 0:
            failed.append(title)
    print("\nplugin gates: " + ("FAIL: " + ", ".join(failed) if failed else "pass") + f"; reports in {OUT.name}/")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
