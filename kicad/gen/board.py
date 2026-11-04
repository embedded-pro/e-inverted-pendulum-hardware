#!/usr/bin/env python3
"""Create or update kicad/e-inverted-pendulum.kicad_pcb from the schematic: a scripted "Update PCB from Schematic".

What it owns (docs/mechanical.md, docs/rf.md, docs/power-map.md, D-008, D-024):
  - board outline 85 x 130 mm with 1 mm corner radii, battery strap slots;
  - JLC04161H-7628 stack-up, title block;
  - board-only mechanical footprints (motor-mount slots, bumper holes) and rule areas (antenna keep-out,
    battery zone);
  - one footprint per schematic symbol with its fields, sheet path, DNP/BOM flags and pad nets;
  - net classes (NET_CLASSES, from docs/power-map.md) and the JLC rules (pcb-design-rules skill, pcb_rules.py).

Re-running keeps every footprint where it is. Locked footprints are never moved. Footprints listed in
placement.ANCHORS are moved to their anchor position only while they are unlocked (drafts before owner approval).
Everything else that is new goes to a staging area right of the board.

Coordinates in placement.py are mechanical (docs/mechanical.md): x across the plate, z up from the wheel axle,
both in mm, viewed from the top (component) side.

Run: python3 kicad/gen/board.py [--rules path/to/pcb_rules.py]
"""

import argparse
import json
import math
import os
import pathlib
import subprocess
import sys
import tempfile


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
if "--pcbnew-stage" in sys.argv:
    import pcbnew  # noqa: E402
import placement  # noqa: E402
from sexpr import Str, Sym, dump, parse  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
KICAD = ROOT / "kicad"
SCHEMATIC = KICAD / "e-inverted-pendulum.kicad_sch"
BOARD = KICAD / "e-inverted-pendulum.kicad_pcb"
PROJECT = KICAD / "e-inverted-pendulum.kicad_pro"
RULES = KICAD / "e-inverted-pendulum.kicad_dru"
SYSTEM_FOOTPRINTS = pathlib.Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
PROJECT_LIBRARY = "e-inverted-pendulum"

ORIGIN = (100.0, 150.0)
CORNER_RADIUS = 1.0
STAGING = (160.0, 40.0)

STACKUP = [
    ("F.SilkS", "Top Silk Screen", None, None, None),
    ("F.Paste", "Top Solder Paste", None, None, None),
    ("F.Mask", "Top Solder Mask", 0.01, None, None),
    ("F.Cu", "copper", 0.035, None, None),
    ("dielectric 1", "prepreg", 0.2104, "7628", 4.4),
    ("In1.Cu", "copper", 0.0152, None, None),
    ("dielectric 2", "core", 1.065, "FR4", 4.6),
    ("In2.Cu", "copper", 0.0152, None, None),
    ("dielectric 3", "prepreg", 0.2104, "7628", 4.4),
    ("B.Cu", "copper", 0.035, None, None),
    ("B.Mask", "Bottom Solder Mask", 0.01, None, None),
    ("B.Paste", "Bottom Solder Paste", None, None, None),
    ("B.SilkS", "Bottom Silk Screen", None, None, None),
]

NET_CLASSES = {
    "PWR_BUS": {"track_width": 1.3, "clearance": 0.2,
                "patterns": ["VBAT", "*/BAT_P", "*/BAT_F", "*/PP_S"]},
    "MOTOR": {"track_width": 0.8, "clearance": 0.2,
              "patterns": ["MOT_L_P", "MOT_L_N", "MOT_R_P", "MOT_R_N", "*/SENSE_A", "*/SENSE_B"]},
    "GATE": {"track_width": 0.3, "clearance": 0.15,
             "patterns": ["*/A?HS_?", "*/A?LS_?", "*/B?HS_?", "*/B?LS_?", "*/PP_G", "*/DRV_CP1", "*/DRV_CP2"]},
    "SENSE": {"track_width": 0.2, "clearance": 0.15, "diff_pair_width": 0.2, "diff_pair_gap": 0.2,
              "patterns": ["*/DRV_?ISENP", "*/DRV_?ISENN", "*/KELVIN_?N", "VBAT_SENSE"]},
    "SWITCH": {"track_width": 0.5, "clearance": 0.15,
               "patterns": ["*/BUCK_SW", "*/SMPS_LX", "*/SMPS_MID"]},
    "SUPPLY": {"track_width": 0.5, "clearance": 0.15,
               "patterns": ["+5V", "+3V3", "VDDA", "*/ENC_VCC", "*/DRV_V5", "*/DRV_VINT", "*/DRV_VCP"]},
    "RF": {"track_width": 0.27, "clearance": 0.15,
           "patterns": ["RF1", "*/RF_50", "*/RF_ANT", "*/RF_UFL"]},
    "CRYSTAL": {"track_width": 0.2, "clearance": 0.15,
                "patterns": ["*/HSE_IN", "*/HSE_OUT", "*/OSC32_IN", "*/OSC32_OUT"]},
}
DEFAULT_CLASS = {"track_width": 0.2, "clearance": 0.15}

