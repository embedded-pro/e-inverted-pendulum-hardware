#!/usr/bin/env python3
"""Generate the project footprints in kicad/lib/e-inverted-pendulum.pretty from datasheet land patterns.

Each footprint lists its source (document and figure). Files are normalised with `kicad-cli fp upgrade`.
"""

import pathlib
import subprocess
import uuid

from sexpr import Str, Sym, dump

PRETTY = pathlib.Path(__file__).resolve().parent.parent / "lib" / "e-inverted-pendulum.pretty"
NAMESPACE = uuid.UUID("0c3f6a47-2b8e-4f0e-8f5d-7a1d9e2c4b60")


def uid(*parts):
    return Str(str(uuid.uuid5(NAMESPACE, "/".join(map(str, parts)))))


def text(kind, value, x, y, layer, name):
    return [Sym("property"), Str(kind), Str(value), [Sym("at"), x, y, 0], [Sym("layer"), Str(layer)],
            [Sym("uuid"), uid(name, kind)],
            [Sym("effects"), [Sym("font"), [Sym("size"), 0.8, 0.8], [Sym("thickness"), 0.12]]]]


def rect(x0, y0, x1, y1, layer, width, name, tag):
    return [Sym("fp_rect"), [Sym("start"), x0, y0], [Sym("end"), x1, y1],
            [Sym("stroke"), [Sym("width"), width], [Sym("type"), Sym("solid")]], [Sym("fill"), False],
            [Sym("layer"), Str(layer)], [Sym("uuid"), uid(name, tag)]]


def label(value, x, y, layer, name, tag):
    return [Sym("fp_text"), Sym("user"), Str(value), [Sym("at"), x, y, 0], [Sym("layer"), Str(layer)],
            [Sym("uuid"), uid(name, tag)],
            [Sym("effects"), [Sym("font"), [Sym("size"), 0.8, 0.8], [Sym("thickness"), 0.12]]]]


def smd(number, x, y, w, h, name, mask=None, paste=None, shape="rect"):
    node = [Sym("pad"), Str(number), Sym("smd"), Sym(shape), [Sym("at"), x, y], [Sym("size"), w, h],
            [Sym("layers"), Str("F.Cu"), Str("F.Paste"), Str("F.Mask")]]
    if mask is not None:
        node.append([Sym("solder_mask_margin"), mask])
    if paste is not None:
        node.append([Sym("solder_paste_margin"), paste])
    node.append([Sym("uuid"), uid(name, "pad", number, x, y)])
    return node


def tht(number, x, y, size, drill, name, square=False):
    return [Sym("pad"), Str(number), Sym("thru_hole"), Sym("rect" if square else "circle"), [Sym("at"), x, y],
            [Sym("size"), size, size], [Sym("drill"), drill], [Sym("layers"), Str("*.Cu"), Str("*.Mask")],
            [Sym("uuid"), uid(name, "pad", number, x, y)]]


def footprint(name, description, attr, body, courtyard, pads, extra=(), silk=True):
    x0, y0, x1, y1 = body
    cx0, cy0, cx1, cy1 = courtyard
    return [Sym("footprint"), Str(name), [Sym("version"), 20241229], [Sym("generator"), Str("pcbnew")],
            [Sym("generator_version"), Str("9.0")], [Sym("layer"), Str("F.Cu")], [Sym("descr"), Str(description)],
            text("Reference", "REF**", (x0 + x1) / 2, cy0 - 1.0, "F.SilkS", name),
            text("Value", name, (x0 + x1) / 2, cy1 + 1.0, "F.Fab", name),
            [Sym("attr"), Sym(attr)],
            rect(x0, y0, x1, y1, "F.Fab", 0.1, name, "fab"),
            rect(cx0, cy0, cx1, cy1, "F.CrtYd", 0.05, name, "crtyd")] + (
            [rect(x0 - 0.1, y0 - 0.1, x1 + 0.1, y1 + 0.1, "F.SilkS", 0.12, name, "silk")] if silk else []
        ) + list(extra) + pads


