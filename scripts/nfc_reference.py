#!/usr/bin/env python3
"""Extract the NFC corner of ST's X-NUCLEO-NFC01A1 (MB1163 rev C-01) from its fab files (D-039).

ST's files stay in the gitignored reference/mb1163/ (STMicroelectronics, Open Platform License, www.st.com/opla). The
board ships as Gerbers, an Excellon drill file and pick-and-place only, so they are read here directly, with stdlib
readers for the subset Altium wrote (apertures C / R / O, D01 / D02 / D03, G36 / G37 regions; drill METRIC 4:4):
  - the tag cluster (U1 M24SR64-Y, L1, C2-C9, R6-R9): ST's lands, tracks, vias and GND pour;
  - the ANT14 coil: two stacked spirals, about 4 turns on F.Cu and 3.5 on B.Cu, joined by two layer changes.
Gerbers carry no nets. Nets come from copper connectivity (pads, track ends and vias, per layer, joined through the
drill hits) and are named from ST's schematic (MB1163 C-01 sheet 1). The script fails if a copper island would need
two names, if a pad's net differs from the schematic, or if the coil is not one path from AC0 to AC1.

Writes:
  - scripts/pcb/mb1163_nfc.json, in ST's board frame (Gerber mm, y up);
  - the MB1163_* footprints: ST's lands re-centred on their pads (orientation 0 is ST's part rotated back to 0), and
    MB1163_ANT14, the coil as footprint copper with net_tie_pad_groups "1,2" (the way nfc_coil.py built our old coil).
Every derived file says "Derived from STMicroelectronics MB1163 rev C-01 (X-NUCLEO-NFC01A1), www.st.com/opla".

Run: python3 scripts/nfc_reference.py
"""

import csv
import hashlib
import json
import math
import pathlib
import re
import subprocess
import sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "schgen"))
from make_footprints import PRETTY, footprint, uid  # noqa: E402
from sexpr import Str, Sym, dump  # noqa: E402

REFERENCE = ROOT / "reference" / "mb1163"
GERBERS = REFERENCE / "gerbers"
STEM = "MB1163_C01"
OUT = ROOT / "scripts" / "pcb" / "mb1163_nfc.json"
LIBRARY = "e-inverted-pendulum"
SOURCE = "Derived from STMicroelectronics MB1163 rev C-01 (X-NUCLEO-NFC01A1), www.st.com/opla"
UPLOADS = ("x-nucleo-nfc01a1_schematics.pdf", "x-nucleo-nfc01a1_gerbers.zip")

CLUSTER_BOX = (16.0, 40.25, 34.6, 59.2)
COIL_TOP_Y = 40.3
EPS = 1e-3

PARTS = {
    "U1": ("U803", "MB1163_SO8"),
    "L1": ("FB801", "MB1163_L_0805"),
    "C3": ("C803", "MB1163_CP_293D_A"),
    "C4": ("C804", "MB1163_C_0603"),
    "C5": ("C818", "MB1163_C_0603"),
    "C6": ("C819", "MB1163_C_0603"),
    "C8": ("C820", "MB1163_C_0603"),
    "C7": ("C821", "MB1163_C_0603"),
    "C9": ("C822", "MB1163_C_0603"),
    "C2": ("C823", "MB1163_C_0603"),
    "R8": ("R810", "MB1163_R_0603"),
    "R9": ("R804", "MB1163_R_0603"),
    "R6": ("R805", "MB1163_R_0603"),
    "R7": ("R806", "MB1163_R_0603"),
}
ANTENNA = ("ANT14", "AE801", "MB1163_ANT14")
U1_PINS = {"1": "RF_DISABLE", "2": "AC0", "3": "AC1", "4": "GND", "5": "SDA", "6": "SCL", "7": "GPO", "8": "VCC"}
PAIRS = {"L1": {"3V3", "VCC"}, "C3": {"VCC", "GND"}, "C4": {"VCC", "GND"}, "C5": {"VCC", "GND"},
         "C6": {"AC1", "GND"}, "C7": {"AC1", "GND"}, "C8": {"AC0", "GND"}, "C9": {"AC0", "GND"},
         "C2": {"AC0", "AC1"}, "R6": {"SDA", "3V3"}, "R7": {"SCL", "3V3"}, "R8": {"GPO", "3V3"},
         "R9": {"RF_DISABLE", "GND"}, ANTENNA[0]: {"AC0", "AC1"}}
