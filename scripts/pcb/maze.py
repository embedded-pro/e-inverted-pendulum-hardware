#!/usr/bin/env python3
"""A grid router for the routing passes after the simple one (D-055, D-057, D-058).

Not a script: vendor_gaps.py and route_maze.py use it. It routes one connection at a time, between two terminals of one
net (route_simple.Terminal: a pad, a via or a free track end), on L1 (F.Cu) and L4 (B.Cu) only; L2 is the solid GND
plane and L3 holds the planes (D-056).
  - The window covers both terminals plus a margin. Its grid (PITCH) is aligned to a point terminal (a track end or a
    via), so the track ends exactly on it.
  - The board's copper is drawn into the window per layer, sorted three ways. Other nets' copper keeps the class
    clearance, 0.2 mm for the PWR_BUS / MOTOR / RF classes, other nets' pours and the board edge. A GND fill outside
    TI's bridges (TI's drive GND, ST's NFC ground) gives way: it is refilled around the new track (soft_fill). The net's own copper
    that is not a terminal is never touched (that would be a tee). Rule areas that forbid tracks are never entered. NPTH
    holes keep 0.5 mm. A via also stays off every part's body and the test pads' names, out of the via keep-outs and
    ST's RF ground strip, and 0.2 mm from other holes.
  - An A* search: 8 directions, turns of 45 degrees only (pcb-design-rules: no right-angle corners), a cost per mm that
    prefers horizontal on F.Cu and vertical on B.Cu (power-pcb-layout §5: layer-direction discipline), a cost per bend
    and per via, at most MAX_VIAS vias, and penalty areas per net (encoders away from the motor phases, the battery
    sense away from the switch nodes; docs/power-map.md).
  - The cells become segments. Jogs and zigzags are straightened where the straight version passes. Every segment and
    via is checked exactly (route_simple.World, the board's clearances) before anything is added; a failure is retried
    with more slack, then with a wider window.
"""

import heapq
import math
import pathlib
import sys
from array import array

import numpy as np
import pcbnew
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gnd_vias as G  # noqa: E402
import place_block as PB  # noqa: E402
import respace as R  # noqa: E402
import route_simple as RS  # noqa: E402
import tidy_copper as T  # noqa: E402

RS.B.pcbnew = pcbnew
mm = pcbnew.FromMM
V = pcbnew.VECTOR2I
PITCH = 0.05
# A window larger than COARSE_AREA (mm2) is searched on COARSE_PITCH first, then on PITCH if that fails.
COARSE_PITCH = 0.1
COARSE_AREA = 600.0
MARGINS = (4.0, 12.0)
SLACKS = (0.4, 0.9)
ERROR = mm(0.002)
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
WIDE_CLASSES = {"PWR_BUS", "MOTOR", "RF"}
WIDE_CLEARANCE = 0.2
EDGE = 0.2
NPTH_GAP = 0.5
PAD_HOLE_GAP = 0.28
HOLE_TO_HOLE = 0.2
HOLE_TO_COPPER = 0.2
BODY_GAP = 0.1
LABEL_GAP = 0.05
VIA_SIZES = ((0.6, 0.3), (0.45, 0.2))
MAX_VIAS = 2
# A search gives up after this many cells (about 20 s): a connection that needs more is left for the owner.
MAX_EXPANSIONS = 600_000
# A segment shorter than this between two parallel runs is a jog (pcb-design-rules gate, pcb_rules.JOG_MM).
JOG_MM = 0.25
DIRS = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1))
SQRT2 = math.sqrt(2)
COS45 = math.cos(math.radians(45)) - 1e-6
INF = float("inf")
# Costs in mm of straight track: per mm on each layer by direction (horizontal, diagonal, vertical), per 45-degree bend.
LAYER_COST = {pcbnew.F_Cu: (1.0, 1.2, 1.6), pcbnew.B_Cu: (1.6, 1.2, 1.0)}
BEND_COST = 0.3
# Penalty areas (docs/power-map.md): a net matching the key costs PENALTY times more within PENALTY_MM of these nets.
HOT = {"ENC_": ("MOT_", "SENSE_A", "SENSE_B"), "VBAT_SENSE": ("BUCK_SW", "SMPS_LX", "MOT_")}
PENALTY = 6
PENALTY_MM = 1.0


