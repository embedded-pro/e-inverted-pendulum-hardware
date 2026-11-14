#!/usr/bin/env python3
"""Create or update hardware/e-inverted-pendulum/e-inverted-pendulum.kicad_pcb from the schematic: a scripted "Update PCB from Schematic".

Placement belongs to the owner (D-032): the .kicad_pcb is the source of truth for where parts are and for the
board geometry. This script never moves or reshapes anything that already exists on the board. It:
  - creates what is missing: the 85 x 130 mm outline, the rule areas and reference drawings from placement.py, and the
    bracket holes (placement.MECHANICAL), each only if absent;
  - syncs the schematic: one footprint per symbol with its fields, sheet path, DNP/BOM flags and pad nets; a footprint
    whose library entry changed is swapped in place (position, rotation and lock kept); new parts go to the first
    free spot in the staging area right of the board; parts removed from the schematic are deleted (board-only
    footprints are never deleted);
  - shows only the reference on the silkscreen, at the fab's minimum text size; test pads show their net name instead
    (label_fields, D-035);
  - writes the JLC04161H-7628 stack-up, the net classes (NET_CLASSES, from docs/power-map.md) and the fab rules, the
    strictest of JLCPCB and Seeed (pcb-design-rules skill, pcb_rules.py, D-034), plus the project rules below.

--stage-all (one-shot) moves every unlocked footprint except the bracket holes off the board into the staging area,
one column per schematic sheet, packed by courtyard so nothing overlaps, with the sheet name on Cmts.User.

Coordinates in placement.py are mechanical (docs/mechanical.md): x across the plate, z up from the wheel axle,
both in mm, viewed from the front (component side).

Run: python3 scripts/pcb/board.py [--rules path/to/pcb_rules.py] [--stage-all]
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
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "schgen"))
if "--pcbnew-stage" in sys.argv:
    import pcbnew  # noqa: E402
import placement  # noqa: E402
from sexpr import Str, Sym, dump, parse  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
KICAD = ROOT / "hardware" / "e-inverted-pendulum"
SCHEMATIC = KICAD / "e-inverted-pendulum.kicad_sch"
BOARD = KICAD / "e-inverted-pendulum.kicad_pcb"
PROJECT = KICAD / "e-inverted-pendulum.kicad_pro"
RULES = KICAD / "e-inverted-pendulum.kicad_dru"
SYSTEM_FOOTPRINTS = pathlib.Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
PROJECT_LIBRARY = "e-inverted-pendulum"

ORIGIN = (100.0, 150.0)
CORNER_RADIUS = 1.0

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
    "PWR_BUS": {"track_width": 2.2, "clearance": 0.2,
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
    "RF": {"track_width": 0.25, "clearance": 0.15,
           "patterns": ["RF1", "*/RF_50", "*/RF_ANT", "*/RF_UFL"]},
    "NFC": {"track_width": 0.25, "clearance": 0.15,
            "patterns": ["*/NFC_AC0", "*/NFC_AC1"]},
    "CRYSTAL": {"track_width": 0.2, "clearance": 0.15,
                "patterns": ["*/HSE_IN", "*/HSE_OUT", "*/OSC32_IN", "*/OSC32_OUT"]},
}
DEFAULT_CLASS = {"track_width": 0.2, "clearance": 0.15}

FABS = "jlcpcb,seeed"
CUSTOM_RULES = """
# Project rules (scripts/pcb/board.py). They follow the pcb_rules block, so they win where both match.

(rule "RF1 matching trace: DS12804 Fig. 13 copies a 104 um gap (docs/rf.md)"
  (condition "A.NetName == 'RF1'")
  (constraint clearance (min 0.104mm)))

(rule "AE401 shorting leg: SWRA117D grounds it through a 0.3 mm plated hole in a 0.5 mm land, a via (via ring: JLC 0.05, Seeed 0.10 mm)"
  (condition "A.Type == 'Pad' && A.memberOfFootprint('AE401')")
  (constraint annular_width (min 0.1mm)))