CUSTOM_RULES = """
# Project rules (kicad/gen/board.py). They follow the pcb_rules block, so they win where both match.

(rule "RF1 matching trace: DS12804 Fig. 13 copies a 104 um gap (docs/rf.md)"
  (condition "A.NetName == 'RF1'")
  (constraint clearance (min 0.1mm)))

(rule "AE401 shorting leg: SWRA117D grounds it through a 0.3 mm plated hole in a 0.5 mm land, a via (JLC via ring 0.05 mm)"
  (condition "A.Type == 'Pad' && A.memberOfFootprint('AE401')")
  (constraint annular_width (min 0.1mm)))
"""

CUSTOM_RULES += """
(rule "NPTH to copper: screw threads touch the hole wall; washers and brackets are kept off by the footprint keep-out"
  (condition "A.Type == 'Pad' && A.Pad_Type == 'NPTH, mechanical'")
  (constraint hole_clearance (min 0.5mm)))
"""

MASK_BRIDGES_ALLOWED = {
    "J401": "Hirose U.FL-R-SMT land pattern: one solder-mask opening over the signal and ground pads",
}


def to_board(x, z):
    return pcbnew.VECTOR2I(pcbnew.FromMM(ORIGIN[0] + x), pcbnew.FromMM(ORIGIN[1] - z))


def child(node, key):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == key]


def value_of(node, key, default=None):
    found = child(node, key)
    return str(found[0][1]) if found and len(found[0]) > 1 else default


def read_netlist():
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "board.net"
        subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(path),
                        str(SCHEMATIC)], check=True, capture_output=True)
        tree = parse(path.read_text(encoding="utf-8"))
    components = {}
    for comp in child(child(tree, "components")[0], "comp"):
        ref = value_of(comp, "ref")
        properties = {value_of(p, "name"): value_of(p, "value", "") for p in child(comp, "property")}
        fields = {value_of(f, "name"): (str(f[2]) if len(f) > 2 else "") for f in child(child(comp, "fields")[0], "field")}
        sheet = child(comp, "sheetpath")[0]
        components[ref] = {
            "value": value_of(comp, "value"), "footprint": value_of(comp, "footprint"),
            "fields": {k: v for k, v in fields.items() if k not in ("Footprint", "Datasheet", "Description")},
            "datasheet": fields.get("Datasheet", ""), "description": fields.get("Description", ""),
            "path": value_of(sheet, "tstamps") + value_of(comp, "tstamps"),
            "sheetname": properties.get("Sheetname", ""), "sheetfile": properties.get("Sheetfile", ""),
            "dnp": "dnp" in properties, "exclude_from_bom": "exclude_from_bom" in properties,
            "exclude_from_board": "exclude_from_board" in properties,
        }
    pins = {}
    nets = []
    for net in child(child(tree, "nets")[0], "net"):
        name = value_of(net, "name")
        nets.append(name)
        for node in child(net, "node"):
            pins[(value_of(node, "ref"), value_of(node, "pin"))] = name
    return components, nets, pins


def library_path(nickname):
    if nickname == PROJECT_LIBRARY:
        return KICAD / "lib" / f"{PROJECT_LIBRARY}.pretty"
    return SYSTEM_FOOTPRINTS / f"{nickname}.pretty"


