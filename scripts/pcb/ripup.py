#!/usr/bin/env python3
"""Take up the routing of passes 1, 3 and 4 so the board can be re-routed after placement changes (D-059).

    python3 scripts/pcb/ripup.py --apply

The copper those passes added is known by provenance, from the repository's history:
  - pass 1 (D-054): every track and via on the board at 86255bf that was not on it at 90d12ca;
  - passes 3 and 4 (D-057, D-058): every track and via at 6926847 that was not at ae59e46.
An item on the board now is taken up when its net, layer, ends, width (a via: position, size, drill) match one of
those. Everything else stays: the vendor copies and pass 2's restorations (D-055), the power bus and L3 (D-056), the
MCU fan-out (D-048), the GND lattice (D-049) and the pours. A pass item that a later step reshaped no longer matches and
is reported, not removed. The zones are refilled. Re-running is a no-op once that copper is gone. Nothing is locked
(D-045).
"""

import argparse
import pathlib
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board as B  # noqa: E402

# (revision with the pass's copper, revision before it), per pass.
PASSES = (("86255bf", "90d12ca"), ("6926847", "ae59e46"))


def key(item, board):
    net = item.GetNetname()
    if item.GetClass() == "PCB_VIA":
        p = item.GetPosition()
        return ("via", net, p.x, p.y, item.GetWidth(pcbnew.F_Cu), item.GetDrillValue())
    ends = sorted([(item.GetStart().x, item.GetStart().y), (item.GetEnd().x, item.GetEnd().y)])
    return ("track", net, board.GetLayerName(item.GetLayer()), *ends[0], *ends[1], item.GetWidth())


def copper_at(revision):
    """The keys of every track and via on the board at a revision."""
    relative = (B.KICAD / B.BOARD.name).relative_to(B.ROOT)
    text = subprocess.run(["git", "show", f"{revision}:{relative.as_posix()}"], cwd=B.ROOT, check=True,
                          capture_output=True).stdout
    with tempfile.TemporaryDirectory() as folder:
        path = pathlib.Path(folder) / "board.kicad_pcb"
        path.write_bytes(text)
        board = pcbnew.LoadBoard(str(path))
        return {key(t, board) for t in board.GetTracks() if t.GetClass() in ("PCB_TRACK", "PCB_VIA")}


def pass_copper():
    added = set()
    for after, before in PASSES:
        added |= copper_at(after) - copper_at(before)
    return added


def stage():
    added = pass_copper()
    board = pcbnew.LoadBoard(str(B.BOARD))
    found = [t for t in board.GetTracks() if t.GetClass() in ("PCB_TRACK", "PCB_VIA") and key(t, board) in added]
    if not found:
        print("no routing of passes 1, 3 or 4 left: nothing to do")
        sys.exit(3)
    tracks = sum(1 for t in found if t.GetClass() == "PCB_TRACK")
    vias = len(found) - tracks
    present = {key(t, board) for t in board.GetTracks() if t.GetClass() in ("PCB_TRACK", "PCB_VIA")}
    for item in found:
        board.Remove(item)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    print(f"taken up: {tracks} tracks, {vias} vias ({len(added)} items added by passes 1, 3 and 4; "
          f"{len(added - present)} no longer on the board as they were laid)")
    pcbnew.SaveBoard(str(B.BOARD), board)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--apply", action="store_true", help="take up the routing of passes 1, 3 and 4 (one shot)")
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        stage()
        return
    if not args.apply:
        parser.error("nothing to do without --apply")
    project = B.PROJECT.read_bytes()
    result = subprocess.run([sys.executable, __file__, "--pcbnew-stage"])
    B.PROJECT.write_bytes(project)
    if result.returncode == 3:
        return
    if result.returncode:
        sys.exit(result.returncode)
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(B.BOARD)], check=True, capture_output=True)
    B.PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