"""

CUSTOM_RULES += """
(rule "Battery on the back: no through-hole pins under it (D-025)"
  (condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole' && A.insideArea('BATTERY_BACK')")
  (constraint disallow pad))

(rule "Bracket strip: no parts except the bracket holes (D-026)"
  (condition "A.Type == 'Footprint' && A.insideArea('BRACKET_STRIP') && A.Reference != 'MB*'")
  (constraint disallow footprint))
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
        return KICAD / f"{PROJECT_LIBRARY}.pretty"
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


def ensure_outline(board):
    if any(item.GetLayer() == pcbnew.Edge_Cuts for item in board.GetDrawings()):
        return
    for shape in outline_shapes():
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
    if any(d.GetLayer() == layer for d in board.GetDrawings()):
        return
    for item in placement.DRAWINGS:
        if item[0] == "rect":
            (x0, z0), (x1, z1) = item[1], item[2]
            shapes = [((x0, z0), (x1, z0)), ((x1, z0), (x1, z1)), ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))]
        else:
            shapes = [(item[1], item[2])]
        for start, end in shapes:
            line = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
            line.SetStart(to_board(*start))
            line.SetEnd(to_board(*end))
            line.SetLayer(layer)
            line.SetWidth(pcbnew.FromMM(0.15))
            board.Add(line)
        if len(item) > 3 and item[3]:
            add_label(board, item[3], to_board((item[1][0] + item[2][0]) / 2.0, max(item[1][1], item[2][1]) - 1.5), layer)


def add_label(board, text, position, layer, size=1.2):
    label = pcbnew.PCB_TEXT(board)
    label.SetText(text)
    label.SetPosition(position)
    label.SetLayer(layer)
    label.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    label.SetTextThickness(pcbnew.FromMM(0.15))
    board.Add(label)
    return label


def ensure_rule_areas(board):
    present = {zone.GetZoneName() for zone in board.Zones() if zone.GetIsRuleArea()}
    for area in placement.RULE_AREAS:
        if area["name"] in present:
            continue
        layers = pcbnew.LSET()
        for layer in area["layers"]:
            layers.AddLayer(board.GetLayerID(layer))
        zone = pcbnew.ZONE(board)
        zone.SetIsRuleArea(True)
        zone.SetZoneName(area["name"])
        zone.SetLayerSet(layers)
        outline = zone.Outline()
        outline.NewOutline()
        for x, z in area["polygon"]:
            outline.Append(to_board(x, z))
        zone.SetDoNotAllowTracks("tracks" in area["deny"])
        zone.SetDoNotAllowVias("vias" in area["deny"])
        zone.SetDoNotAllowPads("pads" in area["deny"])
        zone.SetDoNotAllowZoneFills("pour" in area["deny"])
        zone.SetDoNotAllowFootprints("footprints" in area["deny"])
        board.Add(zone)


def fingerprint(fp):
    pads = sorted((p.GetNumber(), p.GetSize(pcbnew.F_Cu).x, p.GetSize(pcbnew.F_Cu).y, p.GetDrillSize().x,
                   p.GetDrillSize().y, int(p.GetAttribute()), p.GetLayerSet().Seq().size(),
                   p.GetFPRelativePosition().x, p.GetFPRelativePosition().y) for p in fp.Pads())
    zones = sorted(z.GetLayerSet().Seq().size() for z in fp.Zones())
    angle = fp.GetOrientationDegrees()
    fp.SetOrientationDegrees(0)
    fp.BuildCourtyardCaches()
    box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    courtyard = (round(box.GetWidth(), -4), round(box.GetHeight(), -4))
    fp.SetOrientationDegrees(angle)
    return fp.GetLibDescription(), tuple(pads), tuple(zones), courtyard


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


SILK_TEXT_MIN = (1.0, 0.15)