def load_footprint(board, lib_id):
    nickname, name = lib_id.split(":", 1)
    fp = pcbnew.FootprintLoad(str(library_path(nickname)), name)
    if fp is None:
        raise SystemExit(f"footprint {lib_id} not found in {library_path(nickname)}")
    fp.SetFPID(pcbnew.LIB_ID(nickname, name))
    fp.SetParent(board)
    return fp


def outline_shapes():
    w, top, bottom, r = placement.WIDTH / 2.0, placement.TOP_Z, placement.BOTTOM_Z, CORNER_RADIUS
    shapes = [
        ("line", (-w + r, top), (w - r, top)), ("line", (w, top - r), (w, bottom + r)),
        ("line", (w - r, bottom), (-w + r, bottom)), ("line", (-w, bottom + r), (-w, top - r)),
        ("arc", (w - r, top - r), (w, top - r), 90), ("arc", (-w + r, top - r), (-w + r, top), 90),
        ("arc", (-w + r, bottom + r), (-w, bottom + r), 90), ("arc", (w - r, bottom + r), (w - r, bottom), 90),
    ]
    for slot in placement.STRAP_SLOTS:
        x, z, half, rr = slot["x"], slot["z"], (slot["length"] - slot["width"]) / 2.0, slot["width"] / 2.0
        shapes += [("line", (x - half, z + rr), (x + half, z + rr)), ("line", (x + half, z - rr), (x - half, z - rr)),
                   ("arc", (x + half, z), (x + half, z - rr), 180), ("arc", (x - half, z), (x - half, z + rr), 180)]
    return shapes


def rotate(centre, point, degrees):
    a = math.radians(degrees)
    dx, dz = point[0] - centre[0], point[1] - centre[1]
    return (round(centre[0] + dx * math.cos(a) - dz * math.sin(a), 6),
            round(centre[1] + dx * math.sin(a) + dz * math.cos(a), 6))


def shape_points(shape):
    if shape[0] == "line":
        return [to_board(*shape[1]), to_board(*shape[2])]
    _, centre, start, sweep = shape
    return [to_board(*start), to_board(*rotate(centre, start, sweep / 2.0)), to_board(*rotate(centre, start, sweep))]


def signature(points):
    return tuple(sorted((round(p.x, -3), round(p.y, -3)) for p in points))


def ensure_outline(board):
    target = outline_shapes()
    edges = [item for item in board.GetDrawings() if item.GetLayer() == pcbnew.Edge_Cuts]
    have = sorted(signature([e.GetStart(), e.GetEnd()] + ([e.GetArcMid()] if e.GetShape() == pcbnew.SHAPE_T_ARC else []))
                  for e in edges)
    if have == sorted(signature(shape_points(shape)) for shape in target):
        return
    for item in edges:
        board.Delete(item)
    for shape in target:
        points = shape_points(shape)
        item = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT if shape[0] == "line" else pcbnew.SHAPE_T_ARC)
        if shape[0] == "line":
            item.SetStart(points[0])
            item.SetEnd(points[1])
        else:
            item.SetArcGeometry(points[0], points[1], points[2])
        item.SetLayer(pcbnew.Edge_Cuts)
        item.SetWidth(pcbnew.FromMM(0.1))
        board.Add(item)


def ensure_drawings(board):
    layer = pcbnew.Dwgs_User
    target = []
    for item in placement.DRAWINGS:
        if item[0] == "rect":
            (x0, z0), (x1, z1) = item[1], item[2]
            target += [("line", (x0, z0), (x1, z0)), ("line", (x1, z0), (x1, z1)),
                       ("line", (x1, z1), (x0, z1)), ("line", (x0, z1), (x0, z0))]
        else:
            target.append(("line", item[1], item[2]))
    texts = [(item[3], (item[1][0] + item[2][0]) / 2.0, max(item[1][1], item[2][1]) - 1.5)
             for item in placement.DRAWINGS if len(item) > 3 and item[3]]
    lines = [d for d in board.GetDrawings() if d.GetLayer() == layer and d.GetClass() == "PCB_SHAPE"]
    labels = [d for d in board.GetDrawings() if d.GetLayer() == layer and d.GetClass() == "PCB_TEXT"]
    same_lines = (sorted(signature([d.GetStart(), d.GetEnd()]) for d in lines)
                  == sorted(signature(shape_points(t)) for t in target))
    same_texts = sorted((t.GetText(), t.GetPosition().x, t.GetPosition().y) for t in labels) == sorted(
        (text, to_board(x, z).x, to_board(x, z).y) for text, x, z in texts)
    if same_lines and same_texts:
        return
    for item in lines + labels:
        board.Delete(item)
    for shape in target:
        start, end = shape_points(shape)
        line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(start)
        line.SetEnd(end)
        line.SetLayer(layer)
        line.SetWidth(pcbnew.FromMM(0.15))
        board.Add(line)
    for text, x, z in texts:
        label = pcbnew.PCB_TEXT(board)
        label.SetText(text)
        label.SetPosition(to_board(x, z))
        label.SetLayer(layer)
        label.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.2), pcbnew.FromMM(1.2)))
        label.SetTextThickness(pcbnew.FromMM(0.15))
        board.Add(label)


