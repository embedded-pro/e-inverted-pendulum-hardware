"""Emit a hierarchical KiCad 10 schematic from a Python description of parts and pin nets.

Every pin gets a short stub ending in a net label (local, global or a power symbol), so parts
can be placed on a grid without drawing wires between them.
"""

import uuid

from library import load
from sexpr import Str, Sym, dump

VERSION, GENERATOR_VERSION = 20260306, "10.0"
PROJECT = "e-inverted-pendulum"
GRID = 2.54
STUB = 2.54
FONT = [Sym("font"), [Sym("size"), 1.27, 1.27]]
POWER_SYMBOLS = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V", "VBAT": "power:VCC",
                 "VDDA": "power:VDDA"}
PAPERS = [("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594)]
NAMESPACE = uuid.UUID("6b7d1c38-0d55-4c4c-9a77-3f0a1e5e2b11")


def uid(*parts):
    return Str(str(uuid.uuid5(NAMESPACE, "/".join(map(str, parts)))))


def snap(value):
    return round(value / GRID) * GRID


def rotate(x, y, angle):
    """Symbol-space point (y up) -> sheet offset (y down) for a symbol rotated CCW by angle degrees."""
    c, s = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[angle]
    return x * c - y * s, -(x * s + y * c)


def outward(pin, angle):
    ux, uy = {0: (-1, 0), 180: (1, 0), 90: (0, -1), 270: (0, 1)}[pin.angle]
    c, s = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[angle]
    return (ux * c - uy * s, -(ux * s + uy * c))


def _corners(symbol, unit):
    x0, y0, x1, y1 = symbol.bbox(unit)
    return [(x0, -y0), (x1, -y0), (x0, -y1), (x1, -y1)]


def text_width(text):
    return len(text) * 1.27 + 2.0


class Part:
    def __init__(self, ref, lib_id, value, nets, footprint="", lcsc="", mpn="", dnp=False, fields=None,
                 note="", in_bom=True):
        self.ref, self.lib_id, self.value = ref, lib_id, value
        self.nets = {str(k): v for k, v in nets.items()}
        self.footprint, self.lcsc, self.mpn, self.dnp = footprint, lcsc, mpn, dnp
        self.fields = dict(fields or {})
        self.note = note
        self.in_bom = in_bom and not ref.startswith("#")
        self.symbol = load(lib_id)
        two_pin_vertical = len(self.symbol.pins) == 2 and all(p.angle in (90, 270) for p in self.symbol.pins)
        self.rotation = 90 if two_pin_vertical and not self.symbol.is_power else 0

    def check(self):
        numbers = {p.number for p in self.symbol.pins}
        unknown = set(self.nets) - numbers
        missing = {p.number for p in self.symbol.pins if p.kind != "no_connect"} - set(self.nets)
        problems = []
        if unknown:
            problems.append(f"{self.ref}: nets for unknown pins {sorted(unknown)}")
        if missing:
            problems.append(f"{self.ref}: pins without a net decision {sorted(missing, key=lambda n: (len(n), n))}")
        return problems


class Sheet:
    def __init__(self, index, name, title):
        self.index, self.name, self.title = index, name, title
        self.parts = []
        self.counters = {}
        self.texts = []

    def next_ref(self, prefix):
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}{self.index}{self.counters[prefix]:02d}"

    def add(self, part):
        self.parts.append(part)
        return part

    def note(self, text):
        self.texts.append(text)


class Builder:
    def __init__(self, sheets, title, global_nets=None):
        self.sheets, self.title = sheets, title
        self.root_uuid = uid("root")
        self.power_count = 0
        self.global_nets = set(global_nets or ())
        usage = {}
        for sheet in sheets:
            for part in sheet.parts:
                for net in part.nets.values():
                    if net and net not in POWER_SYMBOLS:
                        usage.setdefault(net, set()).add(sheet.name)
        self.global_nets |= {net for net, where in usage.items() if len(where) > 1}

    def problems(self):
        out = []
        refs = {}
        for sheet in self.sheets:
            for part in sheet.parts:
                out += part.check()
                if part.ref in refs:
                    out.append(f"duplicate reference {part.ref}")
                refs[part.ref] = sheet.name
        return out

    def label_node(self, net, x, y, angle, key, force_global=False):
        justify = {0: [Sym("justify"), Sym("left")], 180: [Sym("justify"), Sym("right")],
                   90: [Sym("justify"), Sym("left")], 270: [Sym("justify"), Sym("right")]}[angle]
        if net in self.global_nets or force_global:
            return [Sym("global_label"), Str(net), [Sym("shape"), Sym("bidirectional")],
                    [Sym("at"), x, y, angle], [Sym("fields_autoplaced"), True],
                    [Sym("effects"), FONT, justify], [Sym("uuid"), uid(key, "label")],
                    [Sym("property"), Str("Intersheetrefs"), Str("${INTERSHEET_REFS}"), [Sym("at"), x, y, 0],
                     [Sym("effects"), FONT, justify, [Sym("hide"), True]]]]
        return [Sym("label"), Str(net), [Sym("at"), x, y, angle], [Sym("fields_autoplaced"), True],
                [Sym("effects"), FONT, justify + [Sym("bottom")]], [Sym("uuid"), uid(key, "label")]]

    def symbol_instance(self, symbol, ref, value, x, y, unit, sheet_uuid, fields, hidden_ref=False,
                        dnp=False, in_bom=True, key="", rotation=0, bbox=None):
        node = [Sym("symbol"), [Sym("lib_id"), Str(symbol.lib_id)], [Sym("at"), x, y, rotation], [Sym("unit"), unit],
                [Sym("exclude_from_sim"), False], [Sym("in_bom"), in_bom], [Sym("on_board"), in_bom or not hidden_ref],
                [Sym("dnp"), dnp], [Sym("uuid"), uid(key, ref, unit)]]
        x0, y0, x1, y1 = bbox or symbol.bbox(unit)
        if symbol.is_power:
            vx, vy = symbol.value_at()
            prop = [Sym("property"), Str("Value"), Str(value), [Sym("at"), round(x + vx, 2), round(y - vy, 2), 0],
                    [Sym("effects"), FONT]]
            ref_prop = [Sym("property"), Str("Reference"), Str(ref), [Sym("at"), x, y, 0],
                        [Sym("effects"), FONT, [Sym("hide"), True]]]
            node += [ref_prop, prop] + [[Sym("property"), Str(k), Str(v), [Sym("at"), x, y, 0],
                                         [Sym("effects"), FONT, [Sym("hide"), True]]] for k, v in fields.items()]
            for pin in symbol.unit_pins(unit):
                node.append([Sym("pin"), Str(pin.number), [Sym("uuid"), uid(key, ref, "pin", pin.number, unit)]])
            node.append([Sym("instances"), [Sym("project"), Str(PROJECT),
                         [Sym("path"), Str(f"/{self.root_uuid}/{sheet_uuid}"), [Sym("reference"), Str(ref)],
                          [Sym("unit"), unit]]]])
            return node
        centred = rotation != 0
        rx = x + (x0 + x1) / 2 if centred else x + x0
        properties = [("Reference", ref, rx, y + y0 - 2.54, hidden_ref),
                      ("Value", value, rx, y + y1 + 2.54, False)]
        properties += [(k, v, x, y, True) for k, v in fields.items()]
        for name, text, px, py, hide in properties:
            prop = [Sym("property"), Str(name), Str(text), [Sym("at"), round(px, 2), round(py, 2), rotation],
                    [Sym("effects"), FONT] + ([] if centred else [[Sym("justify"), Sym("left")]])
                    + ([[Sym("hide"), True]] if hide else [])]
            node.append(prop)
        for number in dict.fromkeys(pin.number for pin in symbol.pins):
            node.append([Sym("pin"), Str(number), [Sym("uuid"), uid(key, ref, "pin", number, unit)]])
        node.append([Sym("instances"), [Sym("project"), Str(PROJECT),
                     [Sym("path"), Str(f"/{self.root_uuid}/{sheet_uuid}"), [Sym("reference"), Str(ref)],
                      [Sym("unit"), unit]]]])
        return node

    def power_symbol(self, net, x, y, sheet_uuid, used):
        lib_id = POWER_SYMBOLS[net]
        symbol = load(lib_id)
        used[lib_id] = symbol
        self.power_count += 1
        ref = f"#PWR{self.power_count:04d}"
        return self.symbol_instance(symbol, ref, net, x, y, 1, sheet_uuid, {"Footprint": "", "Datasheet": ""},
                                    hidden_ref=True, in_bom=False, key=f"pwr{self.power_count}")

    def sheet_file(self, sheet):
        sheet_uuid = uid("sheet", sheet.name)
        used, items = {}, []
        cells = []
        for part in sheet.parts:
            used[part.lib_id] = part.symbol
            for unit in part.symbol.units:
                cells.append((part, unit))
        x_cursor, y_cursor, row_height, max_x = 20.32, 30.48, 0.0, 0.0
        width_limit = 380.0
        for part, unit in cells:
            pins = part.symbol.unit_pins(unit)
            rot = part.rotation
            corners = [rotate(x, y, rot) for x, y in _corners(part.symbol, unit)]
            x0, y0 = min(c[0] for c in corners), min(c[1] for c in corners)
            x1, y1 = max(c[0] for c in corners), max(c[1] for c in corners)
            margins = {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
            for pin in pins:
                net = part.nets.get(pin.number)
                side = {(-1, 0): "l", (1, 0): "r", (0, -1): "t", (0, 1): "b"}[outward(pin, rot)]
                vertical_power = net in POWER_SYMBOLS and side in "tb" and len(pins) > 3
                extent = STUB + (text_width(net) if net else 0) + (4 if net in POWER_SYMBOLS and not vertical_power else 0)
                margins[side] = max(margins[side], extent)
            text_span = max(text_width(part.value), text_width(part.ref)) + 2.54
            margins["t"] = max(margins["t"], 6.0)
            margins["b"] = max(margins["b"], 6.0)
            width = max(margins["l"] + (x1 - x0) + margins["r"], text_span) + 7.62
            height = margins["t"] + (y1 - y0) + margins["b"] + 7.62
            if x_cursor + width > width_limit and x_cursor > 21:
                x_cursor, y_cursor, row_height = 20.32, y_cursor + row_height, 0.0
            ox = snap(x_cursor + margins["l"] - x0)
            oy = snap(y_cursor + margins["t"] - y0)
            items.append(self.symbol_instance(
                part.symbol, part.ref, part.value, ox, oy, unit, sheet_uuid,
                {"Footprint": part.footprint, "Datasheet": "", "LCSC": part.lcsc, "MPN": part.mpn, **part.fields},
                dnp=part.dnp, in_bom=part.in_bom, key=sheet.name, rotation=rot, bbox=(x0, y0, x1, y1)))
            for pin in pins:
                net = part.nets.get(pin.number, None)
                rx, ry = rotate(pin.x, pin.y, rot)
                px, py = round(ox + rx, 4), round(oy + ry, 4)
                key = f"{sheet.name}/{part.ref}/{unit}/{pin.number}"
                if net is None:
                    items.append([Sym("no_connect"), [Sym("at"), px, py], [Sym("uuid"), uid(key, "nc")]])
                    continue
                dx, dy = outward(pin, rot)
                vertical_power = net in POWER_SYMBOLS and dy != 0 and len(pins) > 3
                length = STUB * (2 if net in POWER_SYMBOLS and dx != 0 else 1)
                ex, ey = round(px + dx * length, 4), round(py + dy * length, 4)
                items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), px, py], [Sym("xy"), ex, ey]],
                              [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                              [Sym("uuid"), uid(key, "wire")]])
                if net in POWER_SYMBOLS and not vertical_power:
                    items.append(self.power_symbol(net, ex, ey, sheet_uuid, used))
                else:
                    angle = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[(dx, dy)]
                    items.append(self.label_node(net, ex, ey, angle, key, force_global=vertical_power))
            x_cursor += width
            row_height = max(row_height, height)
            max_x = max(max_x, x_cursor)
        for i, text in enumerate(sheet.texts):
            items.append([Sym("text"), Str(text), [Sym("exclude_from_sim"), False],
                          [Sym("at"), 20.32, 15.24 + 5.08 * i, 0],
                          [Sym("effects"), FONT, [Sym("justify"), Sym("left")]], [Sym("uuid"), uid(sheet.name, "text", i)]])
        needed_w, needed_h = max_x + 20, y_cursor + row_height + 20
        paper = next((p for p in PAPERS if p[1] >= needed_w and p[2] >= needed_h), PAPERS[-1])[0]
        tree = [Sym("kicad_sch"), [Sym("version"), VERSION], [Sym("generator"), Str("eeschema")],
                [Sym("generator_version"), Str(GENERATOR_VERSION)], [Sym("uuid"), uid("file", sheet.name)],
                [Sym("paper"), Str(paper)],
                [Sym("title_block"), [Sym("title"), Str(f"{self.title}: {sheet.title}")],
                 [Sym("date"), Str("2026-11-04")], [Sym("rev"), Str("A")],
                 [Sym("company"), Str("embedded-pro")],
                 [Sym("comment"), 1, Str("Generated by scripts/schgen/build.py; do not hand-edit before the Phase 1 gate")]],
                [Sym("lib_symbols")] + [s.embedded() for s in used.values()]]
        tree += items
        tree.append([Sym("embedded_fonts"), False])
        return sheet_uuid, tree

    def root_file(self, sheet_entries):
        items = []
        for i, (sheet, sheet_uuid) in enumerate(sheet_entries):
            x, y = 25.4 + (i % 4) * 95.25, 38.1 + (i // 4) * 50.8
            items.append([Sym("sheet"), [Sym("at"), x, y], [Sym("size"), 76.2, 30.48],
                          [Sym("exclude_from_sim"), False], [Sym("in_bom"), True], [Sym("on_board"), True],
                          [Sym("dnp"), False], [Sym("fields_autoplaced"), True],
                          [Sym("stroke"), [Sym("width"), 0.1524], [Sym("type"), Sym("solid")]],
                          [Sym("fill"), [Sym("color"), 0, 0, 0, 0.0]],
                          [Sym("uuid"), sheet_uuid],
                          [Sym("property"), Str("Sheetname"), Str(f"{sheet.index} {sheet.title}"), [Sym("at"), x, y - 0.7, 0],
                           [Sym("effects"), FONT, [Sym("justify"), Sym("left"), Sym("bottom")]]],
                          [Sym("property"), Str("Sheetfile"), Str(f"{sheet.name}.kicad_sch"),
                           [Sym("at"), x, y + 31.0, 0], [Sym("effects"), FONT, [Sym("justify"), Sym("left"), Sym("top")]]],
                          [Sym("instances"), [Sym("project"), Str(PROJECT),
                                              [Sym("path"), Str(f"/{self.root_uuid}"), [Sym("page"), Str(str(i + 2))]]]]])
        return [Sym("kicad_sch"), [Sym("version"), VERSION], [Sym("generator"), Str("eeschema")],
                [Sym("generator_version"), Str(GENERATOR_VERSION)], [Sym("uuid"), self.root_uuid],
                [Sym("paper"), Str("A3")],
                [Sym("title_block"), [Sym("title"), Str(self.title)], [Sym("date"), Str("2026-11-04")],
                 [Sym("rev"), Str("A")], [Sym("company"), Str("embedded-pro")]],
                [Sym("lib_symbols")]] + items + [
                [Sym("sheet_instances"), [Sym("path"), Str("/"), [Sym("page"), Str("1")]]],
                [Sym("embedded_fonts"), False]]

    def write(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        entries = []
        for sheet in self.sheets:
            sheet_uuid, tree = self.sheet_file(sheet)
            (directory / f"{sheet.name}.kicad_sch").write_text(dump(tree) + "\n", encoding="utf-8")
            entries.append((sheet, sheet_uuid))
        (directory / f"{PROJECT}.kicad_sch").write_text(dump(self.root_file(entries)) + "\n", encoding="utf-8")
