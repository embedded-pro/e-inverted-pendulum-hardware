#!/usr/bin/env python3
"""Extract the motor-driver power stage of TI's BOOST-DRV8711 BoosterPack (SLVC575B design files) (D-040).

TI's files stay in the gitignored reference/boost-drv8711/ (the package zip, its board files unpacked under design/
and gerbers/). This reads BOARD/BOOST-DRV8711.PcbDoc through KiCad 10's Altium importer, like rf_reference.py does for
ST's MB1355, and writes:
  - scripts/pcb/boost_drv8711.json: the power stage's parts (TI ref -> ours, position, rotation, side, pad nets), its
    tracks and vias, and its pours cut to the stage's box, in TI's board frame (KiCad import, mm, y down);
  - the BOOST_* footprints: TI's land patterns, re-centred on their pads, with KiCad library 3D bodies turned to match;
    the net ties rebuilt as KiCad net-tie footprints with TI's pad geometry.
The stage is U1 (DRV8711DCP), Q1-Q4 (CSD88537ND), R1 / R2 (50 mOhm 2512), NT1-NT4 (Kelvin net ties, on the bottom)
and C1-C8. Not copied: the LaunchPad headers J1 / J2, the terminal blocks J5 / J6, the LEDs and R3-R6. Tracks that
leave the box, or end on nothing that is copied, are pruned. The script fails if a copied pad's net is unknown, or if
Q2 / Q4 aren't wired the mirrored way the copy expects.
Every derived file says "Derived from Texas Instruments BOOST-DRV8711 design files (SLVC575B)".

Run: python3 scripts/drv_reference.py
"""

import hashlib
import json
import math
import pathlib
import subprocess
import sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "schgen"))
import rf_reference as RF  # noqa: E402
from make_footprints import footprint, uid  # noqa: E402
from sexpr import Str, Sym, dump, parse  # noqa: E402

REFERENCE = ROOT / "reference" / "boost-drv8711"
PCBDOC = REFERENCE / "design" / "BOARD" / "BOOST-DRV8711.PcbDoc"
OUT = ROOT / "scripts" / "pcb" / "boost_drv8711.json"
PRETTY = RF.PRETTY
LIBRARY = RF.LIBRARY
SOURCE = "Derived from Texas Instruments BOOST-DRV8711 design files (SLVC575B)"
KEYWORDS = "BOOST-DRV8711 DRV8711 TI motor driver"
PREFIX = "BOOST_"
UPLOADS = ("slvc575b.zip", "drv8711_slvsc40h.pdf")

BOX = (125.5, 86.0, 163.6, 123.0)
EPS = 0.001

PARTS = {"U1": "U501", "Q1": "Q501", "Q2": "Q502", "Q3": "Q503", "Q4": "Q504", "R1": "R509", "R2": "R512",
         "NT1": "NT501", "NT2": "NT502", "NT3": "NT503", "NT4": "NT504",
         "C1": "C507", "C2": "C508", "C3": "C510", "C4": "C509", "C5": "C511", "C6": "C512", "C7": "C513", "C8": "C514"}
BULK = "C1"
NET_MAP = {
    "VM": "VBAT", "GND": "GND", "GND_A": "SENSE_A", "GND_B": "SENSE_B",
    "AOUT1": "MOT_R_P", "AOUT2": "MOT_R_N", "BOUT1": "MOT_L_P", "BOUT2": "MOT_L_N",
    "A1HS": "A1HS", "A1LS": "A1LS", "A2HS": "A2HS", "A2LS": "A2LS",
    "B1HS": "B1HS", "B1LS": "B1LS", "B2HS": "B2HS", "B2LS": "B2LS",
    "CP1": "DRV_CP1", "CP2": "DRV_CP2", "VCP": "DRV_VCP", "V5": "DRV_V5", "VINT": "DRV_VINT", "BEMF": "DRV_BEMF",
    "AISENP": "DRV_AISENP", "AISENN": "DRV_AISENN", "BISENP": "DRV_BISENP", "BISENN": "DRV_BISENN",
    "NSLEEP": "DRV_NSLEEP", "RESET": "DRV_RESET", "STEP/AIN1": "DRV_AIN1", "DIR/AIN2": "DRV_AIN2",
    "BIN1": "DRV_BIN1", "BIN2": "DRV_BIN2", "SCLK": "SPI1_SCK_BUS", "SDATI": "SPI1_MOSI", "SCS": "DRV_SCS",
    "SDATO": "SPI1_MISO", "NFAULT": "DRV_NFAULT", "NSTALL": "DRV_NSTALL",
}
MIRRORED = {"Q2": {"1": "GND_A", "2": "A2LS", "4": "A2HS", "5": "VM"},
            "Q4": {"1": "GND_B", "2": "B2LS", "4": "B2HS", "5": "VM"}}