NET_MAP = {"AC0": "NFC_AC0", "AC1": "NFC_AC1", "VCC": "NFC_VCC", "3V3": "+3V3", "GND": "GND", "SDA": "QWIIC_SDA",
           "SCL": "QWIIC_SCL", "GPO": "NFC_GPO", "RF_DISABLE": "NFC_RF_DIS"}

BODY = {"MB1163_SO8": (3.9, 4.9), "MB1163_C_0603": (1.6, 0.8), "MB1163_R_0603": (1.6, 0.8),
        "MB1163_L_0805": (2.0, 1.25), "MB1163_CP_293D_A": (3.2, 1.6)}
DESCRIPTION = {
    "MB1163_SO8": "SO-8 land of the M24SR64-Y",
    "MB1163_C_0603": "0603 capacitor land",
    "MB1163_R_0603": "0603 resistor land",
    "MB1163_L_0805": "0805 land of the VCC ferrite (Wurth 742792042)",
    "MB1163_CP_293D_A": "tantalum case A (3216-18) land, pad 1 +",
}
MODELS = {
    "MB1163_SO8": "Package_SO.3dshapes/SOIC-8_3.9x4.9mm_P1.27mm.step",
    "MB1163_C_0603": "Capacitor_SMD.3dshapes/C_0603_1608Metric.step",
    "MB1163_R_0603": "Resistor_SMD.3dshapes/R_0603_1608Metric.step",
    "MB1163_L_0805": "Inductor_SMD.3dshapes/L_0805_2012Metric.step",
    "MB1163_CP_293D_A": "Capacitor_Tantalum_SMD.3dshapes/CP_EIA-3216-18_Kemet-A.step",
}
COURTYARD_MARGIN = 0.25


def read_gerber(path):
    """Tracks, flashes and regions of one Altium RS-274X layer, in mm with y up."""
    text = path.read_text(errors="replace")
    apertures = {int(code): (shape, [float(v) for v in params.split("X")])
                 for code, shape, params in re.findall(r"%ADD(\d+)([CRO]),([^*]*)\*%", text)}
    body = re.sub(r"%[^%]*%", lambda m: "\n" + m.group(0) + "\n", text)
    tracks, flashes, regions = [], [], []
    aperture, x, y = None, 0.0, 0.0
    in_region, polarity, contours = False, "D", []
    for raw in body.replace("*", "*\n").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("%LP"):
            polarity = line[3]
            continue
        if line.startswith("%") or line.startswith("G04"):
            continue
        if line.startswith("G36"):
            in_region, contours = True, []
            continue
        if line.startswith("G37"):
            regions.append({"polarity": polarity, "contours": contours})
            in_region = False
            continue
        line = re.sub(r"^G0?1(?=[XYD])", "", line)
        m = re.match(r"^(?:G54)?D(\d+)\*$", line)
        if m and int(m.group(1)) >= 10:
            aperture = int(m.group(1))
            continue
        m = re.match(r"^(?:X(-?\d+))?(?:Y(-?\d+))?D0?([123])\*$", line)
        if not m:
            continue
        nx = int(m.group(1)) / 1e4 if m.group(1) else x
        ny = int(m.group(2)) / 1e4 if m.group(2) else y
        op = m.group(3)
        if in_region:
            if op == "2" or not contours:
                contours.append([(nx, ny)] if op == "2" else [(x, y), (nx, ny)])
            else:
                contours[-1].append((nx, ny))
        elif op == "1":
            shape, size = apertures[aperture]
            if shape != "C":
                sys.exit(f"{path.name}: draw with a non-round aperture D{aperture}")
            tracks.append({"width": size[0], "a": (x, y), "b": (nx, ny)})
        elif op == "3":
            shape, size = apertures[aperture]
            w, h = (size[0], size[0]) if shape == "C" else (size[0], size[1])
            flashes.append({"shape": shape, "w": w, "h": h, "at": (nx, ny)})
        x, y = nx, ny
    return {"tracks": tracks, "flashes": flashes, "regions": regions}