def outlines(poly):
    """A polygon set as simple outlines (holes joined in), each an (n, 2) array of nm."""
    poly = pcbnew.SHAPE_POLY_SET(poly)
    poly.Fracture()
    found = []
    for i in range(poly.OutlineCount()):
        chain = poly.Outline(i)
        found.append(np.array([(chain.CPoint(k).x, chain.CPoint(k).y) for k in range(chain.PointCount())],
                              dtype=np.float64))
    return found


# TI's bridges, their phase / sense pours and shunts (mechanical x, z): a GND fill keeps its copper here, where it carries
# the hot loops' current; elsewhere it gives way to tracks and vias (soft_fill).
BRIDGES = (-10.0, 32.0, 12.5, 33.5)


def bridges():
    x0, x1, z0, z1 = BRIDGES
    poly = pcbnew.SHAPE_POLY_SET()
    poly.NewOutline()
    for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
        poly.Append(RS.B.to_board(x, z))
    return poly


def soft_fill(zone):
    """A GND fill a track or via may cut into (it is refilled around them), outside BRIDGES: TI's drive GND and ST's
    NFC ground, which tie ground pads to the L2 plane. ST's RF-strip ground (the RF line's coplanar ground) and every
    pour that carries current (VBAT, the phases, the sense nodes, the power entry) stay solid."""
    return RS.short(zone.GetNetname()) == "GND" and not zone.GetZoneName().startswith("MB1355")


def hot_for(name):
    return next((nets for key, nets in HOT.items() if name.startswith(key)), ())


class Shapes:
    """Each copper item's outline on a layer, cached by UUID (items never move while routing)."""

    def __init__(self):
        self.cache = {}

    def of(self, item, layer):
        key = (RS.uid(item), layer)
        if key not in self.cache:
            poly = pcbnew.SHAPE_POLY_SET()
            item.TransformShapeToPolygon(poly, layer, 0, ERROR, pcbnew.ERROR_OUTSIDE)
            self.cache[key] = outlines(poly)
        return self.cache[key]

    def hole(self, item):
        key = (RS.uid(item), "hole")
        if key not in self.cache:
            poly = pcbnew.SHAPE_POLY_SET()
            if item.GetClass() == "PCB_VIA":
                poly.NewOutline()
                r, c = item.GetDrillValue() / 2, item.GetPosition()
                for k in range(16):
                    a = 2 * math.pi * k / 16
                    poly.Append(int(c.x + r / math.cos(math.pi / 16) * math.cos(a)),
                                int(c.y + r / math.cos(math.pi / 16) * math.sin(a)))
            else:
                item.TransformHoleToPolygon(poly, 0, ERROR, pcbnew.ERROR_OUTSIDE)
            self.cache[key] = outlines(poly)
        return self.cache[key]