def label_fields(fp):
    """Only the reference is shown on the board; test pads show their net name instead (D-035).

    Net ties keep their reference hidden. Silkscreen text is raised to the fab minimum (JLCPCB 1.0 mm high, 0.15 mm
    line; Seeed allows less) and never lowered. A test pad's label is moved onto the silkscreen once; after that its
    position is the owner's.
    """
    reference, value = fp.Reference(), fp.Value()
    lib_id = fp.GetFPIDAsString()
    if lib_id.startswith("TestPoint:"):
        reference.SetVisible(False)
        if not value.IsVisible() or value.GetLayer() != pcbnew.F_SilkS:
            value.SetLayer(pcbnew.F_SilkS)
            value.SetPosition(reference.GetPosition())
            value.SetVisible(True)
    else:
        value.SetVisible(False)
        reference.SetVisible(not lib_id.startswith("NetTie:"))
    height, thickness = (pcbnew.FromMM(v) for v in SILK_TEXT_MIN)
    for item in [reference, value] + [g for g in fp.GraphicalItems() if g.GetClass() == "PCB_TEXT"]:
        if item.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            size = item.GetTextSize()
            item.SetTextSize(pcbnew.VECTOR2I(max(size.x, height), max(size.y, height)))
            item.SetTextThickness(max(item.GetTextThickness(), thickness))


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
            fp.SetPosition(to_board(item["x"], item["z"]))
            fp.SetOrientationDegrees(item.get("rot", 0.0))
            board.Add(fp)
            existing[item["ref"]] = fp
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
    existing = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, fp in list(existing.items()):
        if ref not in components and not fp.IsBoardOnly():
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
            place_in_free_spot(board, fp)
            board.Add(fp)
            staged += 1
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
    for item in child(tree, Sym("paper")):
        item[1:] = [Str("A3")]
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
    subprocess.run([sys.executable, str(script), "apply", str(PROJECT), "--fab", FABS, "--netclasses"], check=True)
    text = RULES.read_text(encoding="utf-8")
    marker = "# Project rules ("
    if marker in text:
        text = text[:text.index(marker)].rstrip() + "\n"
    RULES.write_text(text + CUSTOM_RULES, encoding="utf-8")


def footprint_box(fp):
    fp.BuildCourtyardCaches()
    box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    return box if box.GetWidth() else fp.GetBoundingBox(False)


def place_in_free_spot(board, fp):
    """Put a new part in the staging area at the first spot clear of every footprint already on the board.

    Rows are scanned top-down from the board's top edge, 1 mm apart; along a row the scan jumps past each footprint
    whose box overlaps the band, so new parts never land on staged or placed ones (D-032).
    """
    box = footprint_box(fp)
    w, h, gap = box.GetWidth(), box.GetHeight(), pcbnew.FromMM(STAGE_GAP)
    boxes = []
    for other in board.GetFootprints():
        b = footprint_box(other)
        boxes.append((b.GetLeft() - gap, b.GetTop() - gap, b.GetRight() + gap, b.GetBottom() + gap))
    right = to_board(placement.WIDTH / 2.0, 0.0).x
    x_start, x_limit = right + pcbnew.FromMM(10.0), right + pcbnew.FromMM(STAGE_ROW_WIDTH)
    y = to_board(0.0, placement.TOP_Z).y + pcbnew.FromMM(4.0)
    while True:
        x = x_start
        for b in sorted((b for b in boxes if b[1] < y + h and b[3] > y), key=lambda b: b[0]):
            if b[2] <= x:
                continue
            if x + w <= b[0]:
                break
            x = b[2]
        if x + w <= x_limit:
            fp.SetPosition(pcbnew.VECTOR2I(x, y) + (fp.GetPosition() - box.GetPosition()))
            return
        y += pcbnew.FromMM(1.0)


STAGE_LABEL = "STAGING: "
STAGE_COLUMN_WIDTH = 46.0
STAGE_GAP = 1.0
STAGE_ROW_WIDTH = 210.0