DESCRIPTION = {
    "R-PDSO-G38": "DRV8711DCP HTSSOP-38 PowerPAD land with 12 thermal vias (exposed pad numbered 39 here)",
    "SO-8": "CSD88537ND SO-8 land",
    "2512M": "2512 shunt land (CRA2512 50 mOhm)",
    "0603L": "0603 capacitor land",
    "0805L": "0805 capacitor land",
    "1206L": "1206 capacitor land",
}
MODELS = {  # (KiCad 3D model, KiCad library footprint the model fits)
    "R-PDSO-G38": ("Package_SO.3dshapes/TSSOP-38_4.4x9.7mm_P0.5mm.step", "Package_SO", "TSSOP-38_4.4x9.7mm_P0.5mm"),
    "SO-8": ("Package_SO.3dshapes/SOIC-8_3.9x4.9mm_P1.27mm.step", "Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm"),
    "2512M": ("Resistor_SMD.3dshapes/R_2512_6332Metric.step", "Resistor_SMD", "R_2512_6332Metric"),
    "0603L": ("Capacitor_SMD.3dshapes/C_0603_1608Metric.step", "Capacitor_SMD", "C_0603_1608Metric"),
    "0805L": ("Capacitor_SMD.3dshapes/C_0805_2012Metric.step", "Capacitor_SMD", "C_0805_2012Metric"),
    "1206L": ("Capacitor_SMD.3dshapes/C_1206_3216Metric.step", "Capacitor_SMD", "C_1206_3216Metric"),
}
NET_TIE = PREFIX + "Net-Tie_10mil"

mm = pcbnew.ToMM


def lib_name(fp):
    return fp.GetFPIDAsString().split(":")[-1]


def inside(p):
    return BOX[0] - EPS <= p[0] <= BOX[2] + EPS and BOX[1] - EPS <= p[1] <= BOX[3] + EPS


def xy(v):
    return (round(mm(v.x), 4), round(mm(v.y), 4))


def seg_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def model_rotation(fp, lib, name):
    """The orientation of KiCad's library footprint whose pads coincide with TI's (same numbers), so its 3D body
    can be turned to fit TI's land."""
    ref = pcbnew.FootprintLoad(str(pathlib.Path("/usr/share/kicad/footprints") / f"{lib}.pretty"), name)
    ours = {p.GetNumber(): p.GetFPRelativePosition() for p in fp.Pads() if p.GetNumber() not in ("", "39")}
    best = None
    for angle in (0.0, 90.0, 180.0, 270.0):
        ref.SetOrientationDegrees(angle)
        theirs = {p.GetNumber(): p.GetPosition() - ref.GetPosition() for p in ref.Pads() if p.GetNumber() in ours}
        if not theirs:
            continue
        err = max(math.hypot(mm(theirs[n].x - ours[n].x), mm(theirs[n].y - ours[n].y)) for n in theirs)
        if best is None or err < best[0]:
            best = (err, angle)
    if best is None or best[0] > 0.6:
        sys.exit(f"{name}: no orientation of KiCad's {lib}:{name} fits TI's land (worst {best})")
    return best[1]


def add_model(path, model, angle):
    tree = parse(path.read_text(encoding="utf-8"))
    tree = [n for n in tree if not (isinstance(n, list) and n and n[0] == "model")]
    tree.append([Sym("model"), Str(f"{RF.MODEL_DIR}/{model}"), [Sym("offset"), [Sym("xyz"), 0, 0, 0]],
                 [Sym("scale"), [Sym("xyz"), 1, 1, 1]], [Sym("rotate"), [Sym("xyz"), 0, 0, -angle if angle else 0]]])
    path.write_text(dump(tree) + "\n", encoding="utf-8")


def renumber_exposed_pad(copy):
    for pad in copy.Pads():
        if pad.GetNumber() == "0":
            pad.SetNumber("39")