class Window:
    """A grid of cells over part of the board; cell (i, j) is the point (x0 + i * pitch, y0 + j * pitch)."""

    def __init__(self, box, origin, pitch=PITCH):
        p = mm(pitch)
        self.pitch, self.p = pitch, p
        xmin, ymin, xmax, ymax = box
        self.x0 = origin.x - math.ceil((origin.x - xmin) / p) * p
        self.y0 = origin.y - math.ceil((origin.y - ymin) / p) * p
        self.nx = int((xmax - self.x0) // p) + 1
        self.ny = int((ymax - self.y0) // p) + 1
        self.lo = np.array((self.x0 - p, self.y0 - p))
        self.hi = np.array((self.x0 + (self.nx + 1) * p, self.y0 + (self.ny + 1) * p))

    def cell(self, pt):
        return round((pt.x - self.x0) / self.p), round((pt.y - self.y0) / self.p)

    def point(self, i, j):
        return V(int(self.x0 + i * self.p), int(self.y0 + j * self.p))

    def inside(self, i, j):
        return 0 <= i < self.nx and 0 <= j < self.ny

    def canvas(self):
        image = Image.new("1", (self.nx, self.ny), 0)
        return image, ImageDraw.Draw(image)

    def overlaps(self, pts):
        return not (np.any(pts.max(axis=0) < self.lo) or np.any(pts.min(axis=0) > self.hi))

    def draw(self, draw, pts):
        if len(pts) < 3 or not self.overlaps(pts):
            return
        cells = (pts - (self.x0, self.y0)) / self.p + 0.5
        draw.polygon([tuple(c) for c in cells], fill=1)

    def distance(self, image):
        """mm from each cell centre to the nearest drawn cell centre (large where nothing is drawn)."""
        mask = np.array(image, dtype=bool)
        if not mask.any():
            return np.full(mask.shape, 1e9)
        return ndimage.distance_transform_edt(~mask) * self.pitch


class Router:
    def __init__(self, board, world, islands):
        self.board, self.world, self.islands = board, world, islands
        self.shapes = Shapes()
        outline = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(outline, False)
        box = outline.BBox()
        outside = pcbnew.SHAPE_POLY_SET()
        outside.NewOutline()
        grow = mm(5)
        for x, y in ((box.GetLeft() - grow, box.GetTop() - grow), (box.GetRight() + grow, box.GetTop() - grow),
                     (box.GetRight() + grow, box.GetBottom() + grow), (box.GetLeft() - grow, box.GetBottom() + grow)):
            outside.Append(x, y)
        outside.BooleanSubtract(outline)
        self.outside = outlines(outside)
        self.keep_tracks = {layer: [] for layer in LAYERS}
        self.keep_vias = []
        owned = [zone for fp in board.GetFootprints() for zone in fp.Zones()]
        self.fills = {layer: [] for layer in LAYERS}
        self.hard = {layer: [] for layer in LAYERS}
        for zone in list(board.Zones()) + owned:
            if zone.GetIsRuleArea():
                for layer in LAYERS:
                    if zone.IsOnLayer(layer) and zone.GetDoNotAllowTracks():
                        self.keep_tracks[layer] += outlines(zone.Outline())
                if zone.GetDoNotAllowVias():
                    self.keep_vias += outlines(zone.Outline())
                continue
            gap = mm(max(WIDE_CLEARANCE, zone.GetLocalClearance() / 1e6 if zone.GetLocalClearance() else 0))
            for layer in LAYERS:
                if zone.IsOnLayer(layer):
                    fill = pcbnew.SHAPE_POLY_SET(zone.GetFilledPolysList(layer))
                    if fill.OutlineCount() and soft_fill(zone):
                        fill.BooleanIntersection(bridges())
                    if fill.OutlineCount():
                        self.fills[layer].append((zone.GetNetCode(), RS.short(zone.GetNetname()), outlines(fill)))
                        self.hard[layer].append((zone.GetNetCode(), fill, gap))
        x0, x1, z0, z1 = G.strip_rectangle()
        self.strip = pcbnew.SHAPE_POLY_SET()
        self.strip.NewOutline()
        for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1)):
            self.strip.Append(RS.B.to_board(x, z))
        self.keep_vias += outlines(self.strip)
        self.bodies = []
        for fp in board.GetFootprints():
            body = pcbnew.SHAPE_POLY_SET(PB.body(fp))
            body.Inflate(mm(BODY_GAP), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERROR)
            self.bodies += outlines(body)
        self.labels = [outlines(rect)[0] for rect in world.labels]
        self.npth = [pad for pad in world.pads if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]
        self.soft_pours = False

    # Obstacles in a window.

    def distances(self, win, net, terminals, soft_pours=False):
        """Distance fields (mm) in the window, per layer: to other nets' copper (and to the 0.2 mm classes, the pours and
        the edge), to the net's own copper that is not a terminal, to rule areas forbidding tracks, to the penalty
        nets; and for vias: to every hole, to NPTH holes, to the via keep-outs, bodies and labels, to the terminals."""
        names = {RS.uid(t.item) for t in terminals} | {RS.uid(t.track) for t in terminals if t.track is not None}
        hot = hot_for(RS.short(terminals[0].item.GetNetname()))
        result = {}
        for layer in LAYERS:
            canvases = {key: win.canvas() for key in ("other", "wide", "zone", "own", "keep", "hot", "term")}
            for item in self.world.pads + self.world.tracks:
                if not item.IsOnLayer(layer):
                    continue
                shapes = self.shapes.of(item, layer)
                if not any(win.overlaps(pts) for pts in shapes):
                    continue
                if RS.uid(item) in names:
                    key = "term"
                elif item.GetNetCode() == net and net > 0:
                    key = "own"
                elif item.GetNetClassName() in WIDE_CLASSES:
                    key = "wide"
                else:
                    key = "other"
                for pts in shapes:
                    win.draw(canvases[key][1], pts)
                if hot and any(RS.short(item.GetNetname()).startswith(h) for h in hot):
                    for pts in shapes:
                        win.draw(canvases["hot"][1], pts)
            for zone_net, zone_name, fills in self.fills[layer]:
                if zone_net != net and not soft_pours:
                    for pts in fills:
                        win.draw(canvases["zone"][1], pts)
                if hot and any(zone_name.startswith(h) for h in hot):
                    for pts in fills:
                        win.draw(canvases["hot"][1], pts)
            for pts in self.outside:
                win.draw(canvases["zone"][1], pts)
            for pts in self.keep_tracks[layer]:
                win.draw(canvases["keep"][1], pts)
            result[layer] = {key: win.distance(image) for key, (image, _) in canvases.items()}
        canvases = {key: win.canvas() for key in ("npth", "holes", "keep_via")}
        for pad in self.npth:
            for pts in self.shapes.hole(pad):
                win.draw(canvases["npth"][1], pts)
        for item in self.world.pads + self.world.tracks:
            drilled = item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole())
            if drilled:
                for pts in self.shapes.hole(item):
                    win.draw(canvases["holes"][1], pts)
        for pts in self.keep_vias + self.bodies + self.labels:
            win.draw(canvases["keep_via"][1], pts)
        result["via"] = {key: win.distance(image) for key, (image, _) in canvases.items()}
        result["hot"] = bool(hot)
        return result

    def masks(self, dist, clearance, wide, width, slack, via_size, pitch):
        """The cells a track centre may use on each layer, the cells a via centre may use, the cost multipliers.
        clearance: to other nets' copper; wide: to the 0.2 mm classes' copper; pours and the edge keep 0.2 mm."""
        half = width / 2
        tol = slack * pitch
        free, cost = [], []
        npth = dist["via"]["npth"]
        for layer in LAYERS:
            d = dist[layer]
            free.append((d["other"] >= half + clearance + tol) & (d["wide"] >= half + wide + tol)
                        & (d["zone"] >= half + WIDE_CLEARANCE + tol) & (d["own"] >= half + tol) & (d["keep"] >= half + tol) & (npth >= half + NPTH_GAP + tol))
            mult = np.ones(d["other"].shape, dtype=np.uint8)
            if dist["hot"]:
                mult[d["hot"] < PENALTY_MM] = PENALTY
            cost.append(mult)
        r, drill = via_size[0] / 2, via_size[1] / 2
        v = dist["via"]
        via_ok = (v["holes"] >= drill + HOLE_TO_HOLE + tol) & (v["keep_via"] >= r + tol) & (npth >= r + NPTH_GAP + tol)
        for layer in LAYERS:
            d = dist[layer]
            via_ok &= ((d["other"] >= r + clearance + tol) & (d["wide"] >= r + wide + tol)
                       & (d["zone"] >= r + WIDE_CLEARANCE + tol) & (d["own"] >= r + tol)
                       & (d["term"] >= r + BODY_GAP + tol))
        return free, via_ok, cost

    # Search.

    def search(self, win, free, via_ok, cost, sources, targets, goal, allow_vias, via_cost, layers):
        """A* over (layer, cell): sources [(layer, i, j, allowed directions or None)], targets {(layer, i, j):
        allowed arrival directions or None}. Returns [(layer, i, j), ...] from a source to a target, or None."""
        nx, ny = win.nx, win.ny
        n = nx * ny
        flat_free = [bytearray(np.ascontiguousarray(f, dtype=np.uint8).tobytes()) for f in free]
        flat_cost = [bytearray(np.ascontiguousarray(c, dtype=np.uint8).tobytes()) for c in cost]
        flat_via = bytearray(np.ascontiguousarray(via_ok, dtype=np.uint8).tobytes())
        g = array("d", [INF]) * (2 * n)
        came = array("q", [-1]) * (2 * n)
        heading = bytearray([8]) * (2 * n)
        vias = bytearray(2 * n)
        p = win.pitch
        steps = []
        for k, (dx, dy) in enumerate(DIRS):
            kind = 0 if dy == 0 else (2 if dx == 0 else 1)
            steps.append((dx, dy, dx + dy * nx, kind, (SQRT2 if kind == 1 else 1.0) * p))
        layer_cost = [LAYER_COST[layer] for layer in LAYERS]
        gx, gy = goal
        hmin = min(min(c) for c in layer_cost)

        def h(i, j):
            dx, dy = abs(i - gx), abs(j - gy)
            return 1.2 * hmin * p * (max(dx, dy) + (SQRT2 - 1) * min(dx, dy))

        heap = []
        start_dirs = {}
        for l, i, j, allowed in sources:
            if l not in layers or not win.inside(i, j):
                continue
            idx = l * n + j * nx + i
            g[idx] = 0.0
            start_dirs[idx] = allowed
            heapq.heappush(heap, (h(i, j), 0.0, idx))
        target_index = {l * n + j * nx + i: allowed for (l, i, j), allowed in targets.items()}
        expanded = 0
        while heap:
            f, gc, idx = heapq.heappop(heap)
            if gc > g[idx]:
                continue
            expanded += 1
            if expanded > MAX_EXPANSIONS:
                return None
            if idx in target_index:
                allowed = target_index[idx]
                if allowed is None or heading[idx] in allowed:
                    path = []
                    while idx >= 0:
                        l, rest = divmod(idx, n)
                        j, i = divmod(rest, nx)
                        path.append((l, i, j))
                        idx = came[idx]
                    return path[::-1]
            l, rest = divmod(idx, n)
            j, i = divmod(rest, nx)
            d0 = heading[idx]
            allowed = start_dirs.get(idx)
            lc = layer_cost[l]
            ff, fc = flat_free[l], flat_cost[l]
            base = l * n
            for k, (dx, dy, dk, kind, length) in enumerate(steps):
                if d0 != 8:
                    turn = (k - d0) % 8
                    if turn not in (0, 1, 7):
                        continue
                    bend = 0.0 if turn == 0 else BEND_COST
                else:
                    if allowed is not None and k not in allowed:
                        continue
                    bend = 0.0
                ni, nj = i + dx, j + dy
                if ni < 0 or nj < 0 or ni >= nx or nj >= ny:
                    continue
                cell = rest + dk
                if not ff[cell]:
                    continue
                ng = gc + length * lc[kind] * fc[cell] + bend
                nidx = base + cell
                if ng < g[nidx]:
                    g[nidx] = ng
                    came[nidx] = idx
                    heading[nidx] = k
                    vias[nidx] = vias[idx]
                    heapq.heappush(heap, (ng + h(ni, nj), ng, nidx))
            if allow_vias and flat_via[rest] and vias[idx] < MAX_VIAS and d0 != 8:
                other = 1 - l
                if other in layers and flat_free[other][rest]:
                    nidx = other * n + rest
                    ng = gc + via_cost
                    if ng < g[nidx]:
                        g[nidx] = ng
                        came[nidx] = idx
                        heading[nidx] = 8
                        vias[nidx] = vias[idx] + 1
                        heapq.heappush(heap, (ng + h(i, j), ng, nidx))
        return None

    # Terminals on the grid.

    def ends(self, win, term, width, free, as_source):
        """Grid cells where the route may start or end at this terminal, with the directions allowed there."""
        found = {}
        layers = [k for k, layer in enumerate(LAYERS) if layer in term.layers()]
        if term.kind == "pad":
            for k in layers:
                image, draw = win.canvas()
                for pts in self.shapes.of(term.item, LAYERS[k]):
                    win.draw(draw, pts)
                inside = np.argwhere(np.array(image, dtype=bool) & free[k])
                for j, i in inside:
                    found[(k, int(i), int(j))] = None
                if not inside.size:
                    i, j = win.cell(term.at)
                    if win.inside(i, j):
                        free[k][j, i] = True
                        found[(k, i, j)] = None
            return found
        i, j = win.cell(term.at)
        exact = win.point(i, j) == term.at
        for k in layers:
            layer = LAYERS[k]
            dirs = [d for d, (dx, dy) in enumerate(DIRS)
                    if RS.angle_ok(term, term.at + V(int(dx * 1e6), int(dy * 1e6)), layer, self.world)]
            arrive = [(d + 4) % 8 for d in dirs]
            if exact:
                if win.inside(i, j):
                    free[k][j, i] = True
                    found[(k, i, j)] = set(dirs) if as_source else set(arrive)
            else:
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        if win.inside(i + di, j + dj) and free[k][j + dj, i + di]:
                            found[(k, i + di, j + dj)] = None
        return found

    # Geometry.

    def geometry(self, win, path, a, b):
        """[(layer, [points])] runs and the via points, from the cells."""
        runs, vias = [], []
        current = None
        for l, i, j in path:
            pt = win.point(i, j)
            if current is None or current[0] != LAYERS[l]:
                if current is not None:
                    vias.append(pt)
                current = (LAYERS[l], [pt])
                runs.append(current)
            else:
                current[1].append(pt)
        cleaned = []
        for layer, pts in runs:
            corners = [pts[0]]
            for k in range(1, len(pts) - 1):
                d1, d2 = pts[k] - pts[k - 1], pts[k + 1] - pts[k]
                if (d1.x * d2.y - d1.y * d2.x) != 0 or d1.x * d2.x + d1.y * d2.y < 0:
                    corners.append(pts[k])
            if len(pts) > 1:
                corners.append(pts[-1])
            cleaned.append([layer, corners])
        for term, first in ((a, True), (b, False)):
            if term.kind == "pad":
                continue
            layer, pts = cleaned[0] if first else cleaned[-1]
            end = pts[0] if first else pts[-1]
            if end == term.at:
                continue
            hop = [term.at] + T.two_legs(term.at, end)[:1] + [end] if first else [end] + T.two_legs(end, term.at)[:1] + [term.at]
            hop = [q for k, q in enumerate(hop) if k == 0 or q != hop[k - 1]]
            if first:
                pts[:1] = hop
            else:
                pts[-1:] = hop
        return cleaned, vias

    def straighten(self, runs, net, width, probe, a, b):
        """Shortcuts: any stretch of a run whose straight or one-bend version passes the exact checks, longest first;
        removes zigzags and jogs. A stretch from a terminal keeps that terminal's angle rule."""
        for index, run in enumerate(runs):
            layer, pts = run
            changed = True
            while changed and len(pts) > 2:
                changed = False
                for i in range(len(pts) - 2):
                    for j in range(len(pts) - 1, i + 1, -1):
                        for path in RS.paths(pts[i], pts[j]):
                            if len(path) >= j - i + 1 or not self.joins_ok(pts, i, j, path):
                                continue
                            if index == 0 and i == 0 and not RS.angle_ok(a, path[1], layer, self.world):
                                continue
                            if index == len(runs) - 1 and j == len(pts) - 1 and \
                                    not RS.angle_ok(b, path[-2], layer, self.world):
                                continue
                            legs = [(p, q) for p, q in zip(path, path[1:]) if p != q]
                            if self.legs_ok(legs, layer, width, probe, (a, b), net):
                                pts[i:j + 1] = [q for k, q in enumerate(path) if k == 0 or q != path[k - 1]]
                                changed = True
                                break
                        if changed:
                            break
                    if changed:
                        break
        return runs

    @staticmethod
    def joins_ok(pts, i, j, path):
        """The new stretch meets the rest of the run at 135 degrees or more (no sharp corners)."""
        def turn_ok(u, v):
            nu, nv = math.hypot(u.x, u.y), math.hypot(v.x, v.y)
            return nu == 0 or nv == 0 or (u.x * v.x + u.y * v.y) / (nu * nv) >= COS45
        if i > 0 and not turn_ok(pts[i] - pts[i - 1], path[1] - path[0]):
            return False
        if j < len(pts) - 1 and not turn_ok(path[-1] - path[-2], pts[j + 1] - pts[j]):
            return False
        return True

    def legs_ok(self, legs, layer, width, probe, own, net):
        if RS.tee_problem(self.world, legs, layer, net):
            return False
        return all(self.world.track_problem(p, q, layer, width, probe, own, pours=False) is None
                   and self.pour_problem(p, q, layer, width, probe) is None for p, q in legs)

    def pour_problem(self, a, b, layer, width, probe):
        """Another net's pour that the track would cut into (the hard ones: see soft_fill)."""
        if self.soft_pours:
            return None
        shape = pcbnew.SHAPE_SEGMENT(a, b, width)
        for net, poly, gap in self.hard[layer]:
            if net != probe.GetNetCode() and poly.Collide(shape, gap):
                return "pour"
        return None

    def via_problem(self, at, diameter, drill, probe, own_net_ok=False, ignore_bodies=(), soft_pours=False):
        """Why a signal via here would break a rule, or None (exact, like route_simple.World.via_problem, but the inner
        planes are carved by it rather than in its way)."""
        ring = pcbnew.SHAPE_CIRCLE(at, diameter // 2)
        hole = pcbnew.SHAPE_CIRCLE(at, drill // 2)
        world = self.world
        if world.outside.Collide(ring, mm(EDGE)):
            return "edge"
        if any(area.Collide(ring, 0) for area in world.keep_vias) or self.strip.Collide(ring, 0):
            return "rule area"
        if any(body.Collide(ring, mm(BODY_GAP)) for ref, body in world.bodies.items() if ref not in ignore_bodies):
            return "body"
        if any(label.Collide(ring, mm(LABEL_GAP)) for label in world.labels):
            return "label"
        for item in world.near(world.pads + world.tracks, at, mm(3)):
            drilled = item.GetClass() == "PCB_VIA" or (item.GetClass() == "PAD" and item.HasHole())
            if drilled and item.GetEffectiveHoleShape().Collide(hole, mm(HOLE_TO_HOLE)):
                return "hole"
            if item.GetClass() == "PAD" and item.HasHole() and item.GetNetCode() != probe.GetNetCode():
                gap = NPTH_GAP if item.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH else PAD_HOLE_GAP
                if item.GetEffectiveHoleShape().Collide(ring, mm(gap)):
                    return "hole"
            for layer in LAYERS:
                if not item.IsOnLayer(layer):
                    continue
                shape = item.GetEffectiveShape(layer)
                if item.GetNetCode() == probe.GetNetCode():
                    if shape.Collide(ring, 0) and not own_net_ok:
                        return "own net"
                elif shape.Collide(ring, mm(R.rule_clearance(item, probe))) or \
                        shape.Collide(hole, mm(HOLE_TO_COPPER)):
                    return "copper"
        for layer in (LAYERS if not soft_pours else ()):
            for net, poly, gap in self.hard[layer]:
                if net != probe.GetNetCode() and poly.Collide(ring, gap):
                    return "pour"
        return None

    # One connection.

    @staticmethod
    def clearances(probe):
        """The routed net's clearance to other copper by the board's rules (respace.rule_clearance): the class
        clearance and 0.2 mm to the PWR_BUS / MOTOR / RF classes, unless a custom rule covers the net (ST's 0.1 mm on
        its SMPS, HSE and RF nets, TI's 0.178 mm on the DRV8711's), which then applies to all copper but pours."""
        own = R.rule_clearance(probe, probe)
        default = max(R.CLASS_CLEARANCE.get(probe.GetNetClassName(), 0.15), 0.15)
        if own < default or "/DRV_" in probe.GetNetname():
            return own, own
        return default, max(default, WIDE_CLEARANCE)

    def route(self, a, b, width, allow_vias=True, via_cost=3.0, layers=(0, 1), margins=MARGINS, soft_pours=False):
        """Route a to b (route_simple.Terminal) at this width (nm). Returns (tracks, vias) added, or (None, why).
        soft_pours: other nets' pours are not obstacles (a vendor's own connection, which its pour flows around)."""
        net = a.item.GetNetCode()
        probe = RS.probe_for(self.board, a.item.GetNet())
        clearance, wide = self.clearances(probe)
        self.soft_pours = soft_pours
        origin = next((t.at for t in (a, b) if t.kind == "end"), None) or \
            next((t.at for t in (a, b) if t.kind == "via"), a.at)
        why = "no path"
        for margin in margins:
            pad = mm(margin)
            box = (min(a.at.x, b.at.x) - pad, min(a.at.y, b.at.y) - pad,
                   max(a.at.x, b.at.x) + pad, max(a.at.y, b.at.y) + pad)
            area = (box[2] - box[0]) * (box[3] - box[1]) / 1e12
            for pitch in (COARSE_PITCH, PITCH) if area > COARSE_AREA else (PITCH,):
                win = Window(box, origin, pitch)
                dist = self.distances(win, net, (a, b), soft_pours)
                for size in (VIA_SIZES if allow_vias else VIA_SIZES[:1]):
                    for slack in SLACKS:
                        free, via_ok, cost = self.masks(dist, clearance, wide, width / 1e6, slack, size, win.pitch)
                        sources = [(k, i, j, allowed)
                                   for (k, i, j), allowed in self.ends(win, a, width, free, True).items()]
                        targets = self.ends(win, b, width, free, False)
                        if not sources or not targets:
                            why = "terminal blocked"
                            break
                        for k, i, j, _ in sources:
                            via_ok[j, i] = False
                        for k, i, j in targets:
                            via_ok[j, i] = False
                        goal = win.cell(b.at)
                        path = self.search(win, free, via_ok, cost, sources, targets, goal, allow_vias, via_cost,
                                           layers)
                        if path is None:
                            why = "no path"
                            break
                        runs, via_points = self.geometry(win, path, a, b)
                        runs = self.straighten(runs, net, width, probe, a, b)
                        problem = self.check(runs, via_points, width, probe, a, b, size)
                        if problem is None:
                            return self.lay(runs, via_points, width, a, b, size), None
                        why = problem
        return None, why

    def check(self, runs, via_points, width, probe, a, b, size):
        net = a.item.GetNetCode()
        for layer, pts in runs:
            legs = [(p, q) for p, q in zip(pts, pts[1:]) if p != q]
            if not legs:
                continue
            for k in range(1, len(pts) - 1):
                u, w = pts[k] - pts[k - 1], pts[k + 1] - pts[k]
                nu, nw = math.hypot(u.x, u.y), math.hypot(w.x, w.y)
                if nu and nw and (u.x * w.x + u.y * w.y) / (nu * nw) < COS45:
                    return "corner"
            for k in range(1, len(pts) - 2):
                middle = (pts[k + 1] - pts[k]).EuclideanNorm()
                before, after = pts[k] - pts[k - 1], pts[k + 2] - pts[k + 1]
                if middle < mm(JOG_MM) and before.x * after.y - before.y * after.x == 0 and \
                        before.x * after.x + before.y * after.y > 0:
                    return "jog"
            if RS.tee_problem(self.world, legs, layer, net):
                return "tee"
            for p, q in legs:
                why = self.world.track_problem(p, q, layer, width, probe, (a, b), pours=False) or \
                    self.pour_problem(p, q, layer, width, probe)
                if why:
                    return why
        first_layer, first_pts = runs[0]
        last_layer, last_pts = runs[-1]
        if len(first_pts) > 1 and not RS.angle_ok(a, first_pts[1], first_layer, self.world):
            return "angle"
        if len(last_pts) > 1 and not RS.angle_ok(b, last_pts[-2], last_layer, self.world):
            return "angle"
        diameter, drill = (mm(v) for v in size)
        for at in via_points:
            why = self.via_problem(at, diameter, drill, probe)
            if why:
                return f"via {why}"
        return None

    def lay(self, runs, via_points, width, a, b, size):
        net = a.item.GetNet()
        added_tracks, added_vias = [], []
        for layer, pts in runs:
            legs = [(p, q) for p, q in zip(pts, pts[1:]) if p != q]
            added_tracks += RS.lay(self.board, self.world, net, layer, legs, width)
        for at in via_points:
            via = pcbnew.PCB_VIA(self.board)
            via.SetViaType(pcbnew.VIATYPE_THROUGH)
            via.SetPosition(at)
            via.SetWidth(mm(size[0]))
            via.SetDrill(mm(size[1]))
            via.SetNet(net)
            self.world.add(via)
            added_vias.append(via)
        for item in added_tracks + added_vias:
            self.islands.union(RS.uid(item), RS.uid(a.item))
        self.islands.union(RS.uid(a.item), RS.uid(b.item))
        return added_tracks, added_vias