def read_drill(path):
    tools, hits = {}, []
    kind, tool, x, y = "PLATED", None, 0.0, 0.0
    for raw in path.read_text(errors="replace").splitlines():
        line = raw.strip()
        if line.startswith(";TYPE="):
            kind = line.split("=", 1)[1]
            continue
        m = re.match(r"^T(\d+)F\d+S\d+C([\d.]+)$", line)
        if m:
            tools[int(m.group(1))] = (float(m.group(2)), kind == "PLATED")
            continue
        m = re.match(r"^T(\d+)$", line)
        if m:
            tool = int(m.group(1))
            continue
        m = re.match(r"^(?:X(-?\d+))?(?:Y(-?\d+))?$", line)
        if m and (m.group(1) or m.group(2)):
            x = int(m.group(1)) / 1e4 if m.group(1) else x
            y = int(m.group(2)) / 1e4 if m.group(2) else y
            drill, plated = tools[tool]
            hits.append({"at": (x, y), "drill": drill, "plated": plated})
    return hits


def read_pick_place(path):
    rows = {}
    with open(path, encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle):
            ref = (row.get("Designator") or "").strip()
            if not ref:
                continue
            value = lambda key: float(row[key].replace("mm", ""))  # noqa: E731
            rows[ref] = {"mid": (value("Mid X"), value("Mid Y")), "pad1": (value("Pad X"), value("Pad Y")),
                         "rot": float(row["Rotation"]) % 360.0, "layer": row["Layer"], "value": row["Comment"].strip(),
                         "footprint": row["Footprint"]}
    return rows


def read_rules(path):
    rules = {}
    for line in path.read_text(errors="replace").splitlines():
        fields = dict(item.split("=", 1) for item in line.split("|") if "=" in item)
        if "Minimum" in fields:
            rules[fields["RuleName"]] = round(float(fields["Minimum"]) * 0.0254, 4)
    return rules


def inside(box, p):
    return box[0] - EPS <= p[0] <= box[2] + EPS and box[1] - EPS <= p[1] <= box[3] + EPS