def stage_all(board):
    keep = {item["ref"] for item in placement.MECHANICAL}
    for item in [d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT" and d.GetText().startswith(STAGE_LABEL)]:
        board.Delete(item)
    groups = {}
    for fp in board.GetFootprints():
        if fp.IsLocked() or fp.GetReference() in keep:
            continue
        group = fp.GetSheetname() or "Mechanical (owner to place)"
        groups.setdefault(group, []).append(fp)
    right = to_board(placement.WIDTH / 2.0, 0.0).x
    top = to_board(0.0, placement.TOP_Z).y
    gap, width = pcbnew.FromMM(STAGE_GAP), pcbnew.FromMM(STAGE_COLUMN_WIDTH)
    first_x, limit = right + pcbnew.FromMM(10.0), right + pcbnew.FromMM(STAGE_ROW_WIDTH)
    column_x, row_y, row_height = first_x, top + pcbnew.FromMM(4.0), 0
    moved = 0
    for group in sorted(groups):
        if column_x > first_x and column_x + width > limit:
            column_x, row_y, row_height = first_x, row_y + row_height + pcbnew.FromMM(10.0), 0
        parts = sorted(groups[group], key=lambda f: (f.GetFPIDAsString(), f.GetReference()))
        label = add_label(board, STAGE_LABEL + group, pcbnew.VECTOR2I(column_x, row_y - pcbnew.FromMM(3.0)),
                          pcbnew.Cmts_User, size=1.2)
        label.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        x, y, shelf = column_x, row_y, 0
        widest = 0
        for fp in parts:
            fp.SetOrientationDegrees(0)
            fp.BuildCourtyardCaches()
            box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            if box.GetWidth() == 0:
                box = fp.GetBoundingBox(False)
            w, h = box.GetWidth(), box.GetHeight()
            if x > column_x and x + w > column_x + width:
                x, y, shelf = column_x, y + shelf + gap, 0
            offset = fp.GetPosition() - box.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(x, y) + offset)
            x += w + gap
            shelf = max(shelf, h)
            widest = max(widest, x - column_x)
            moved += 1
        row_height = max(row_height, y + shelf - row_y)
        column_x += max(width, widest) + pcbnew.FromMM(8.0)
    return moved


def build_board(stage=False):
    components, nets, pins = read_netlist()
    board = pcbnew.LoadBoard(str(BOARD)) if BOARD.exists() else pcbnew.NewBoard(str(BOARD))
    board.SetCopperLayerCount(4)
    block = board.GetTitleBlock()
    block.SetTitle("e-inverted-pendulum: chassis PCB")
    block.SetCompany("embedded-pro")
    block.SetRevision("A (draft)")
    block.SetComment(0, "4 layers, 1.6 mm, 1 oz outer / 0.5 oz inner: JLC04161H-7628 or Seeed 0.2 mm prepreg (D-008, D-034)")
    block.SetComment(1, "Outline 85 x 130 mm (D-024); see docs/mechanical.md and docs/rf.md")

    ensure_outline(board)
    footprints = sync_footprints(board, components, nets, pins)
    ensure_mechanical(board, footprints)
    for fp in board.GetFootprints():
        label_fields(fp)
    ensure_rule_areas(board)
    ensure_drawings(board)
    staged = stage_all(board) if stage else 0
    board.GetDesignSettings().SetGridOrigin(to_board(0.0, 0.0))
    board.GetDesignSettings().SetAuxOrigin(to_board(-placement.WIDTH / 2.0, placement.BOTTOM_Z))
    pcbnew.SaveBoard(str(BOARD), board)
    print(f"{BOARD.name}: {len(components)} schematic parts, {len(nets)} nets, "
          f"{len(placement.MECHANICAL)} bracket holes" + (f", {staged} footprints staged" if stage else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rules", type=pathlib.Path, help="pcb_rules.py from the pcb-design-rules skill")
    parser.add_argument("--stage-all", action="store_true",
                        help="move every unlocked footprint except the bracket holes into the staging area (one-shot)")
    parser.add_argument("--pcbnew-stage", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pcbnew_stage:
        build_board(stage=args.stage_all)
        return
    # pcbnew rewrites the .kicad_pro when its process exits (power-pcb-layout s6.2), so the board is built in a
    # child process and the project, stack-up and rules are written after it has gone.
    subprocess.run([sys.executable, __file__, "--pcbnew-stage"] + (["--stage-all"] if args.stage_all else []), check=True)
    write_stackup()
    write_net_classes()
    if args.rules:
        apply_rules(args.rules)
    project = PROJECT.read_bytes()
    subprocess.run(["kicad-cli", "pcb", "upgrade", "--force", str(BOARD)], check=True, capture_output=True)
    PROJECT.write_bytes(project)


if __name__ == "__main__":
    main()