FOOTPRINTS = {
    "ST_MLPF-WB55-01E3": lambda n: footprint(
        n, "ST MLPF-WB55-01E3 bumpless CSP, 2x3 pads 0.5 x 0.587 mm pitch; DS12804 Rev 2 Table 4, Table 6, Fig. 13 "
           "(top view: A1 OUT, A2 GND4, A3 IN | B1 GND3, B2 GND2, B3 GND1; 300 um copper, 200 um mask/paste)",
        "smd", (-0.5, -0.8, 0.5, 0.8), (-0.75, -1.05, 0.75, 1.05),
        [smd(p, x, y, 0.3, 0.3, n, mask=-0.05, paste=-0.05) for p, x, y in (
            ("A1", -0.25, -0.587), ("A2", -0.25, 0.0), ("A3", -0.25, 0.587),
            ("B1", 0.25, -0.587), ("B2", 0.25, 0.0), ("B3", 0.25, 0.587))],
        [label("OUT", -1.2, -0.587, "F.Fab", n, "out"), label("IN", -1.2, 0.587, "F.Fab", n, "in")]),
    "AMASS_XT30UPB-F_1x02_P5.00mm_Vertical": lambda n: footprint(
        n, "AMASS XT30UPB-F PCB socket, 2 x Ø1.6 pins at 5.00 mm, recommended holes Ø1.9 (AMASS drawing p.2-3); "
           "pad 1 = +; check against the molded marking at assembly",
        "through_hole", (-2.6, -2.8, 7.6, 2.8), (-2.85, -3.05, 7.85, 3.05),
        [tht("1", 0, 0, 3.2, 1.9, n, square=True), tht("2", 5.0, 0, 3.2, 1.9, n)],
        [label("+", 0, -3.8, "F.SilkS", n, "plus"), label("-", 5.0, -3.8, "F.SilkS", n, "minus")]),
    "SW_Slide_SPDT_SS-12D10L5_P4.70mm": lambda n: footprint(
        n, "SS-12D10L5 slide switch, 3 pins 0.8 x 1.3 mm at 4.7 mm pitch, centre pin common (datasheet page 1); "
           "hole diameter not given, Ø1.7 chosen to clear the 1.53 mm pin diagonal",
        "through_hole", (-1.8, -3.4, 11.2, 3.4), (-2.05, -3.65, 11.45, 3.65),
        [tht("1", 0, 0, 2.6, 1.7, n, square=True), tht("2", 4.7, 0, 2.6, 1.7, n), tht("3", 9.4, 0, 2.6, 1.7, n)]),
    "Buzzer_MLT-8530_8.5x8.5mm": lambda n: footprint(
        n, "Jiangsu Huaneng MLT-8530 SMD magnetic transducer, 4 pads 2.3 x 2.3 mm on a 7.1 mm square "
           "(datasheet p.2, p.4 s5.2): + top-left, - bottom-left, right pads mechanical",
        "smd", (-4.35, -4.35, 4.35, 4.35), (-4.85, -4.85, 4.85, 4.85),
        [smd("1", -3.55, -3.55, 2.3, 2.3, n), smd("2", -3.55, 3.55, 2.3, 2.3, n),
         smd("", 3.55, -3.55, 2.3, 2.3, n), smd("", 3.55, 3.55, 2.3, 2.3, n)],
        [label("+", -3.55, -5.4, "F.SilkS", n, "plus")], silk=False),
    "SW_Push_TS-1187A_5.1x5.1mm": lambda n: footprint(
        n, "XKB TS-1187A-B-A-B 5.1 x 5.1 mm SMD tact switch; pads 1.0 x 0.75 mm at 6.0 x 3.75 mm centres; "
           "A-B (pad 1) and C-D (pad 2) internally joined (datasheet page 1)",
        "smd", (-2.55, -2.55, 2.55, 2.55), (-3.75, -2.8, 3.75, 2.8),
        [smd("1", -3.0, -1.875, 1.0, 0.75, n), smd("1", 3.0, -1.875, 1.0, 0.75, n),
         smd("2", -3.0, 1.875, 1.0, 0.75, n), smd("2", 3.0, 1.875, 1.0, 0.75, n)], silk=False),
}


def main():
    PRETTY.mkdir(parents=True, exist_ok=True)
    for name, make in FOOTPRINTS.items():
        path = PRETTY / f"{name}.kicad_mod"
        path.write_text(dump(make(name)) + "\n", encoding="utf-8")
    subprocess.run(["kicad-cli", "fp", "upgrade", "--force", str(PRETTY)], check=True, capture_output=True)
    print(f"wrote {len(FOOTPRINTS)} footprints to {PRETTY}")


if __name__ == "__main__":
    main()
