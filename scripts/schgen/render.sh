#!/bin/bash
# Build the schematic, check it against the intent, write docs/schematic.pdf and render every sheet to PNG.
# Usage: scripts/schgen/render.sh   (OUT=<dir> keeps the images, RES=<dpi> sets the resolution)
set -e
cd "$(dirname "$0")"
python3 build.py
python3 check.py
D=${OUT:-$(mktemp -d)}
mkdir -p "$D"
kicad-cli sch export pdf -o ../../docs/schematic.pdf ../../hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_sch >/dev/null
pdftoppm -r "${RES:-110}" -png ../../docs/schematic.pdf "$D/p"
echo "docs/schematic.pdf written; sheet images in $D"
