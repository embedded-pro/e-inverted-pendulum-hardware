#!/usr/bin/env python3
"""Extract the RF corner of ST's NUCLEO-WB55 board (MB1355 rev D-01) into data this repository keeps (D-037).

Input: reference/mb1355/ (ST's Altium project and BOM, Open Platform License Agreement www.st.com/opla; gitignored,
never committed). The board is read through KiCad's Altium importer.

Output, derived from STMicroelectronics MB1355 rev D-01:
- scripts/pcb/mb1355_rf.json: the RF corner in ST's board coordinates (mm): part positions, copper tracks and arcs,
  vias, the antenna tab outline, the L1/L3/L4 ground and the L2 cut-out under the RF line, and the net map;
- footprints MB1355_* in hardware/e-inverted-pendulum/e-inverted-pendulum.pretty: ST's land patterns, re-centred on
  their pads (the JLCPCB placement origin), with a courtyard and our text conventions; MB1355_Meander_Antenna is the
  antenna copper (net ANT) as one custom pad.

scripts/pcb/rf_block.py applies the JSON to our board.
"""

import json
import math
import pathlib
import sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "schgen"))
from sexpr import dump, parse  # noqa: E402

REFERENCE = ROOT / "reference" / "mb1355" / "MB1355D" / "MB1355.PcbDoc"
OUT = ROOT / "scripts" / "pcb" / "mb1355_rf.json"
PRETTY = ROOT / "hardware" / "e-inverted-pendulum" / "e-inverted-pendulum.pretty"
LIBRARY = "e-inverted-pendulum"
SOURCE = "Derived from STMicroelectronics MB1355 rev D-01 (NUCLEO-WB55), Open Platform License www.st.com/opla"

STRIP = (126.5, 72.0, 156.5, 88.8)
SHIELD = (127.6, 83.8, 146.1, 102.2)
GROUND_STRIP = (126.5, 80.0, 156.5, 88.8)
CUT_SEARCH = (126.5, 80.6, 156.5, 88.8)

NET_MAP = {
    "GND": "GND",
    "NetU1_31": "RF1", "NetR5_1": "RF_50", "NetC36_1": "RF_MATCH", "ANT": "RF_ANT",
    "NetC39_2": "RF_SMA_A", "NetC40_2": "RF_SMA",
    "NetU1_34": "HSE_OUT", "NetU1_35": "HSE_IN",
    "NetC6_1": "OSC32_IN", "NetC7_1": "OSC32_OUT",
    "NetL5_2": "SMPS_LX", "NetL1_2": "SMPS_MID", "NetC29_1": "VFBSMPS",
    "NetC23_1": "+3V3",
}
VIA_NETS = {"GND", "NetC23_1"}

PARTS = [
    ("U12", "FL401"), ("R5", "R401"), ("C36", "C401"), ("L3", "L401"), ("C37", "C402"),
    ("R13", "R402"), ("C39", "C403"), ("L4", "R403"), ("C40", "C404"), ("J2", "J401"),
    ("X1", "Y301"), ("X2", "Y302"), ("C6", "C315"), ("C7", "C316"),
    ("L5", "L302"), ("L1", "L301"), ("C29", "C314"), ("C23", "C309"), ("C24", "C318"),
    ("SC1", "SC401"), ("SC2", "SC402"), ("SC3", "SC403"), ("SC4", "SC404"),
]
EXTRA_FOOTPRINTS = {"C33": "VDDRF decoupling (placed on top by rf_block.py, D-037)"}

mm = pcbnew.ToMM


def inside(box, x, y):
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def in_region(x, y):
    return inside(STRIP, x, y) or inside(SHIELD, x, y)


def point(v):
    return [round(mm(v.x), 4), round(mm(v.y), 4)]


def footprint_name(fp):
    name = fp.GetFPIDAsString().split(":")[-1]
    return "MB1355_" + "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def polygons(shape):
    out = []
    for i in range(shape.OutlineCount()):
        outline = shape.Outline(i)
        out.append([point(outline.CPoint(j)) for j in range(outline.PointCount())])
    return out


def box_poly(box):
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])):
        poly.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    return poly


def pad_box(fp):
    xs, ys = [], []
    for pad in fp.Pads():
        bb = pad.GetBoundingBox()
        xs += [bb.GetLeft(), bb.GetRight()]
        ys += [bb.GetTop(), bb.GetBottom()]
    return min(xs), min(ys), max(xs), max(ys)


