#!/usr/bin/env python3
"""Hand the three vendor copies over to the owner: no groups, no pours (owner, D-046).

One shot: `python3 scripts/pcb/ungroup_copies.py --apply`. For "MB1355 RF corner", "MB1163 NFC corner" and
"BOOST-DRV8711 drive" it:
  - removes the group and every copper pour that came with it (ST's and TI's GND, VM, phase, sense and RF_50 pours);
  - keeps the parts, the tracks and the vias where they are, unlocked and ungrouped, for the owner to edit;
  - keeps the MB1355 rule areas (the L2 cut-out under the RF line and ST's two pad keep-outs): the RF line needs them.
The group-scoped DRC rules are gone from board.py; ST's and TI's clearances are now scoped by net and reference there.
The copied routing's 90-degree corners, which the 45-degree rule would flag, are recorded as DRC exclusions in the
project (exact items, so anything the owner draws or changes is checked in full); --exclusions rewrites them alone.
Re-running --apply is a no-op once no group is left (the exclusions stay as they are). Run board.py --rules first so
the project rules are current.
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402

COMMENT = "copied vendor routing: 90-degree corner (D-046)"


def ungroup(board):
    groups = [g for g in board.Groups() if g.GetName() in B.COPIED_GROUPS]
    if not groups:
        return None
    members = [(g, list(g.GetItems())) for g in groups]
    pours, report = [], {}
    for group, items in members:
        mine = [i for i in items if i.GetClass() == "ZONE" and not i.GetIsRuleArea()]
        report[group.GetName()] = (len(mine), sum(1 for i in items if i.GetClass() == "ZONE" and i.GetIsRuleArea()))
        pours += mine
    for group, items in members:
        for item in items:
            item.SetLocked(False)
            group.RemoveItem(item)
    for item in pours + groups:
        board.Remove(item)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    return report


def angle_exclusions():
    """DRC exclusion keys for every track_angle error, already excluded or not: KiCad puts the marker on the corner both
    tracks share. The board is read in a child process: pcbnew rewrites the project file when its process exits."""
    with tempfile.TemporaryDirectory() as tmp:
        report = pathlib.Path(tmp) / "drc.json"
        subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-error", "--severity-exclusions",
                        "-o", str(report), str(B.BOARD)], check=True, capture_output=True)
        project = B.PROJECT.read_bytes()
        result = subprocess.run([sys.executable, __file__, "--pcbnew-keys", str(report)],
                                capture_output=True, text=True)
        B.PROJECT.write_bytes(project)
    if result.returncode:
        sys.exit(result.stderr or result.returncode)
    return json.loads(result.stdout.strip().splitlines()[-1])


def corner_keys(report):
    violations = json.loads(pathlib.Path(report).read_text(encoding="utf-8"))["violations"]
    board = pcbnew.LoadBoard(str(B.BOARD))
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    keys = []
    for v in violations:
        if v["type"] != "track_angle":
            continue
        a, b = (i["uuid"] for i in v["items"])
        ends = [{(p.x, p.y) for p in (tracks[u].GetStart(), tracks[u].GetEnd())} for u in (a, b)]
        corner = ends[0] & ends[1]
        if len(corner) != 1:
            sys.exit(f"track_angle between {a} and {b}: no single shared corner")
        x, y = corner.pop()
        keys.append(f"track_angle|{x}|{y}|{a}|{b}")
    print(json.dumps(sorted(keys)))


def write_exclusions(keys):
    project = json.loads(B.PROJECT.read_text(encoding="utf-8"))
    settings = project.setdefault("board", {}).setdefault("design_settings", {})
    kept = [e for e in settings.get("drc_exclusions", []) if not (isinstance(e, list) and e[1:] == [COMMENT])]
    settings["drc_exclusions"] = kept + [[k, COMMENT] for k in keys]
    B.PROJECT.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")


def stage():
    board = pcbnew.LoadBoard(str(B.BOARD))
    report = ungroup(board)
    if report is None:
        print("no copied group left: nothing to ungroup")
        sys.exit(3)
    pcbnew.SaveBoard(str(B.BOARD), board)
    for name, (pours, areas) in report.items():
        print(f"'{name}': group removed, {pours} pours removed, {areas} rule areas kept")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="ungroup the copies and remove their pours (one shot)")
    parser.add_argument("--exclusions", action="store_true", help="only rewrite the corner exclusions")
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--pcbnew-keys", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_keys:
        corner_keys(args.pcbnew_keys)
        return
    if args.pcbnew_stage:
        stage()
        return
    if not (args.apply or args.exclusions):
        parser.error("nothing to do without --apply or --exclusions")
    if args.apply:
        project = B.PROJECT.read_bytes()
        result = subprocess.run([sys.executable, __file__, "--pcbnew-stage"])
        B.PROJECT.write_bytes(project)
        if result.returncode == 3:
            return
        if result.returncode:
            sys.exit(result.returncode)
        subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
        B.PROJECT.write_bytes(project)
    keys = angle_exclusions()
    write_exclusions(keys)
    print(f"{len(keys)} copied-routing corners recorded as DRC exclusions")


if __name__ == "__main__":
    main()