def ensure_rule_areas(board):
    current = {zone.GetZoneName(): zone for zone in board.Zones() if zone.GetIsRuleArea()}
    for area in placement.RULE_AREAS:
        layers = pcbnew.LSET()
        for layer in area["layers"]:
            layers.AddLayer(board.GetLayerID(layer))
        points = [to_board(x, z) for x, z in area["polygon"]]
        zone = current.get(area["name"])
        if zone is not None:
            outline = zone.Outline()
            existing = [outline.CVertex(i) for i in range(outline.TotalVertices())]
            same = ([(p.x, p.y) for p in existing] == [(p.x, p.y) for p in points]
                    and zone.GetLayerSet().Seq().size() == layers.Seq().size())
            if same:
                continue
            board.Delete(zone)
        zone = pcbnew.ZONE(board)
        zone.SetIsRuleArea(True)
        zone.SetZoneName(area["name"])
        zone.SetLayerSet(layers)
        outline = zone.Outline()
        outline.NewOutline()
        for point in points:
            outline.Append(point)
        board.Add(zone)
    for area in placement.RULE_AREAS:
        zone = next(z for z in board.Zones() if z.GetIsRuleArea() and z.GetZoneName() == area["name"])
        zone.SetDoNotAllowTracks("tracks" in area["deny"])
        zone.SetDoNotAllowVias("vias" in area["deny"])
        zone.SetDoNotAllowPads("pads" in area["deny"])
        zone.SetDoNotAllowZoneFills("pour" in area["deny"])
        zone.SetDoNotAllowFootprints("footprints" in area["deny"])


def fingerprint(fp):
    pads = sorted((p.GetNumber(), p.GetSize(pcbnew.F_Cu).x, p.GetSize(pcbnew.F_Cu).y, p.GetDrillSize().x,
                   p.GetDrillSize().y, int(p.GetAttribute()), p.GetLayerSet().Seq().size(),
                   p.GetFPRelativePosition().x, p.GetFPRelativePosition().y) for p in fp.Pads())
    zones = sorted(z.GetLayerSet().Seq().size() for z in fp.Zones())
    return fp.GetLibDescription(), tuple(pads), tuple(zones)


_LIBRARY_CACHE = {}


def library_fingerprint(board, lib_id):
    if lib_id not in _LIBRARY_CACHE:
        _LIBRARY_CACHE[lib_id] = fingerprint(load_footprint(board, lib_id))
    return _LIBRARY_CACHE[lib_id]


def replace_footprint(board, fp, lib_id):
    position, orientation, locked = fp.GetPosition(), fp.GetOrientationDegrees(), fp.IsLocked()
    board.Delete(fp)
    fresh = load_footprint(board, lib_id)
    fresh.SetPosition(position)
    fresh.SetOrientationDegrees(orientation)
    fresh.SetLocked(locked)
    board.Add(fresh)
    return fresh


def ensure_mechanical(board, existing):
    for item in placement.MECHANICAL:
        fp = existing.get(item["ref"])
        lib_id = f"{PROJECT_LIBRARY}:{item['footprint']}"
        if fp is not None and fingerprint(fp) != library_fingerprint(board, lib_id):
            fp = replace_footprint(board, fp, lib_id)
            fp.SetReference(item["ref"])
            fp.SetValue(item["value"])
            existing[item["ref"]] = fp
        if fp is None:
            fp = load_footprint(board, f"{PROJECT_LIBRARY}:{item['footprint']}")
            fp.SetReference(item["ref"])
            fp.SetValue(item["value"])
            board.Add(fp)
            existing[item["ref"]] = fp
        if not fp.IsLocked():
            fp.SetPosition(to_board(item["x"], item["z"]))
            fp.SetOrientationDegrees(item.get("rot", 0.0))
        fp.SetBoardOnly(True)
        fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)