def pad_centre(fp):
    x0, y0, x1, y1 = pad_box(fp)
    return pcbnew.VECTOR2I((x0 + x1) // 2, (y0 + y1) // 2)


def tidy(fp, name, description):
    """Courtyard (pads + 0.1 mm, IPC-7351 least: ST packs the RF corner that tightly), reference on silk, value
    hidden, source in the description. ST's own texts, silk and courtyard are stripped from the saved file by
    clean_file() (removing items through pcbnew leaves its SWIG views unusable for the rest of the process)."""
    fp.SetFPID(pcbnew.LIB_ID(LIBRARY, name))
    fp.SetLibDescription(f"{description}. {SOURCE}")
    fp.SetKeywords("MB1355 NUCLEO-WB55 STM32WB RF")
    x0, y0, x1, y1 = pad_box(fp)
    margin = pcbnew.FromMM(0.1)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    courtyard = []
    for i in range(4):
        line = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(pcbnew.VECTOR2I(*corners[i]))
        line.SetEnd(pcbnew.VECTOR2I(*corners[(i + 1) % 4]))
        line.SetLayer(pcbnew.F_CrtYd)
        line.SetWidth(pcbnew.FromMM(0.05))
        fp.Add(line)
        courtyard.append(line.m_Uuid.AsString())
    size = pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0))
    ref, value = fp.Reference(), fp.Value()
    ref.SetText("REF**")
    ref.SetLayer(pcbnew.F_SilkS)
    ref.SetTextSize(size)
    ref.SetTextThickness(pcbnew.FromMM(0.15))
    ref.SetVisible(True)
    ref.SetPosition(pcbnew.VECTOR2I(0, y0 - pcbnew.FromMM(0.8)))
    ref.SetTextAngleDegrees(0)
    ref.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    ref.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    value.SetText(name)
    value.SetLayer(pcbnew.F_Fab)
    value.SetTextSize(size)
    value.SetTextThickness(pcbnew.FromMM(0.15))
    value.SetVisible(False)
    value.SetPosition(pcbnew.VECTOR2I(0, y1 + pcbnew.FromMM(0.8)))
    value.SetTextAngleDegrees(0)
    value.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    value.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    return courtyard


def clean_file(path, keep_courtyard_uuid=None):
    """Drop ST's texts, silk and courtyard and the 3D models (paths into ST's Altium install, or embedded vendor STEP
    files) from a saved footprint; our courtyard and the Reference / Value properties stay."""
    tree = parse(path.read_text(encoding="utf-8"))
    graphics = {"fp_line", "fp_arc", "fp_circle", "fp_poly", "fp_rect", "fp_curve"}
    kept = []
    for node in tree:
        head = node[0] if isinstance(node, list) and node else None
        if head in ("model", "embedded_files", "fp_text", "fp_text_box"):
            continue
        if head in graphics:
            layer = next((c[1] for c in node[1:] if isinstance(c, list) and c and c[0] == "layer"), "")
            uuid = next((c[1] for c in node[1:] if isinstance(c, list) and c and c[0] == "uuid"), "")
            if layer in ("F.SilkS", "B.SilkS", "B.CrtYd") or (layer == "F.CrtYd" and uuid not in (keep_courtyard_uuid or ())):
                continue
        kept.append(node)
    path.write_text(dump(kept) + "\n", encoding="utf-8")


def export_footprint(io, fp, description):
    """Save a copy of an ST footprint, unrotated, on top, with its origin at the centre of its pads."""
    name = footprint_name(fp)
    copy = pcbnew.FOOTPRINT(fp)
    if copy.IsFlipped():
        copy.Flip(copy.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
    copy.SetOrientationDegrees(0)
    copy.SetPosition(pcbnew.VECTOR2I(0, 0))
    centre = pad_centre(copy)
    copy.MoveAnchorPosition(pcbnew.VECTOR2I(-centre.x, -centre.y))
    copy.SetPosition(pcbnew.VECTOR2I(0, 0))
    courtyard = tidy(copy, name, description)
    io.FootprintSave(str(PRETTY), copy)
    clean_file(PRETTY / f"{name}.kicad_mod", courtyard)
    return name


def antenna_footprint(io, board, zone):
    """The meander antenna (ST AN3359 type, net ANT) as one custom SMD pad on F.Cu, origin at its feed."""
    pcbnew.ZONE_FILLER(board).Fill([zone])
    fill = zone.GetFilledPolysList(pcbnew.F_Cu)
    outline = fill.Outline(0)
    pts = [outline.CPoint(j) for j in range(outline.PointCount())]
    bottom = max(p.y for p in pts)
    feed_candidates = [p for p in pts if p.y >= bottom - pcbnew.FromMM(0.01)]
    feed = pcbnew.VECTOR2I(sum(p.x for p in feed_candidates) // len(feed_candidates), bottom - pcbnew.FromMM(0.3))
    fp = pcbnew.FOOTPRINT(board)
    pad = pcbnew.PAD(fp)
    pad.SetNumber("1")
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Cu)
    pad.SetLayerSet(layers)
    pad.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CUSTOM)
    pad.SetAnchorPadShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(pcbnew.FromMM(0.3), pcbnew.FromMM(0.3)))
    chain = pcbnew.VECTOR_VECTOR2I()
    for p in pts:
        chain.append(pcbnew.VECTOR2I(p.x - feed.x, p.y - feed.y))
    pad.AddPrimitivePoly(pcbnew.F_Cu, chain, 0, True)
    pad.SetPosition(pcbnew.VECTOR2I(0, 0))
    fp.Add(pad)
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    courtyard = tidy(fp, "MB1355_Meander_Antenna", "2.4 GHz printed meander antenna (ST AN3359 type), copper only, "
                     "keep the ground-free tab of the MB1355 outline around it")
    io.FootprintSave(str(PRETTY), fp)
    clean_file(PRETTY / "MB1355_Meander_Antenna.kicad_mod", courtyard)
    return point(feed), [[round(mm(p.x - feed.x), 4), round(mm(p.y - feed.y), 4)] for p in pts]