def write_net_tie(fp):
    """TI's 10 mil net tie (two 0.254 mm pads and a copper bridge) as a KiCad net-tie footprint, on top (the paste flips
    it to B.Cu as TI has it), pad 1 the sense side, pad 2 the power side."""
    pads = {p.GetNumber(): p for p in fp.Pads() if p.GetNumber() in ("1", "2")}
    a, b = xy(pads["1"].GetPosition()), xy(pads["2"].GetPosition())
    centre = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    half = math.dist(a, b) / 2
    size = round(mm(pads["1"].GetSize(pcbnew.B_Cu).x), 4)
    nodes = [[Sym("pad"), Str(str(n)), Sym("smd"), Sym("circle"), [Sym("at"), x, 0], [Sym("size"), size, size],
              [Sym("layers"), Str("F.Cu")], [Sym("uuid"), uid(NET_TIE, "pad", n)]]
             for n, x in ((1, round(-half, 4)), (2, round(half, 4)))]
    bridge = [Sym("fp_line"), [Sym("start"), round(-half, 4), 0], [Sym("end"), round(half, 4), 0],
              [Sym("stroke"), [Sym("width"), size], [Sym("type"), Sym("solid")]], [Sym("layer"), Str("F.Cu")],
              [Sym("uuid"), uid(NET_TIE, "bridge")]]
    m = 0.25
    node = footprint(NET_TIE, f"TI's 10 mil Kelvin net tie, pads {size} mm, {2 * half:.3f} mm apart. {SOURCE}", "smd",
                     (-half - size / 2, -size / 2, half + size / 2, size / 2),
                     (round(-half - size / 2 - m, 3), round(-size / 2 - m, 3), round(half + size / 2 + m, 3),
                      round(size / 2 + m, 3)), nodes, [bridge], silk=False)
    attr = next(i for i in node if isinstance(i, list) and i and i[0] == Sym("attr"))
    attr[1:] = [Sym("smd"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom")]
    node.insert(node.index(attr) + 1, [Sym("net_tie_pad_groups"), Str("1,2")])
    (PRETTY / f"{NET_TIE}.kicad_mod").write_text(dump(node) + "\n", encoding="utf-8")
    return centre


def main():
    if not PCBDOC.exists():
        sys.exit(f"{PCBDOC.relative_to(ROOT)} not found: unpack TI's slvc575b.zip board files into "
                 "reference/boost-drv8711/design (docs/drive.md)")
    io_altium = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.ALTIUM_DESIGNER)
    board = io_altium.LoadBoard(str(PCBDOC), None)
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}

    for ref, wanted in MIRRORED.items():
        got = {p.GetNumber(): p.GetNetname() for p in footprints[ref].Pads()}
        if any(got.get(n) != net for n, net in wanted.items()):
            sys.exit(f"{ref} isn't wired as expected (FET1 low side): {got}")

    parts, pads = [], []
    for st, ours in PARTS.items():
        fp = footprints[st]
        numbered = []
        for pad in fp.Pads():
            number = "39" if (st == "U1" and pad.GetNumber() == "0") else pad.GetNumber()
            if not number:
                continue
            net = pad.GetNetname()
            if net not in NET_MAP:
                sys.exit(f"{st} pad {number}: net {net!r} has no mapping")
            numbered.append([number, *xy(pad.GetPosition()), net])
            through = pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
            pads.append({"layer": "*" if through else ("B.Cu" if fp.IsFlipped() else "F.Cu"), "pad": pad})
        name = None if st == BULK else (NET_TIE if lib_name(fp) == "Net-Tie_10mil" else PREFIX + RF.footprint_name(fp, ""))
        parts.append({"st": st, "ours": ours, "footprint": f"{LIBRARY}:{name}" if name else None,
                      "st_footprint": lib_name(fp), "st_value": fp.GetValue(), "at": list(xy(RF.pad_centre(fp))),
                      "rot": round(fp.GetOrientationDegrees(), 3), "side": "B" if fp.IsFlipped() else "F",
                      "pads": sorted(numbered, key=lambda p: (len(p[0]), p[0]))})

    # Copper of the stage: tracks inside the box on mapped nets, pruned until every end lands on copied copper.
    zones = [z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() in NET_MAP]
    tracks = []
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() not in NET_MAP:
            continue
        a, b = xy(t.GetStart()), xy(t.GetEnd())
        if a == b or not (inside(a) and inside(b)):
            continue
        tracks.append({"layer": board.GetLayerName(t.GetLayer()), "width": round(mm(t.GetWidth()), 4), "a": a, "b": b,
                       "net": t.GetNetname(), "lid": t.GetLayer()})
    vias = [{"at": xy(v.GetPosition()), "size": round(mm(v.GetWidth(pcbnew.F_Cu)), 4), "drill": round(mm(v.GetDrill()), 4),
             "net": v.GetNetname()}
            for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() in NET_MAP and inside(xy(v.GetPosition()))]

    def on_zone(p, lid, net):
        return any(z.GetNetname() == net and z.IsOnLayer(lid) and
                   z.Outline().Contains(pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))) for z in zones)

    def attached(p, t, index):
        for entry in pads:
            pad = entry["pad"]
            if pad.GetNetname() == t["net"] and (entry["layer"] == "*" or pad.IsOnLayer(t["lid"])) and \
                    pad.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(p[0]), pcbnew.FromMM(p[1]))):
                return True
        if any(v["net"] == t["net"] and math.dist(p, v["at"]) <= v["size"] / 2 + EPS for v in vias):
            return True
        if any(i != index and o["lid"] == t["lid"] and o["net"] == t["net"] and
               seg_distance(p, o["a"], o["b"]) <= o["width"] / 2 + EPS for i, o in enumerate(tracks)):
            return True
        return on_zone(p, t["lid"], t["net"])

    while True:
        loose = {i for i, t in enumerate(tracks) if not (attached(t["a"], t, i) and attached(t["b"], t, i))}
        if not loose:
            break
        tracks = [t for i, t in enumerate(tracks) if i not in loose]
    vias = [v for v in vias if any(t["net"] == v["net"] and min(math.dist(v["at"], t["a"]), math.dist(v["at"], t["b"]))
                                   <= v["size"] / 2 + EPS for t in tracks)
            or (on_zone(v["at"], pcbnew.F_Cu, v["net"]) and on_zone(v["at"], pcbnew.B_Cu, v["net"]))]
    pours = []
    for z in zones:
        layer = board.GetLayerName(z.GetLayer())
        polys = RF.zone_part(z, layer, BOX)
        if polys:
            pours.append({"net": z.GetNetname(), "layer": layer, "priority": z.GetAssignedPriority(),
                          "polygons": polys, **RF.zone_settings(z)})

    data = {
        "source": SOURCE,
        "board": "BOOST-DRV8711 BoosterPack, BOARD/BOOST-DRV8711.PcbDoc (KiCad Altium import), 2 layers",
        "files": {f: hashlib.sha256((REFERENCE / f).read_bytes()).hexdigest() for f in UPLOADS},
        "frame": "TI board coordinates (KiCad import), mm, y down",
        "box": list(BOX),
        "st_rules_mm": {"clearance": 0.1778, "pour_clearance": 0.381, "width": 0.1524, "annular_ring": 0.127},
        "net_map": NET_MAP,
        "parts": parts,
        "tracks": [{"layer": t["layer"], "width": t["width"], "start": list(t["a"]), "end": list(t["b"]), "net": t["net"]}
                   for t in tracks],
        "vias": [{"at": list(v["at"]), "size": v["size"], "drill": v["drill"], "net": v["net"]} for v in vias],
        "zones": pours,
        "not_copied": "LaunchPad headers J1 / J2, terminal blocks J5 / J6, LEDs D1 / D2, R3-R6, the logo, and TI's "
                      "routing from the stage to them; C1's through-hole land (our SMD bulk C507 sits at its centre)",
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")

    # Last: exporting modifies footprint copies, which leaves pcbnew's SWIG views unusable afterwards.
    written = {}
    for st in PARTS:
        fp = footprints[st]
        base = lib_name(fp)
        if st == BULK or base in written:
            continue
        if base == "Net-Tie_10mil":
            write_net_tie(fp)
            written[base] = NET_TIE
            continue
        name = RF.export_footprint(io, fp, f"{DESCRIPTION[base]}, TI BOOST-DRV8711", PREFIX, SOURCE, KEYWORDS,
                                   edit=renumber_exposed_pad if st == "U1" else None)
        model, lib, ref_name = MODELS[base]
        saved = pcbnew.FootprintLoad(str(PRETTY), name)
        add_model(PRETTY / f"{name}.kicad_mod", model, model_rotation(saved, lib, ref_name))
        written[base] = name
    subprocess.run(["kicad-cli", "fp", "upgrade", "--force", str(PRETTY)], check=True, capture_output=True)
    print(f"{OUT.relative_to(ROOT)}: {len(parts)} parts, {len(tracks)} tracks, {len(vias)} vias, {len(pours)} pours "
          f"in box {BOX}")
    print("footprints:", ", ".join(sorted(written.values())))


if __name__ == "__main__":
    main()