def sync_footprints(board, components, nets, pins):
    netinfo = {}
    for name in [""] + nets:
        found = board.FindNet(name)
        if found is None:
            found = pcbnew.NETINFO_ITEM(board, name)
            board.Add(found)
        netinfo[name] = found
    mechanical = {item["ref"] for item in placement.MECHANICAL}
    existing = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, fp in list(existing.items()):
        if ref not in components and ref not in mechanical:
            board.Delete(fp)
            del existing[ref]
    staged = 0
    for ref in sorted(components, key=lambda r: (components[r]["sheetfile"], r)):
        comp = components[ref]
        if comp["exclude_from_board"] or not comp["footprint"]:
            continue
        fp = existing.get(ref)
        if fp is not None and (fp.GetFPIDAsString() != comp["footprint"]
                               or fingerprint(fp) != library_fingerprint(board, comp["footprint"])):
            fp = replace_footprint(board, fp, comp["footprint"])
        elif fp is None:
            fp = load_footprint(board, comp["footprint"])
            column, row = divmod(staged, 14)
            fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(STAGING[0] + 9.0 * column),
                                           pcbnew.FromMM(STAGING[1] + 9.0 * row)))
            staged += 1
            board.Add(fp)
        fp.SetReference(ref)
        fp.SetValue(comp["value"])
        for name, value in comp["fields"].items():
            fp.SetField(name, value)
            field = fp.GetField(name)
            field.SetVisible(False)
            field.SetLayer(pcbnew.F_Fab)
            field.SetPosition(fp.GetPosition())
        fp.SetPath(pcbnew.KIID_PATH(comp["path"]))
        fp.SetSheetname(comp["sheetname"])
        fp.SetSheetfile(comp["sheetfile"])
        fp.SetDNP(comp["dnp"])
        fp.SetExcludedFromBOM(comp["exclude_from_bom"])
        fp.SetExcludedFromPosFiles(comp["dnp"])
        fp.SetAllowSolderMaskBridges(ref in MASK_BRIDGES_ALLOWED)
        for pad in fp.Pads():
            net = pins.get((ref, pad.GetNumber()))
            pad.SetNet(netinfo[net] if net else netinfo[""])
        anchor = placement.ANCHORS.get(ref)
        if anchor is not None and not fp.IsLocked():
            x, z, rotation = anchor[:3]
            fp.SetPosition(to_board(x, z))
            fp.SetOrientationDegrees(rotation)
        existing[ref] = fp
    return existing


def write_stackup():
    text = BOARD.read_text(encoding="utf-8")
    tree = parse(text)
    setup = child(tree, Sym("setup"))[0]
    setup[1:] = [c for c in setup[1:] if not (isinstance(c, list) and c and c[0] == "stackup")]
    stack = [Sym("stackup")]
    for name, kind, thickness, material, epsilon in STACKUP:
        layer = [Sym("layer"), Str(name), [Sym("type"), Str(kind)]]
        if thickness is not None:
            layer.append([Sym("thickness"), thickness])
        if material is not None:
            layer += [[Sym("material"), Str(material)], [Sym("epsilon_r"), epsilon], [Sym("loss_tangent"), 0.02]]
        stack.append(layer)
    stack += [[Sym("copper_finish"), Str("HAL lead-free")], [Sym("dielectric_constraints"), Sym("no")]]
    setup.insert(1, stack)
    general = child(tree, Sym("general"))[0]
    for item in child(general, Sym("thickness")):
        item[1] = 1.6
    BOARD.write_text(dump(tree) + "\n", encoding="utf-8")