def zone_settings(zone):
    return {"clearance": round(mm(zone.GetLocalClearance() or 0), 4), "min_width": round(mm(zone.GetMinThickness()), 4),
            "thermal_gap": round(mm(zone.GetThermalReliefGap()), 4),
            "thermal_spoke": round(mm(zone.GetThermalReliefSpokeWidth()), 4),
            "pad_connection": int(zone.GetPadConnection())}


def zone_part(zone, layer, box):
    clip = box_poly(box)
    shape = pcbnew.SHAPE_POLY_SET(zone.Outline())
    shape.BooleanIntersection(clip)
    return polygons(shape)


def main():
    if not REFERENCE.exists():
        sys.exit(f"{REFERENCE.relative_to(ROOT)} not found: unpack ST's MB1355 files into reference/mb1355 (docs/rf.md)")
    io_altium = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.ALTIUM_DESIGNER)
    board = io_altium.LoadBoard(str(REFERENCE), None)
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    exports = {}
    parts = []
    for st_ref, our_ref in PARTS:
        fp = footprints[st_ref]
        name = footprint_name(fp)
        exports.setdefault(name, (st_ref, f"ST land pattern {fp.GetFPIDAsString()} (MB1355 {st_ref})"))
        parts.append({"st": st_ref, "ours": our_ref, "footprint": f"{LIBRARY}:{name}",
                      "at": point(pad_centre(fp)), "rot": round(fp.GetOrientationDegrees(), 3),
                      "st_side": "B" if fp.IsFlipped() else "F",
                      "pads": [[pad.GetNumber()] + point(pad.GetPosition()) for pad in fp.Pads()]})
    for st_ref, note in EXTRA_FOOTPRINTS.items():
        exports.setdefault(footprint_name(footprints[st_ref]), (st_ref, f"ST land pattern ({note})"))

    u1 = footprints["U1"]
    mcu_pads = {pad.GetNumber(): point(pad.GetPosition()) for pad in u1.Pads()}

    ant_zone = [z for z in board.Zones() if z.GetNetname() == "ANT" and not z.GetIsRuleArea()][0]
    feed, antenna = antenna_footprint(io, board, ant_zone)
    parts.append({"st": "ANT", "ours": "AE401", "footprint": f"{LIBRARY}:MB1355_Meander_Antenna", "at": feed,
                  "rot": 0.0, "st_side": "F"})

    tracks, vias = [], []
    for item in board.GetTracks():
        net = item.GetNetname()
        if item.GetClass() == "PCB_VIA":
            at = item.GetPosition()
            if net in VIA_NETS and in_region(mm(at.x), mm(at.y)):
                vias.append({"net": net, "at": point(at), "size": round(mm(item.GetWidth(pcbnew.F_Cu)), 4),
                             "drill": round(mm(item.GetDrillValue()), 4)})
            continue
        if net not in NET_MAP or item.GetLayer() != pcbnew.F_Cu:
            continue
        start, end = item.GetStart(), item.GetEnd()
        if not (in_region(mm(start.x), mm(start.y)) and in_region(mm(end.x), mm(end.y))):
            continue
        if item.GetClass() == "PCB_TRACK" and (end - start).EuclideanNorm() < pcbnew.FromMM(0.01):
            continue
        entry = {"net": net, "layer": "F.Cu", "start": point(start), "end": point(end),
                 "width": round(mm(item.GetWidth()), 4)}
        if item.GetClass() == "PCB_ARC":
            entry["mid"] = point(item.GetMid())
        tracks.append(entry)

    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    zones, rule_areas = [], []
    for zone in board.Zones():
        bb = zone.GetBoundingBox()
        centre = (mm(bb.Centre().x), mm(bb.Centre().y))
        if zone.GetIsRuleArea():
            if mm(bb.GetWidth()) < 1.0 and mm(bb.GetHeight()) < 1.0 and in_region(*centre) \
                    and zone.GetLayerSet().Seq().size() == 1:
                rule_areas.append({"name": "MB1355 pad keep-out", "layers": ["F.Cu"],
                                   "deny": ["pour"], "polygon": polygons(zone.Outline())[0]})
            continue
        net = zone.GetNetname()
        if net == "NetR5_1":
            zones.append({"net": net, "layer": "F.Cu", "priority": 2, "polygons": polygons(zone.Outline()),
                          **zone_settings(zone)})
        if net == "GND":
            layer = board.GetLayerName(zone.GetLayer())
            canonical = {pcbnew.F_Cu: "F.Cu", pcbnew.In1_Cu: "In1.Cu", pcbnew.In2_Cu: "In2.Cu",
                         pcbnew.B_Cu: "B.Cu"}[zone.GetLayer()]
            parts_in_strip = zone_part(zone, canonical, GROUND_STRIP)
            if parts_in_strip:
                zones.append({"net": "GND", "layer": canonical, "priority": 1, "polygons": parts_in_strip,
                              "st_layer": layer, **zone_settings(zone)})
            if zone.GetLayer() == pcbnew.In1_Cu:
                cut = box_poly(CUT_SEARCH)
                cut.BooleanSubtract(pcbnew.SHAPE_POLY_SET(zone.Outline()))
                for poly in polygons(cut):
                    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
                    if max(xs) - min(xs) > 1.0 and max(ys) - min(ys) > 1.0:
                        rule_areas.append({"name": "MB1355 L2 cut-out (RF line references L3)", "layers": ["In1.Cu"],
                                           "deny": ["pour", "tracks"], "polygon": poly})

    outline = []
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts and d.GetShape() == pcbnew.SHAPE_T_SEGMENT:
            s, e = d.GetStart(), d.GetEnd()
            if (s - e).EuclideanNorm() > pcbnew.FromMM(0.05) and min(mm(s.y), mm(e.y)) < 81.0 \
                    and max(mm(s.x), mm(e.x)) < 182.0:
                outline.append([point(s), point(e)])
    ground_edge = min(min(p[1] for p in poly) for z in zones if z["net"] == "GND" and z["layer"] != "F.Cu"
                      for poly in z["polygons"])

    bom = {}
    for st_ref, our_ref in PARTS:
        fp = footprints[st_ref]
        bom[st_ref] = {"value": fp.GetValue(), "footprint": fp.GetFPIDAsString(),
                       "pads": {p.GetNumber(): p.GetNetname() for p in fp.Pads()}}

    data = {
        "source": SOURCE,
        "board": "MB1355 rev D-01, MB1355D/MB1355.PcbDoc (KiCad Altium import)",
        "frame": "ST board coordinates, mm, y down",
        "stackup": "MB1355: L1 1.6 mil / 18 mil FR-4 (Dk 4.2) / L2 1.2 mil / 20 mil (Dk 4.4) / L3 / 18 mil / L4; "
                   "the RF line references L3 (L2 is cut out under it)",
        "board_left_x": 113.4507, "tab_top_y": 72.7152, "ground_edge_y": ground_edge,
        "outline_segments": outline,
        "net_map": NET_MAP,
        "parts": parts,
        "st_parts": bom,
        "mcu": {"st": "U1", "ours": "U301", "pads": mcu_pads, "rot": round(u1.GetOrientationDegrees(), 3)},
        "antenna_polygon": antenna,
        "tracks": tracks, "vias": vias, "zones": zones, "rule_areas": rule_areas,
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    # Last: exporting removes items from footprint copies, which leaves pcbnew's SWIG views unusable afterwards.
    for name, (st_ref, description) in exports.items():
        export_footprint(io, footprints[st_ref], description)
    print(f"{OUT.relative_to(ROOT)}: {len(parts)} parts, {len(tracks)} tracks/arcs, {len(vias)} vias, "
          f"{len(zones)} zones, {len(rule_areas)} rule areas; ground edge y {ground_edge:.3f}")
    print("footprints:", ", ".join(sorted(set(exports) | {"MB1355_Meander_Antenna"})))


if __name__ == "__main__":
    main()