def seg_distance(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def in_pad(p, pad):
    return abs(p[0] - pad["at"][0]) <= pad["w"] / 2 + EPS and abs(p[1] - pad["at"][1]) <= pad["h"] / 2 + EPS


def in_polygon(p, contour):
    x, y = p
    hit = False
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


class Islands:
    def __init__(self):
        self.parent = {}

    def find(self, key):
        self.parent.setdefault(key, key)
        while self.parent[key] != key:
            self.parent[key] = self.parent[self.parent[key]]
            key = self.parent[key]
        return key

    def join(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def part_pads(ref, row, flashes):
    """ST's lands of one part, numbered: pin 1 from the pick-and-place, SO-8 counter-clockwise from it."""
    count = 8 if PARTS[ref][1] == "MB1163_SO8" else 2
    radius = 3.5 if count == 8 else 1.8
    found = [f for f in flashes if f["shape"] != "C" and math.dist(f["at"], row["mid"]) < radius]
    if len(found) != count:
        sys.exit(f"{ref}: {len(found)} lands found, expected {count}")
    pin1 = min(found, key=lambda f: math.dist(f["at"], row["pad1"]))
    if math.dist(pin1["at"], row["pad1"]) > 0.01:
        sys.exit(f"{ref}: no land at the pick-and-place pin 1 {row['pad1']}")
    if count == 2:
        return {"1": pin1, "2": next(f for f in found if f is not pin1)}
    for axis in (0, 1):
        row_a = [f for f in found if abs(f["at"][1 - axis] - pin1["at"][1 - axis]) < 0.3]
        if len(row_a) == 4:
            break
    else:
        sys.exit(f"{ref}: can't find the row of pin 1")
    row_a.sort(key=lambda f: math.dist(f["at"], pin1["at"]))
    row_b = sorted((f for f in found if f not in row_a), key=lambda f: math.dist(f["at"], row_a[-1]["at"]))
    return {str(i + 1): f for i, f in enumerate(row_a + row_b)}


def to_local(offset, rot):
    """Offset from the part's centre (ST frame, y up) in the footprint at orientation 0 (KiCad frame, y down)."""
    a = math.radians(-rot)
    x = offset[0] * math.cos(a) - offset[1] * math.sin(a)
    y = offset[0] * math.sin(a) + offset[1] * math.cos(a)
    return round(x, 4) + 0.0, round(-y, 4) + 0.0


def mask_margin(pad, mask_flashes):
    hits = [f for f in mask_flashes if math.dist(f["at"], pad["at"]) < 0.005]
    if not hits:
        return None
    return round((hits[0]["w"] - pad["w"]) / 2, 4)


def land_footprint(name, rot, pads, masks):
    """Footprint text for ST's land pattern of one part, centred on its pads."""
    centre = (sum(p["at"][0] for p in pads.values()) / len(pads), sum(p["at"][1] for p in pads.values()) / len(pads))
    swap = round(rot) % 180 == 90
    local = []
    for number, pad in sorted(pads.items(), key=lambda kv: int(kv[0])):
        x, y = to_local((pad["at"][0] - centre[0], pad["at"][1] - centre[1]), rot)
        w, h = (pad["h"], pad["w"]) if swap else (pad["w"], pad["h"])
        shape = "oval" if pad["shape"] == "O" else "rect"
        local.append((number, x, y, round(w, 4), round(h, 4), shape, mask_margin(pad, masks)))
    return centre, local


def write_land(name, local):
    bw, bh = BODY[name]
    xs = [x - w / 2 for _, x, _, w, _, _, _ in local] + [x + w / 2 for _, x, _, w, _, _, _ in local] + [-bw / 2, bw / 2]
    ys = [y - h / 2 for _, _, y, _, h, _, _ in local] + [y + h / 2 for _, _, y, _, h, _, _ in local] + [-bh / 2, bh / 2]
    courtyard = tuple(round(v, 2) for v in (min(xs) - COURTYARD_MARGIN, min(ys) - COURTYARD_MARGIN,
                                            max(xs) + COURTYARD_MARGIN, max(ys) + COURTYARD_MARGIN))
    pads = []
    for number, x, y, w, h, shape, margin in local:
        node = [Sym("pad"), Str(number), Sym("smd"), Sym(shape), [Sym("at"), x, y], [Sym("size"), w, h],
                [Sym("layers"), Str("F.Cu"), Str("F.Paste"), Str("F.Mask")]]
        if margin is not None:
            node.append([Sym("solder_mask_margin"), margin])
        node.append([Sym("uuid"), uid(name, "pad", number)])
        pads.append(node)
    node = footprint(name, f"{DESCRIPTION[name]}, ST's land from MB1163 rev C-01 (X-NUCLEO-NFC01A1). {SOURCE}",
                     "smd", (-bw / 2, -bh / 2, bw / 2, bh / 2), courtyard, pads, silk=False)
    node.append([Sym("model"), Str(f"${{KICAD10_3DMODEL_DIR}}/{MODELS[name]}"), [Sym("offset"), [Sym("xyz"), 0, 0, 0]],
                 [Sym("scale"), [Sym("xyz"), 1, 1, 1]], [Sym("rotate"), [Sym("xyz"), 0, 0, 0]]])
    (PRETTY / f"{name}.kicad_mod").write_text(dump(node) + "\n", encoding="utf-8")


def write_antenna(coil, pads, transitions, centre, masks, bbox):
    """ANT14 as one footprint: ST's copper on F.Cu and B.Cu, pads 1 (AC0) and 2 (AC1), plated layer changes. The
    courtyard is the spiral's: the leads and pads reach into ST's cluster, as on MB1163."""
    name = ANTENNA[2]

    def at(p):
        return round(p[0] - centre[0], 4) + 0.0, round(-(p[1] - centre[1]), 4) + 0.0

    items = []
    for i, s in enumerate(coil):
        (x0, y0), (x1, y1) = at(s["a"]), at(s["b"])
        items.append([Sym("fp_line"), [Sym("start"), x0, y0], [Sym("end"), x1, y1],
                      [Sym("stroke"), [Sym("width"), s["width"]], [Sym("type"), Sym("solid")]],
                      [Sym("layer"), Str(s["layer"])], [Sym("uuid"), uid(name, "seg", i)]])
    nodes = []
    for number in ("1", "2"):
        pad = pads[number]
        layers = [Str("F.Cu")] + ([Str("F.Mask")] if mask_margin(pad, masks["F"]) is not None else [])
        nodes.append([Sym("pad"), Str(number), Sym("smd"), Sym("circle"), [Sym("at"), *at(pad["at"])],
                      [Sym("size"), pad["w"], pad["w"]], [Sym("layers"), *layers], [Sym("uuid"), uid(name, "pad", number)]])
    for i, t in enumerate(transitions):
        layers = [Str("*.Cu")]
        if t["mask_top"]:
            layers.append(Str("F.Mask"))
        if t["mask_bottom"]:
            layers.append(Str("B.Mask"))
        nodes.append([Sym("pad"), Str("2"), Sym("thru_hole"), Sym("circle"), [Sym("at"), *at(t["at"])],
                      [Sym("size"), t["size"], t["size"]], [Sym("drill"), t["drill"]], [Sym("layers"), *layers],
                      [Sym("remove_unused_layers"), Sym("yes")], [Sym("keep_end_layers"), Sym("yes")],
                      [Sym("uuid"), uid(name, "via", i)]])
    x0, x1 = bbox[0] - centre[0], bbox[2] - centre[0]
    y0, y1 = -(bbox[3] - centre[1]), -(bbox[1] - centre[1])
    m = COURTYARD_MARGIN
    node = footprint(name, "13.56 MHz printed coil ANT14 of the M24SR64-Y: about 4 turns on F.Cu and 3.5 on B.Cu, "
                     f"0.6 / 0.6 mm, plated layer changes; MB1163 rev C-01 (X-NUCLEO-NFC01A1). {SOURCE}",
                     "smd", (round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)),
                     (round(x0 - m, 3), round(y0 - m, 3), round(x1 + m, 3), round(y1 + m, 3)), nodes, items, silk=False)
    attr = next(i for i in node if isinstance(i, list) and i and i[0] == Sym("attr"))
    attr[1:] = [Sym("smd"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom")]
    node.insert(node.index(attr) + 1, [Sym("net_tie_pad_groups"), Str("1,2")])
    (PRETTY / f"{name}.kicad_mod").write_text(dump(node) + "\n", encoding="utf-8")


def clip_pour(regions, box):
    """ST's dark pour regions cut to the cluster box, through KiCad's polygon engine."""
    clip = pcbnew.SHAPE_POLY_SET()
    rect = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
        rect.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    rect.SetClosed(True)
    clip.AddOutline(rect)
    out = []
    for region in regions:
        if region["polarity"] != "D":
            continue
        for contour in region["contours"]:
            poly = pcbnew.SHAPE_POLY_SET()
            chain = pcbnew.SHAPE_LINE_CHAIN()
            for x, y in contour:
                chain.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
            chain.SetClosed(True)
            poly.AddOutline(chain)
            poly.BooleanIntersection(clip)
            for i in range(poly.OutlineCount()):
                if poly.HoleCount(i):
                    sys.exit("the clipped pour has holes: not handled")
                line = poly.Outline(i)
                pts = [[round(pcbnew.ToMM(line.CPoint(j).x), 4), round(pcbnew.ToMM(line.CPoint(j).y), 4)]
                       for j in range(line.PointCount())]
                if len(pts) >= 3:
                    out.append(pts)
    return out


def main():
    if not GERBERS.exists():
        sys.exit(f"{GERBERS.relative_to(ROOT)} is missing: unzip ST's x-nucleo-nfc01a1_gerbers.zip there (gitignored)")
    top = read_gerber(GERBERS / f"{STEM}.GTL")
    bottom = read_gerber(GERBERS / f"{STEM}.GBL")
    masks = {"F": read_gerber(GERBERS / f"{STEM}.GTS")["flashes"], "B": read_gerber(GERBERS / f"{STEM}.GBS")["flashes"]}
    drills = read_drill(GERBERS / f"{STEM}.TXT")
    placed = read_pick_place(GERBERS / f"Pick Place for {STEM}.csv")
    rules = read_rules(GERBERS / f"{STEM}.RUL")
    layers = {"F.Cu": top, "B.Cu": bottom}

    # Coil: every track at or below its two pads.
    coil = [dict(t, layer=layer) for layer, g in layers.items() for t in g["tracks"]
            if max(t["a"][1], t["b"][1]) <= COIL_TOP_Y + EPS and t["a"] != t["b"]]
    ant_pads = sorted((f for f in top["flashes"] if f["shape"] == "C" and abs(f["at"][1] - COIL_TOP_Y) < EPS),
                      key=lambda f: f["at"][0])
    changes = [h for h in drills if h["drill"] == 0.5 and
               any(math.dist(h["at"], p) < EPS for s in coil for p in (s["a"], s["b"]))]
    if len(ant_pads) != 2 or len(changes) != 2:
        sys.exit(f"ANT14: {len(ant_pads)} pads and {len(changes)} layer changes found, expected 2 and 2")
    for h in changes:
        pad = next(f for f in top["flashes"] if math.dist(f["at"], h["at"]) < EPS)
        h.update(size=pad["w"], mask_top=any(math.dist(f["at"], h["at"]) < EPS for f in masks["F"]),
                 mask_bottom=any(math.dist(f["at"], h["at"]) < EPS for f in masks["B"]))

    islands = Islands()
    for i, s in enumerate(coil):
        for j, o in enumerate(coil):
            if i < j and s["layer"] == o["layer"] and any(
                    seg_distance(p, o["a"], o["b"]) <= o["width"] / 2 + EPS for p in (s["a"], s["b"])):
                islands.join(("coil", i), ("coil", j))
        for k, h in enumerate(changes):
            if any(math.dist(p, h["at"]) <= h["size"] / 2 + EPS for p in (s["a"], s["b"])):
                islands.join(("coil", i), ("change", k))
        for k, pad in enumerate(ant_pads):
            if any(math.dist(p, pad["at"]) <= pad["w"] / 2 + EPS for p in (s["a"], s["b"])):
                islands.join(("coil", i), ("antpad", k))
    roots = {islands.find(("coil", i)) for i in range(len(coil))}
    if len(roots) != 1 or islands.find(("antpad", 0)) != islands.find(("antpad", 1)):
        sys.exit("ANT14 is not one path from pad to pad through both layers")

    # Cluster: ST's lands, tracks and vias inside the box, dangling ends pruned.
    pads = {}
    for st in PARTS:
        row = placed[st]
        if row["layer"] != "T":
            sys.exit(f"{st} is not on the top side")
        for number, pad in part_pads(st, row, top["flashes"]).items():
            pads[(st, number)] = dict(pad, layer="F.Cu")
    for k, pad in enumerate(ant_pads):
        pads[(ANTENNA[0], str(k))] = dict(pad, layer="F.Cu")
    vias = [dict(h) for h in drills if h["plated"] and h["drill"] < 0.5 and inside(CLUSTER_BOX, h["at"])]
    for via in vias:
        flash = next(f for f in top["flashes"] if math.dist(f["at"], via["at"]) < EPS)
        via["size"] = flash["w"]
    tracks = [dict(t, layer=layer) for layer, g in layers.items() for t in g["tracks"]
              if t["a"] != t["b"] and inside(CLUSTER_BOX, t["a"]) and inside(CLUSTER_BOX, t["b"])
              and min(t["a"][1], t["b"][1]) >= COIL_TOP_Y - EPS]

    def attached(p, layer, self_index):
        if any(pad["layer"] == layer and in_pad(p, pad) for pad in pads.values()):
            return True
        if any(math.dist(p, v["at"]) <= v["size"] / 2 + EPS for v in vias):
            return True
        return any(i != self_index and t["layer"] == layer and seg_distance(p, t["a"], t["b"]) <= t["width"] / 2 + EPS
                   for i, t in enumerate(tracks))

    while True:
        loose = [i for i, t in enumerate(tracks) if not (attached(t["a"], t["layer"], i) and attached(t["b"], t["layer"], i))]
        if not loose:
            break
        tracks = [t for i, t in enumerate(tracks) if i not in loose]

    pours = {layer: [c for r in g["regions"] if r["polarity"] == "D" for c in r["contours"]] for layer, g in layers.items()}
    islands = Islands()
    for i, t in enumerate(tracks):
        for p in (t["a"], t["b"]):
            for key, pad in pads.items():
                if pad["layer"] == t["layer"] and in_pad(p, pad):
                    islands.join(("track", i), ("pad",) + key)
            for k, v in enumerate(vias):
                if math.dist(p, v["at"]) <= v["size"] / 2 + EPS:
                    islands.join(("track", i), ("via", k))
            for j, o in enumerate(tracks):
                if j != i and o["layer"] == t["layer"] and seg_distance(p, o["a"], o["b"]) <= o["width"] / 2 + EPS:
                    islands.join(("track", i), ("track", j))
    names = {}

    def name(key, net, why):
        root = islands.find(key)
        if names.get(root, net) != net:
            sys.exit(f"{key}: copper joins {names[root]} and {net} ({why})")
        changed = root not in names
        names[root] = net
        return changed

    for number, net in U1_PINS.items():
        name(("pad", "U1", number), net, "U1 pin")
    for k, v in enumerate(vias):
        root = islands.find(("via", k))
        if root not in names and any(in_polygon(v["at"], c) for c in pours["F.Cu"] + pours["B.Cu"]):
            name(("via", k), "GND", "via in ST's GND pour")
    progress = True
    while progress:
        progress = False
        for st, pair in PAIRS.items():
            keys = [k for k in pads if k[0] == st]
            known = {k: names.get(islands.find(("pad",) + k)) for k in keys}
            nets = [n for n in known.values() if n]
            if len(nets) == 1 and len(keys) == 2:
                other = next(iter(pair - {nets[0]}), None)
                if other is None:
                    sys.exit(f"{st}: both pads would be {nets[0]}")
                missing = next(k for k, n in known.items() if not n)
                progress |= name(("pad",) + missing, other, f"{st} joins {sorted(pair)}")
    pad_net = {k: names.get(islands.find(("pad",) + k)) for k in pads}
    for st, pair in PAIRS.items():
        got = {n for k, n in pad_net.items() if k[0] == st}
        if got != pair:
            sys.exit(f"{st}: pads on {sorted(map(str, got))}, ST's schematic has {sorted(pair)}")
    for number, net in U1_PINS.items():
        if pad_net[("U1", number)] != net:
            sys.exit(f"U1 pin {number} is on {pad_net[('U1', number)]}, ST's schematic has {net}")
    track_nets = [names.get(islands.find(("track", i))) for i in range(len(tracks))]
    via_nets = [names.get(islands.find(("via", k))) for k in range(len(vias))]
    if None in track_nets or None in via_nets:
        sys.exit("some copper in the cluster has no net")

    # Footprints and the JSON.
    parts, written = [], {}
    for st, (ours, fp_name) in PARTS.items():
        row = placed[st]
        numbered = {k[1]: pad for k, pad in pads.items() if k[0] == st}
        centre, local = land_footprint(fp_name, row["rot"], numbered, masks["F"])
        if fp_name in written and written[fp_name] != local:
            sys.exit(f"{fp_name}: {st}'s land differs from the first part on it")
        if fp_name not in written:
            write_land(fp_name, local)
            written[fp_name] = local
        parts.append({"st": st, "ours": ours, "footprint": f"{LIBRARY}:{fp_name}", "st_value": row["value"],
                      "at": [round(c, 4) for c in centre], "rot": row["rot"],
                      "pads": [[n, round(p["at"][0], 4), round(p["at"][1], 4), pad_net[(st, n)]]
                               for n, p in sorted(numbered.items(), key=lambda kv: int(kv[0]))]})
    by_net = {pad_net[(ANTENNA[0], str(k))]: pad for k, pad in enumerate(ant_pads)}
    ant_numbered = {"1": by_net["AC0"], "2": by_net["AC1"]}
    xs = [v for s in coil for v in (s["a"][0], s["b"][0])]
    ys = [v for s in coil for v in (s["a"][1], s["b"][1])]
    half = max(s["width"] for s in coil) / 2
    turns = [s for s in coil if abs(s["a"][1] - s["b"][1]) < EPS and abs(s["a"][0] - s["b"][0]) > 5]
    spiral_top = max(s["a"][1] for s in turns) + half
    bbox = [round(min(xs) - half, 4), round(min(ys) - half, 4), round(max(xs) + half, 4), round(spiral_top, 4)]
    centre = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    write_antenna(coil, ant_numbered, changes, centre, masks, bbox)
    pour_edge = min(p[1] for c in pours["F.Cu"] + pours["B.Cu"] for p in c)
    subprocess.run(["kicad-cli", "fp", "upgrade", "--force", str(PRETTY)], check=True, capture_output=True)

    data = {
        "source": SOURCE,
        "board": "MB1163 rev C-01 (X-NUCLEO-NFC01A1): Gerbers, Excellon drill and pick-and-place",
        "files": {f: hashlib.sha256((REFERENCE / f).read_bytes()).hexdigest() for f in UPLOADS},
        "frame": "ST board coordinates, Gerber mm, y up",
        "st_rules_mm": rules,
        "net_map": NET_MAP,
        "cluster_box": list(CLUSTER_BOX),
        "parts": parts,
        "antenna": {"st": ANTENNA[0], "ours": ANTENNA[1], "footprint": f"{LIBRARY}:{ANTENNA[2]}",
                    "at": [round(c, 4) for c in centre], "rot": 0.0,
                    "pads": [[n, p["at"][0], p["at"][1], "AC0" if n == "1" else "AC1"] for n, p in ant_numbered.items()]},
        "coil": {"bbox": bbox, "segments": [[s["layer"], s["width"], *s["a"], *s["b"]] for s in coil],
                 "layer_changes": [{"at": list(h["at"]), "size": h["size"], "drill": h["drill"],
                                    "plated_in_st_drill_file": h["plated"]} for h in changes],
                 "board_thickness_mm": 1.6},
        "tracks": [{"layer": t["layer"], "width": t["width"], "start": list(t["a"]), "end": list(t["b"]), "net": n}
                   for t, n in zip(tracks, track_nets)],
        "vias": [{"at": list(v["at"]), "size": v["size"], "drill": v["drill"], "net": n} for v, n in zip(vias, via_nets)],
        "pour": {layer: clip_pour(g["regions"], CLUSTER_BOX) for layer, g in layers.items()},
        "pour_net": "GND",
        "pour_edge_y": round(pour_edge, 4),
        "coil_to_pour_mm": round(pour_edge - spiral_top, 4),
        "not_copied": "headers CN1-CN4, LED1-LED3, R1-R5 (host side: Arduino pins, LEDs, the RF-disable jumper), "
                      "logo, mounting holes, and ST's routing out of the cluster to the headers",
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    plated = [h["plated"] for h in changes]
    print(f"{OUT.relative_to(ROOT)}: {len(parts)} parts, {len(tracks)} tracks, {len(vias)} vias, "
          f"{sum(len(v) for v in data['pour'].values())} pour polygons; coil {len(coil)} segments, bbox {bbox}, "
          f"pour {data['coil_to_pour_mm']} mm from the coil")
    print(f"ANT14 layer changes in ST's drill file: plated {plated} (ours are plated)")
    print("footprints:", ", ".join(sorted(written) + [ANTENNA[2]]))


if __name__ == "__main__":
    main()