def write_net_classes():
    project = json.loads(PROJECT.read_text(encoding="utf-8")) if PROJECT.exists() else {}
    template = {"bus_width": 12, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2,
                "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1, "pcb_color": "rgba(0, 0, 0, 0.000)",
                "schematic_color": "rgba(0, 0, 0, 0.000)", "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6}
    classes = [dict(template, name="Default", priority=2147483647, **DEFAULT_CLASS)]
    patterns = []
    for priority, (name, spec) in enumerate(NET_CLASSES.items()):
        values = {k: v for k, v in spec.items() if k != "patterns"}
        classes.append(dict(template, name=name, priority=priority, **values))
        patterns += [{"netclass": name, "pattern": pattern} for pattern in spec["patterns"]]
    settings = project.setdefault("net_settings", {})
    settings.update({"classes": classes, "meta": {"version": 4}, "net_colors": None,
                     "netclass_assignments": None, "netclass_patterns": patterns})
    PROJECT.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")


def apply_rules(script):
    subprocess.run([sys.executable, str(script), "apply", str(PROJECT), "--fab", "jlcpcb", "--netclasses"], check=True)
    text = RULES.read_text(encoding="utf-8")
    marker = "# Project rules (kicad/gen/board.py)"
    if marker in text:
        text = text[:text.index(marker)].rstrip() + "\n"
    RULES.write_text(text + CUSTOM_RULES, encoding="utf-8")


def build_board():
    components, nets, pins = read_netlist()
    board = pcbnew.LoadBoard(str(BOARD)) if BOARD.exists() else pcbnew.NewBoard(str(BOARD))
    board.SetCopperLayerCount(4)
    block = board.GetTitleBlock()
    block.SetTitle("e-inverted-pendulum: chassis PCB")
    block.SetCompany("embedded-pro")
    block.SetRevision("A (draft)")
    block.SetComment(0, "JLC04161H-7628, 4 layers, 1.6 mm, 1 oz outer / 0.5 oz inner (D-008)")
    block.SetComment(1, "Outline 85 x 130 mm (D-024); see docs/mechanical.md and docs/rf.md")

    ensure_outline(board)
    footprints = sync_footprints(board, components, nets, pins)
    ensure_mechanical(board, footprints)
    ensure_rule_areas(board)
    ensure_drawings(board)
    board.GetDesignSettings().SetGridOrigin(to_board(0.0, 0.0))
    board.GetDesignSettings().SetAuxOrigin(to_board(-placement.WIDTH / 2.0, placement.BOTTOM_Z))
    pcbnew.SaveBoard(str(BOARD), board)
    anchored = sum(1 for ref in footprints if ref in placement.ANCHORS)
    print(f"{BOARD.name}: {len(components)} schematic parts, {len(nets)} nets, "
          f"{len(placement.MECHANICAL)} mechanical, {anchored} anchors")


LAYOUT_DOC = ROOT / "docs" / "layout.md"


def write_anchor_table():
    if not LAYOUT_DOC.exists():
        return
    rows = ["| Ref | x | z | Rot | Why |", "|---|---|---|---|---|"]
    rows += [f"| {ref} | {x:+.2f} | {z:+.2f} | {rot} | {why} |" for ref, (x, z, rot, why) in placement.ANCHORS.items()]
    rows += [f"| {m['ref']} | {m['x']:+.2f} | {m['z']:+.2f} | {m.get('rot', 0)} | {m['value']} ({m['footprint']}) |"
             for m in placement.MECHANICAL]
    text = LAYOUT_DOC.read_text(encoding="utf-8")
    begin, end = "<!-- BEGIN anchors (kicad/gen/board.py) -->", "<!-- END anchors -->"
    head, rest = text.split(begin, 1)
    tail = rest.split(end, 1)[1]
    LAYOUT_DOC.write_text(head + begin + "\n" + "\n".join(rows) + "\n" + end + tail, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rules", type=pathlib.Path, help="pcb_rules.py from the pcb-design-rules skill")
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        build_board()
        return
    # pcbnew rewrites the .kicad_pro when its process exits (power-pcb-layout s6.2), so the board is built in a
    # child process and the project, stack-up and rules are written after it has gone.
    subprocess.run([sys.executable, __file__, "--pcbnew-stage"], check=True)
    write_stackup()
    write_net_classes()
    if args.rules:
        apply_rules(args.rules)
    project = PROJECT.read_bytes()
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(BOARD)], check=True, capture_output=True)
    PROJECT.write_bytes(project)
    write_anchor_table()


if __name__ == "__main__":
    main()
