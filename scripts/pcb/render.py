#!/usr/bin/env python3
"""Render the board for review (power-pcb-layout s6.4): every copper layer, both sides, a whole-page overview
(board plus the staging area) and a 3D view.

SVGs come from `kicad-cli pcb export svg` (board area only, no drawing sheet) and are rasterised with cairosvg on a
white background. The 3D view uses `kicad-cli pcb render`; parts without installed 3D models show as bare pads.

Run: python3 scripts/pcb/render.py [--out docs/images] [--dpi 300] [--no-3d]
"""

import argparse
import pathlib
import subprocess
import tempfile

import cairosvg

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOARD = ROOT / "hardware" / "e-inverted-pendulum" / "e-inverted-pendulum.kicad_pcb"

VIEWS = {
    "top": "F.Cu,F.SilkS,F.Mask,F.CrtYd,F.Fab,User.Drawings,User.Comments,Edge.Cuts",
    "bottom": "B.Cu,B.SilkS,B.CrtYd,User.Drawings,Edge.Cuts",
    "L1_F.Cu": "F.Cu,Edge.Cuts",
    "L2_In1.Cu": "In1.Cu,Edge.Cuts",
    "L3_In2.Cu": "In2.Cu,Edge.Cuts",
    "L4_B.Cu": "B.Cu,Edge.Cuts",
    "placement": "F.CrtYd,F.Fab,F.SilkS,User.Drawings,User.Comments,Edge.Cuts",
    "overview": "F.CrtYd,F.Fab,User.Drawings,User.Comments,Edge.Cuts",
}
WHOLE_PAGE = {"overview"}
MIRRORED = {"bottom", "L4_B.Cu"}


def render_svg(name, layers, out, dpi):
    with tempfile.TemporaryDirectory() as tmp:
        svg = pathlib.Path(tmp) / f"{name}.svg"
        command = ["kicad-cli", "pcb", "export", "svg", "-l", layers, "--exclude-drawing-sheet",
                   "--page-size-mode", "0" if name in WHOLE_PAGE else "2", "-o", str(svg), str(BOARD)]
        if name in MIRRORED:
            command.insert(-1, "--mirror")
        subprocess.run(command, check=True, capture_output=True)
        png = out / f"{name}.png"
        cairosvg.svg2png(url=str(svg), write_to=str(png), dpi=dpi, background_color="white")
    return png


def render_3d(out):
    png = out / "3d_top.png"
    subprocess.run(["kicad-cli", "pcb", "render", "--side", "top", "--width", "1400", "--height", "2000",
                    "--quality", "basic", "--background", "opaque", "-o", str(png), str(BOARD)],
                   check=True, capture_output=True)
    return png


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=pathlib.Path, default=ROOT / "docs" / "images")
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--no-3d", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    written = [render_svg(name, layers, args.out, args.dpi) for name, layers in VIEWS.items()]
    if not args.no_3d:
        written.append(render_3d(args.out))
    for path in written:
        print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


if __name__ == "__main__":
    main()
