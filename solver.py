"""
Warehouse Bay Placement Solver — HackUPC 2026 - Mecalux Challenge

Fast axis-aligned solver. Strategy:

  1. Pure rectangle math (NO Shapely). All overlap checks are O(1) on bounds.
  2. Multi-strategy shelf packing: for every (primary bay type, axis,
     back-to-back yes/no) combination, build a full row-based layout in
     well under a second.
  3. Back-to-back row pairing: gaps of consecutive rows can overlap (the
     evaluator forbids only gap-vs-footprint), so paired rows save a gap.
  4. Maximal-rectangle gap fill: detect leftover free rectangles and fill
     them with the most cost-effective bay that still fits.
  5. Local search (swap / replace / remove) and LNS (destroy + repair)
     consume the remaining time budget.

Lower Q is better, where
    Q = (Σ price/loads) ^ (2 - Σ area / warehouse_area)
"""

import math
import time
import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

EPS = 1e-6
TOUCH_EPS = 1.0  # An overlap area smaller than this is treated as "just touching".


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BayType:
    id: int
    w: float
    d: float
    h: float
    gap: float
    n_loads: int
    price: float

    @property
    def area(self) -> float:
        return self.w * self.d

    def value_density(self) -> float:
        # Lower is better: cheap-per-load AND big bays preferred.
        return (self.price / max(self.n_loads, 1)) / max(self.area, 1.0)


@dataclass
class BayCandidate:
    """A bay type with one specific orientation already baked in."""
    type_id: int
    fp_w: float       # footprint extent along +x
    fp_d: float       # footprint extent along +y
    h: float
    gap: float
    gap_dir: int      # 0:+y, 1:+x, 2:-y, 3:-x
    rotation: int     # 0/90/180/270  (for the output CSV)
    n_loads: int
    price: float

    @property
    def fp_area(self) -> float:
        return self.fp_w * self.fp_d


@dataclass
class PlacedBay:
    cand: BayCandidate
    fp_x0: float
    fp_y0: float
    fp_x1: float
    fp_y1: float
    gap_bounds: Optional[Tuple[float, float, float, float]]  # may be None

    # ---- properties that mirror the old solver's PlacedBay API -----------
    @property
    def type_id(self) -> int:
        return self.cand.type_id

    @property
    def w(self) -> float:
        # "width" as listed in types_of_bays.csv (pre-rotation)
        return self.cand.fp_w if self.cand.rotation in (0, 180) else self.cand.fp_d

    @property
    def d(self) -> float:
        return self.cand.fp_d if self.cand.rotation in (0, 180) else self.cand.fp_w

    @property
    def h(self) -> float:
        return self.cand.h

    @property
    def n_loads(self) -> int:
        return self.cand.n_loads

    @property
    def price(self) -> float:
        return self.cand.price

    @property
    def gap(self) -> float:
        return self.cand.gap

    @property
    def rotation(self) -> int:
        return self.cand.rotation

    @property
    def x(self) -> float:
        # Pre-rotation origin point (matches the slide convention).
        r = self.cand.rotation
        if r == 0:
            return self.fp_x0
        if r == 90:
            return self.fp_x1
        if r == 180:
            return self.fp_x1
        return self.fp_x0  # 270

    @property
    def y(self) -> float:
        r = self.cand.rotation
        if r == 0:
            return self.fp_y0
        if r == 90:
            return self.fp_y0
        if r == 180:
            return self.fp_y1
        return self.fp_y1  # 270

    @property
    def area(self) -> float:
        return (self.fp_x1 - self.fp_x0) * (self.fp_y1 - self.fp_y0)

    def to_dict(self) -> dict:
        fp = [
            (self.fp_x0, self.fp_y0),
            (self.fp_x1, self.fp_y0),
            (self.fp_x1, self.fp_y1),
            (self.fp_x0, self.fp_y1),
            (self.fp_x0, self.fp_y0),
        ]
        gp_coords = []
        if self.gap_bounds is not None:
            gx0, gy0, gx1, gy1 = self.gap_bounds
            gp_coords = [
                (gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1), (gx0, gy0),
            ]

        return {
            "id": self.type_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "w": self.w,
            "d": self.d,
            "h": self.h,
            "rotation": int(self.rotation),
            "nLoads": self.n_loads,
            "price": self.price,
            "gap": self.gap,
            "footprintCoords": [[round(c[0], 2), round(c[1], 2)] for c in fp],
            "gapCoords": [[round(c[0], 2), round(c[1], 2)] for c in gp_coords],
        }


# ---------------------------------------------------------------------------
# Geometry helpers (axis-aligned only)
# ---------------------------------------------------------------------------

def rect_overlap_area(a, b) -> float:
    ix0 = max(a[0], b[0])
    iy0 = max(a[1], b[1])
    ix1 = min(a[2], b[2])
    iy1 = min(a[3], b[3])
    if ix0 >= ix1 or iy0 >= iy1:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def rects_overlap(a, b) -> bool:
    """True iff the *interior* of a and b intersect (touching is fine)."""
    return rect_overlap_area(a, b) > TOUCH_EPS


def rect_subtract(a, b):
    """Subtract rect b from a; returns 0..4 axis-aligned sub-rects."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix0 >= ix1 or iy0 >= iy1:
        return [a]
    res = []
    if ay0 < iy0 - EPS:
        res.append((ax0, ay0, ax1, iy0))
    if iy1 < ay1 - EPS:
        res.append((ax0, iy1, ax1, ay1))
    if ax0 < ix0 - EPS:
        res.append((ax0, max(ay0, iy0), ix0, min(ay1, iy1)))
    if ix1 < ax1 - EPS:
        res.append((ix1, max(ay0, iy0), ax1, min(ay1, iy1)))
    return res


def precompute_polygon_edges(vertices):
    """Return (vertical_edges, horizontal_edges) for a rectilinear polygon."""
    n = len(vertices)
    v_edges, h_edges = [], []
    for i in range(n):
        v0 = vertices[i]
        v1 = vertices[(i + 1) % n]
        if abs(v0[0] - v1[0]) < EPS:
            ymin, ymax = sorted([v0[1], v1[1]])
            v_edges.append((v0[0], ymin, ymax))
        elif abs(v0[1] - v1[1]) < EPS:
            xmin, xmax = sorted([v0[0], v1[0]])
            h_edges.append((v0[1], xmin, xmax))
    return v_edges, h_edges


def rect_in_polygon(rect, v_edges, h_edges, poly_bbox):
    """Fast rect-in-rectilinear-polygon test."""
    x0, y0, x1, y1 = rect
    px0, py0, px1, py1 = poly_bbox
    if x0 < px0 - EPS or y0 < py0 - EPS or x1 > px1 + EPS or y1 > py1 + EPS:
        return False

    # No edge of the polygon may cut the open interior of rect.
    for ex, ey0, ey1 in v_edges:
        if x0 + EPS < ex < x1 - EPS:
            if max(ey0, y0) < min(ey1, y1) - EPS:
                return False
    for ey, ex0, ex1 in h_edges:
        if y0 + EPS < ey < y1 - EPS:
            if max(ex0, x0) < min(ex1, x1) - EPS:
                return False

    # If no edge cuts, the rect is either fully inside or fully outside.
    # Cast a vertical ray upward from a point slightly off the centre.
    cx = (x0 + x1) / 2 + 0.31415  # avoid landing exactly on a vertex
    cy = (y0 + y1) / 2 + 0.27182
    count = 0
    for ey, ex0, ex1 in h_edges:
        if ey > cy and ex0 < cx < ex1:
            count += 1
    return count % 2 == 1


# ---------------------------------------------------------------------------
# Bay candidates and placement helpers
# ---------------------------------------------------------------------------

def expand_candidates(bay_types: List[BayType], rotations=(0, 90, 180, 270)) -> List[BayCandidate]:
    """Expand each bay type into one BayCandidate per allowed rotation."""
    cands = []
    for bt in bay_types:
        for rot in rotations:
            if rot in (0, 180):
                fp_w, fp_d = bt.w, bt.d
            else:
                fp_w, fp_d = bt.d, bt.w
            gap_dir = {0: 0, 90: 1, 180: 2, 270: 3}[rot]
            cands.append(BayCandidate(
                type_id=bt.id, fp_w=fp_w, fp_d=fp_d, h=bt.h, gap=bt.gap,
                gap_dir=gap_dir, rotation=rot,
                n_loads=bt.n_loads, price=bt.price,
            ))
    return cands


def make_placed(cand: BayCandidate, x0: float, y0: float) -> PlacedBay:
    """Build a PlacedBay where (x0,y0) is the bottom-left of the footprint."""
    x1 = x0 + cand.fp_w
    y1 = y0 + cand.fp_d
    if cand.gap > 0:
        if cand.gap_dir == 0:
            gp = (x0, y1, x1, y1 + cand.gap)
        elif cand.gap_dir == 1:
            gp = (x1, y0, x1 + cand.gap, y1)
        elif cand.gap_dir == 2:
            gp = (x0, y0 - cand.gap, x1, y0)
        else:
            gp = (x0 - cand.gap, y0, x0, y1)
    else:
        gp = None
    return PlacedBay(cand=cand, fp_x0=x0, fp_y0=y0, fp_x1=x1, fp_y1=y1, gap_bounds=gp)


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------

class WarehouseSolver:
    def __init__(self, warehouse_vertices, obstacles, ceiling, bay_types):
        self.vertices = list(warehouse_vertices)
        self.v_edges, self.h_edges = precompute_polygon_edges(self.vertices)
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        self.min_x, self.max_x = min(xs), max(xs)
        self.min_y, self.max_y = min(ys), max(ys)
        self.poly_bbox = (self.min_x, self.min_y, self.max_x, self.max_y)

        # Polygon area via shoelace.
        n = len(self.vertices)
        s = 0.0
        for i in range(n):
            x0, y0 = self.vertices[i]
            x1, y1 = self.vertices[(i + 1) % n]
            s += x0 * y1 - x1 * y0
        self.wh_area = abs(s) / 2

        # Obstacles in (x0, y0, x1, y1) form.
        self.obstacles = [(o[0], o[1], o[0] + o[2], o[1] + o[3]) for o in obstacles]

        # Ceiling: list of (x, h), sorted, defines a step function.
        self.ceiling = sorted([(c[0], c[1]) for c in ceiling], key=lambda c: c[0])

        # Bay types and candidates.
        self.bay_types = [
            BayType(int(b[0]), float(b[1]), float(b[2]), float(b[3]),
                    float(b[4]), int(b[5]), float(b[6]))
            for b in bay_types
        ]
        # All 4-rotation candidates
        self.all_candidates = expand_candidates(self.bay_types)
        # Only "primary" candidates (rotation 0 and 90) for shelf packing.
        self.primary_candidates = expand_candidates(self.bay_types, rotations=(0, 90))

    # ------------------------------------------------------------------
    # Ceiling
    # ------------------------------------------------------------------
    def min_ceiling(self, x0, x1):
        if not self.ceiling:
            return float("inf")
        n = len(self.ceiling)
        h_min = float("inf")
        for i in range(n):
            seg_x0 = self.ceiling[i][0]
            seg_x1 = self.ceiling[i + 1][0] if i + 1 < n else float("inf")
            if seg_x1 <= x0 + EPS:
                continue
            if seg_x0 >= x1 - EPS:
                break
            h_min = min(h_min, self.ceiling[i][1])
        return h_min

    # ------------------------------------------------------------------
    # Feasibility checks
    # ------------------------------------------------------------------
    def _free_for_fp(self, fp, h_required, placed, exclude_idx=None):
        # Polygon containment.
        if not rect_in_polygon(fp, self.v_edges, self.h_edges, self.poly_bbox):
            return False
        # Ceiling.
        if self.min_ceiling(fp[0], fp[2]) < h_required - EPS:
            return False
        # Obstacles.
        for ob in self.obstacles:
            if rects_overlap(fp, ob):
                return False
        # Placed bays.
        for i, p in enumerate(placed):
            if i == exclude_idx:
                continue
            if rects_overlap(fp, (p.fp_x0, p.fp_y0, p.fp_x1, p.fp_y1)):
                return False
            if p.gap_bounds is not None and rects_overlap(fp, p.gap_bounds):
                return False
        return True

    def _free_for_gap(self, gp, placed, exclude_idx=None):
        # Gap must be inside the polygon and not collide with obstacles or
        # with the *footprint* of any existing bay. (Gap-vs-gap is allowed.)
        if not rect_in_polygon(gp, self.v_edges, self.h_edges, self.poly_bbox):
            return False
        for ob in self.obstacles:
            if rects_overlap(gp, ob):
                return False
        for i, p in enumerate(placed):
            if i == exclude_idx:
                continue
            if rects_overlap(gp, (p.fp_x0, p.fp_y0, p.fp_x1, p.fp_y1)):
                return False
        return True

    def can_place_cand(self, cand: BayCandidate, x0: float, y0: float, placed,
                       exclude_idx=None) -> bool:
        fp = (x0, y0, x0 + cand.fp_w, y0 + cand.fp_d)
        if not self._free_for_fp(fp, cand.h, placed, exclude_idx):
            return False
        if cand.gap > 0:
            pb = make_placed(cand, x0, y0)
            if not self._free_for_gap(pb.gap_bounds, placed, exclude_idx):
                return False
        return True

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def compute_score(self, placed):
        if not placed:
            return {
                "score": float("inf"),
                "totalBays": 0, "totalLoads": 0, "totalArea": 0,
                "warehouseArea": self.wh_area, "areaUsage": 0, "totalCost": 0,
            }
        sum_pl = sum(b.cand.price / max(b.cand.n_loads, 1) for b in placed)
        sum_area = sum((b.fp_x1 - b.fp_x0) * (b.fp_y1 - b.fp_y0) for b in placed)
        exponent = 2 - (sum_area / self.wh_area)
        try:
            score = sum_pl ** exponent if sum_pl > 0 else float("inf")
        except OverflowError:
            score = float("inf")
        return {
            "score": score,
            "totalBays": len(placed),
            "totalLoads": sum(b.cand.n_loads for b in placed),
            "totalArea": sum_area,
            "warehouseArea": self.wh_area,
            "areaUsage": sum_area / self.wh_area * 100,
            "totalCost": sum(b.cand.price for b in placed),
        }

    def _q(self, placed):
        return self.compute_score(placed)["score"]

    # ------------------------------------------------------------------
    # SHELF PACKING (rows along x, advancing in y)
    # ------------------------------------------------------------------
    def _shelf_pack(self, primary: BayCandidate, fill_cands: List[BayCandidate],
                    back_to_back: bool, deadline: float) -> List[PlacedBay]:
        """
        Build a layout by stacking rows of `primary` upward, optionally pairing
        rows back-to-back so they share a gap zone.
        """
        placed: List[PlacedBay] = []

        # Force the primary row to lie horizontally: fp_w along x, fp_d along y.
        # If primary is rotated to put gap on +x or -x, shelf packing in rows
        # doesn't work well; we route those through column packing instead.
        if primary.gap_dir not in (0, 2):
            return placed

        # Use rotation 0 (gap +y) for "up" rows, rotation 180 (gap -y) for "down" rows.
        cand_up = next(
            c for c in self.all_candidates
            if c.type_id == primary.type_id and c.rotation == 0
            and c.fp_w == primary.fp_w and c.fp_d == primary.fp_d
        )
        cand_down = next(
            c for c in self.all_candidates
            if c.type_id == primary.type_id and c.rotation == 180
            and c.fp_w == primary.fp_w and c.fp_d == primary.fp_d
        )

        depth = primary.fp_d
        gap = primary.gap

        y = self.min_y
        row_idx = 0
        while y + depth <= self.max_y + EPS:
            if time.time() >= deadline:
                break

            row_cand = cand_up
            row_advance = depth + gap  # default

            if back_to_back:
                # Even rows go up (gap +y), odd rows go down (gap -y).
                # Pair (up, down) shares a gap, so the pair advances by depth*2 + gap.
                if row_idx % 2 == 0:
                    row_cand = cand_up
                    row_advance = depth  # next row will overlap its gap with this one
                else:
                    row_cand = cand_down
                    row_advance = depth + gap
            else:
                row_cand = cand_up
                row_advance = depth + gap

            # The "down" rows in back-to-back have their footprint starting at y+gap.
            row_y0 = y + gap if back_to_back and row_idx % 2 == 1 else y

            if row_y0 + depth > self.max_y + EPS:
                break

            self._fill_row_x(row_cand, fill_cands, row_y0, placed, deadline)

            y += row_advance
            row_idx += 1

        return placed

    def _fill_row_x(self, primary_cand: BayCandidate, fill_cands: List[BayCandidate],
                    row_y0: float, placed: List[PlacedBay], deadline: float) -> None:
        """Place bays along this row, primary first, smaller fillers if primary doesn't fit.

        When nothing fits at the current x, advance to the next "interesting"
        x-coordinate (obstacle edge, polygon edge, placed-bay edge) instead of
        a fixed slide.
        """
        # Pre-compute relevant x-anchors so we can skip blocked regions cleanly.
        row_height = primary_cand.fp_d
        row_y1 = row_y0 + row_height
        anchors = self._row_x_anchors(row_y0, row_y1, placed)
        anchors = sorted(set(a for a in anchors if self.min_x - EPS <= a <= self.max_x + EPS))

        ai = 0
        while ai < len(anchors):
            if time.time() >= deadline:
                return
            x = anchors[ai]
            placed_here = False

            # Primary first.
            if x + primary_cand.fp_w <= self.max_x + EPS:
                if self.can_place_cand(primary_cand, x, row_y0, placed):
                    pb = make_placed(primary_cand, x, row_y0)
                    placed.append(pb)
                    # Skip anchors covered by the new bay.
                    while ai < len(anchors) and anchors[ai] < pb.fp_x1 - EPS:
                        ai += 1
                    # Make sure the next anchor IS the new right edge.
                    if ai >= len(anchors) or abs(anchors[ai] - pb.fp_x1) > EPS:
                        anchors.insert(ai, pb.fp_x1)
                    placed_here = True
                    continue

            if not placed_here:
                # Try smaller / different fill candidates that fit in this row's depth.
                best = None
                best_eff = float("inf")
                for fc in fill_cands:
                    if fc.fp_d > row_height + EPS:
                        continue
                    if x + fc.fp_w > self.max_x + EPS:
                        continue
                    if not self.can_place_cand(fc, x, row_y0, placed):
                        continue
                    eff = (fc.price / max(fc.n_loads, 1)) / max(fc.fp_area, 1.0)
                    if eff < best_eff:
                        best_eff = eff
                        best = fc
                if best is not None:
                    pb = make_placed(best, x, row_y0)
                    placed.append(pb)
                    while ai < len(anchors) and anchors[ai] < pb.fp_x1 - EPS:
                        ai += 1
                    if ai >= len(anchors) or abs(anchors[ai] - pb.fp_x1) > EPS:
                        anchors.insert(ai, pb.fp_x1)
                else:
                    ai += 1

    def _row_x_anchors(self, y0: float, y1: float, placed: List[PlacedBay]):
        """Collect x-coordinates that matter for a row spanning y∈[y0, y1]."""
        anchors = [self.min_x, self.max_x]
        # Polygon vertices.
        for v in self.vertices:
            anchors.append(v[0])
        # Obstacle edges that affect this row.
        for ob in self.obstacles:
            if ob[3] > y0 - EPS and ob[1] < y1 + EPS:
                anchors.append(ob[0])
                anchors.append(ob[2])
        # Placed bay edges (footprint + gap) intersecting the y-band.
        for p in placed:
            if p.fp_y1 > y0 - EPS and p.fp_y0 < y1 + EPS:
                anchors.append(p.fp_x0)
                anchors.append(p.fp_x1)
            if p.gap_bounds is not None:
                gb = p.gap_bounds
                if gb[3] > y0 - EPS and gb[1] < y1 + EPS:
                    anchors.append(gb[0])
                    anchors.append(gb[2])
        # Ceiling step boundaries (a bay can end at one and a smaller-h start there).
        for cx, _ in self.ceiling:
            anchors.append(cx)
        return anchors

    # ------------------------------------------------------------------
    # COLUMN PACKING (columns along y, advancing in x). Mirror of the above.
    # ------------------------------------------------------------------
    def _column_pack(self, primary: BayCandidate, fill_cands: List[BayCandidate],
                     back_to_back: bool, deadline: float) -> List[PlacedBay]:
        placed: List[PlacedBay] = []
        if primary.gap_dir not in (1, 3):
            return placed

        cand_right = next(
            c for c in self.all_candidates
            if c.type_id == primary.type_id and c.rotation == 90
            and c.fp_w == primary.fp_w and c.fp_d == primary.fp_d
        )
        cand_left = next(
            c for c in self.all_candidates
            if c.type_id == primary.type_id and c.rotation == 270
            and c.fp_w == primary.fp_w and c.fp_d == primary.fp_d
        )

        col_w = primary.fp_w
        gap = primary.gap

        x = self.min_x
        col_idx = 0
        while x + col_w <= self.max_x + EPS:
            if time.time() >= deadline:
                break

            if back_to_back:
                if col_idx % 2 == 0:
                    col_cand = cand_right
                    col_advance = col_w
                else:
                    col_cand = cand_left
                    col_advance = col_w + gap
            else:
                col_cand = cand_right
                col_advance = col_w + gap

            col_x0 = x + gap if back_to_back and col_idx % 2 == 1 else x
            if col_x0 + col_w > self.max_x + EPS:
                break

            self._fill_col_y(col_cand, fill_cands, col_x0, placed, deadline)

            x += col_advance
            col_idx += 1

        return placed

    def _fill_col_y(self, primary_cand: BayCandidate, fill_cands: List[BayCandidate],
                    col_x0: float, placed: List[PlacedBay], deadline: float) -> None:
        """Place bays along this column. Same edge-anchored strategy as the
        row variant: when nothing fits at the current y, advance to the next
        meaningful y-coordinate (obstacle edge, polygon edge, placed-bay edge)
        instead of using a fixed slide."""
        col_width = primary_cand.fp_w
        col_x1 = col_x0 + col_width
        anchors = self._col_y_anchors(col_x0, col_x1, placed)
        anchors = sorted(set(a for a in anchors if self.min_y - EPS <= a <= self.max_y + EPS))

        ai = 0
        while ai < len(anchors):
            if time.time() >= deadline:
                return
            y = anchors[ai]
            placed_here = False

            # Primary first.
            if y + primary_cand.fp_d <= self.max_y + EPS:
                if self.can_place_cand(primary_cand, col_x0, y, placed):
                    pb = make_placed(primary_cand, col_x0, y)
                    placed.append(pb)
                    while ai < len(anchors) and anchors[ai] < pb.fp_y1 - EPS:
                        ai += 1
                    if ai >= len(anchors) or abs(anchors[ai] - pb.fp_y1) > EPS:
                        anchors.insert(ai, pb.fp_y1)
                    placed_here = True
                    continue

            if not placed_here:
                best = None
                best_eff = float("inf")
                for fc in fill_cands:
                    if fc.fp_w > col_width + EPS:
                        continue
                    if y + fc.fp_d > self.max_y + EPS:
                        continue
                    if not self.can_place_cand(fc, col_x0, y, placed):
                        continue
                    eff = (fc.price / max(fc.n_loads, 1)) / max(fc.fp_area, 1.0)
                    if eff < best_eff:
                        best_eff = eff
                        best = fc
                if best is not None:
                    pb = make_placed(best, col_x0, y)
                    placed.append(pb)
                    while ai < len(anchors) and anchors[ai] < pb.fp_y1 - EPS:
                        ai += 1
                    if ai >= len(anchors) or abs(anchors[ai] - pb.fp_y1) > EPS:
                        anchors.insert(ai, pb.fp_y1)
                else:
                    ai += 1

    def _col_y_anchors(self, x0: float, x1: float, placed: List[PlacedBay]):
        """Collect y-coordinates that matter for a column spanning x∈[x0, x1]."""
        anchors = [self.min_y, self.max_y]
        # Polygon vertices.
        for v in self.vertices:
            anchors.append(v[1])
        # Obstacle edges that affect this column.
        for ob in self.obstacles:
            if ob[2] > x0 - EPS and ob[0] < x1 + EPS:
                anchors.append(ob[1])
                anchors.append(ob[3])
        # Placed bay edges (footprint + gap) intersecting the x-band.
        for p in placed:
            if p.fp_x1 > x0 - EPS and p.fp_x0 < x1 + EPS:
                anchors.append(p.fp_y0)
                anchors.append(p.fp_y1)
            if p.gap_bounds is not None:
                gb = p.gap_bounds
                if gb[2] > x0 - EPS and gb[0] < x1 + EPS:
                    anchors.append(gb[1])
                    anchors.append(gb[3])
        return anchors

    # ------------------------------------------------------------------
    # Maximal-rectangle gap fill
    # ------------------------------------------------------------------
    def _free_rectangles(self, placed: List[PlacedBay]) -> List[Tuple[float, float, float, float]]:
        """Compute approximate maximal free rectangles by subtracting all
        obstacles + placed footprints + placed gaps from the polygon bbox.
        For rectilinear polygons we also subtract the area outside the polygon
        by re-using the polygon's vertical edges to slice the bbox."""
        rects = [self.poly_bbox]

        # Slice out the area outside the polygon. We approximate by removing
        # rectangles that are not inside the polygon: do a coarse vertical-strip
        # decomposition of "outside the polygon".
        # Simpler approach: subtract the obstacles + placed bodies, then drop
        # any candidate rect whose centre is outside the polygon.
        blockers = list(self.obstacles)
        for p in placed:
            blockers.append((p.fp_x0, p.fp_y0, p.fp_x1, p.fp_y1))
            if p.gap_bounds is not None:
                blockers.append(p.gap_bounds)

        for b in blockers:
            new = []
            for r in rects:
                new.extend(rect_subtract(r, b))
            rects = new

        # Filter by polygon containment (each free rect must lie in polygon).
        good = []
        for r in rects:
            if (r[2] - r[0]) < 50 or (r[3] - r[1]) < 50:
                continue
            if rect_in_polygon(r, self.v_edges, self.h_edges, self.poly_bbox):
                good.append(r)
        # Sort by area descending so we try largest holes first.
        good.sort(key=lambda r: -(r[2] - r[0]) * (r[3] - r[1]))
        return good

    def _gap_fill(self, placed: List[PlacedBay], deadline: float) -> bool:
        """Fill each maximal free rectangle with as many bays as we can — not
        just one. For each rect we pick the best-value candidate that fits and
        sweep rows along its width, then advance up. We re-compute the free
        rectangles after each pass and stop when nothing more fits."""
        improved_any = False
        # Order candidates: best area-per-cost-per-load first.
        cands = sorted(
            self.all_candidates,
            key=lambda c: -(c.fp_area * c.n_loads / max(c.price, 1.0)),
        )

        # Iterate passes until no rect can absorb anything new (or time out).
        for _ in range(8):
            if time.time() >= deadline:
                break
            rects = self._free_rectangles(placed)
            if not rects:
                break
            improved_pass = False

            for r in rects:
                if time.time() >= deadline:
                    break
                rx0, ry0, rx1, ry1 = r
                # Mini shelf-pack inside the rect.
                if self._fill_rect(rx0, ry0, rx1, ry1, cands, placed, deadline):
                    improved_pass = True
                    improved_any = True

            if not improved_pass:
                break
        return improved_any

    def _fill_rect(self, rx0: float, ry0: float, rx1: float, ry1: float,
                   cands: List[BayCandidate], placed: List[PlacedBay],
                   deadline: float) -> bool:
        """Fill one free rectangle with rows of bays. Returns True if at least
        one bay was placed inside it."""
        improved = False
        rw = rx1 - rx0
        rh = ry1 - ry0
        if rw < 50 or rh < 50:
            return False

        y = ry0
        # Cap iterations to avoid pathological loops.
        for _ in range(200):
            if time.time() >= deadline:
                break
            if y >= ry1 - EPS:
                break

            # Pick the best candidate that fits a row at this y.
            row_cand = None
            for c in cands:
                if c.fp_w > rw + EPS:
                    continue
                if y + c.fp_d > ry1 + EPS:
                    continue
                # Probe the bottom-left corner.
                if self.can_place_cand(c, rx0, y, placed):
                    row_cand = c
                    break
            if row_cand is None:
                # Nothing fits at this y. Advance to the next placed-bay edge
                # within the rect (or break if there is none above y).
                next_y = None
                for p in placed:
                    if p.fp_y1 > y + EPS and p.fp_y1 < ry1 + EPS \
                            and p.fp_x1 > rx0 - EPS and p.fp_x0 < rx1 + EPS:
                        if next_y is None or p.fp_y1 < next_y:
                            next_y = p.fp_y1
                if next_y is None or next_y <= y + EPS:
                    break
                y = next_y
                continue

            # Place the chosen candidate, then sweep across in x using the
            # same kind of edge-anchored fill.
            x = rx0
            row_h = row_cand.fp_d
            while x + row_cand.fp_w <= rx1 + EPS:
                if time.time() >= deadline:
                    break
                if self.can_place_cand(row_cand, x, y, placed):
                    pb = make_placed(row_cand, x, y)
                    placed.append(pb)
                    improved = True
                    x = pb.fp_x1
                else:
                    # Try a smaller filler at this x.
                    placed_filler = False
                    for fc in cands:
                        if fc is row_cand:
                            continue
                        if fc.fp_w > rx1 - x + EPS:
                            continue
                        if fc.fp_d > row_h + EPS:
                            continue
                        if y + fc.fp_d > ry1 + EPS:
                            continue
                        if self.can_place_cand(fc, x, y, placed):
                            pb = make_placed(fc, x, y)
                            placed.append(pb)
                            improved = True
                            x = pb.fp_x1
                            placed_filler = True
                            break
                    if not placed_filler:
                        x += max(50.0, row_cand.fp_w / 4)
            y += row_h
        return improved

    # ------------------------------------------------------------------
    # Full-polygon edge-anchored sweep (post-polish gap completion)
    # ------------------------------------------------------------------
    def _sweep_fill(self, placed: List[PlacedBay], deadline: float,
                    only_q_improving: bool = False) -> bool:
        """Try to place bays at every interesting (x, y) anchor combination
        across the whole polygon. This catches free spaces that the maximal-
        rectangle decomposition fragments into pieces that each look 'too
        small' but together fit a bay.

        If only_q_improving is True, only commit a placement if it strictly
        improves Q (useful in cases where adding a bay can hurt the score)."""
        # Collect anchor coordinates from polygon, obstacles, ceiling and
        # current placed bays.
        x_anchors = {self.min_x, self.max_x}
        y_anchors = {self.min_y, self.max_y}
        for v in self.vertices:
            x_anchors.add(v[0])
            y_anchors.add(v[1])
        for ob in self.obstacles:
            x_anchors.add(ob[0]); x_anchors.add(ob[2])
            y_anchors.add(ob[1]); y_anchors.add(ob[3])
        for cx, _ in self.ceiling:
            x_anchors.add(cx)
        for p in placed:
            x_anchors.add(p.fp_x0); x_anchors.add(p.fp_x1)
            y_anchors.add(p.fp_y0); y_anchors.add(p.fp_y1)
            if p.gap_bounds is not None:
                gb = p.gap_bounds
                x_anchors.add(gb[0]); x_anchors.add(gb[2])
                y_anchors.add(gb[1]); y_anchors.add(gb[3])

        xs = sorted(a for a in x_anchors if self.min_x - EPS <= a <= self.max_x + EPS)
        ys = sorted(a for a in y_anchors if self.min_y - EPS <= a <= self.max_y + EPS)

        # Candidates ordered by best area*loads/price.
        cands = sorted(
            self.all_candidates,
            key=lambda c: -(c.fp_area * c.n_loads / max(c.price, 1.0)),
        )

        improved = False
        cur_q = self._q(placed) if only_q_improving else None

        for y in ys:
            if time.time() >= deadline:
                break
            for x in xs:
                if time.time() >= deadline:
                    break
                for c in cands:
                    if x + c.fp_w > self.max_x + EPS:
                        continue
                    if y + c.fp_d > self.max_y + EPS:
                        continue
                    if not self.can_place_cand(c, x, y, placed):
                        continue
                    pb = make_placed(c, x, y)
                    placed.append(pb)
                    if only_q_improving:
                        q = self._q(placed)
                        if q < cur_q - EPS:
                            cur_q = q
                            improved = True
                            # Refresh the anchor set with the new edges.
                            x_anchors.update([pb.fp_x0, pb.fp_x1])
                            y_anchors.update([pb.fp_y0, pb.fp_y1])
                            if pb.gap_bounds is not None:
                                gb = pb.gap_bounds
                                x_anchors.update([gb[0], gb[2]])
                                y_anchors.update([gb[1], gb[3]])
                        else:
                            placed.pop()
                    else:
                        improved = True
                        x_anchors.update([pb.fp_x0, pb.fp_x1])
                        y_anchors.update([pb.fp_y0, pb.fp_y1])
                        if pb.gap_bounds is not None:
                            gb = pb.gap_bounds
                            x_anchors.update([gb[0], gb[2]])
                            y_anchors.update([gb[1], gb[3]])
                    break  # next (x, y)
        return improved

    # ------------------------------------------------------------------
    # Local search
    # ------------------------------------------------------------------
    def _try_swap_in_place(self, placed: List[PlacedBay], deadline: float) -> bool:
        """For each placed bay, try replacing it with another candidate at the
        same bottom-left corner."""
        improved_any = False
        cur_q = self._q(placed)
        i = 0
        while i < len(placed):
            if time.time() >= deadline:
                break
            p = placed[i]
            best = None
            best_q = cur_q
            for c in self.all_candidates:
                if c.type_id == p.type_id and c.rotation == p.rotation:
                    continue
                if not self.can_place_cand(c, p.fp_x0, p.fp_y0, placed, exclude_idx=i):
                    continue
                # Probe quickly: avoid full rebuild list, just test by score function.
                placed[i] = make_placed(c, p.fp_x0, p.fp_y0)
                q = self._q(placed)
                if q < best_q - EPS:
                    best_q = q
                    best = placed[i]
                placed[i] = p
            if best is not None:
                placed[i] = best
                cur_q = best_q
                improved_any = True
            i += 1
        return improved_any

    def _try_remove(self, placed: List[PlacedBay], deadline: float) -> bool:
        """Remove any bay whose deletion improves Q. (Possible because the
        exponent on Σ price/loads can dominate in some cases.)"""
        improved = False
        cur_q = self._q(placed)
        i = 0
        while i < len(placed):
            if time.time() >= deadline:
                break
            removed = placed.pop(i)
            q = self._q(placed)
            if q < cur_q - EPS:
                cur_q = q
                improved = True
            else:
                placed.insert(i, removed)
                i += 1
        return improved

    # ------------------------------------------------------------------
    # LNS: destroy + repair
    # ------------------------------------------------------------------
    def _destroy_random_zone(self, placed: List[PlacedBay], rng: random.Random,
                             ratio: float = 0.25) -> List[PlacedBay]:
        if not placed:
            return []
        cx = rng.uniform(self.min_x, self.max_x)
        cy = rng.uniform(self.min_y, self.max_y)
        ww = (self.max_x - self.min_x) * rng.uniform(0.20, 0.45)
        hh = (self.max_y - self.min_y) * rng.uniform(0.20, 0.45)
        zone = (cx - ww / 2, cy - hh / 2, cx + ww / 2, cy + hh / 2)
        max_remove = max(1, int(len(placed) * ratio))
        keep = []
        removed = 0
        # Sort so removing the worst-performing (high price/load) inside the zone
        # is tried first.
        order = sorted(
            placed,
            key=lambda b: -(b.cand.price / max(b.cand.n_loads, 1)),
        )
        remove_ids = set()
        for b in order:
            if removed >= max_remove:
                break
            fp = (b.fp_x0, b.fp_y0, b.fp_x1, b.fp_y1)
            if rects_overlap(fp, zone):
                remove_ids.add(id(b))
                removed += 1
        for b in placed:
            if id(b) not in remove_ids:
                keep.append(b)
        return keep

    def _destroy_worst(self, placed: List[PlacedBay], ratio: float = 0.18) -> List[PlacedBay]:
        if not placed:
            return []
        n_remove = max(1, int(len(placed) * ratio))
        ranked = sorted(
            placed,
            key=lambda b: (b.cand.price / max(b.cand.n_loads, 1), -b.area),
            reverse=True,
        )
        kill = set(id(b) for b in ranked[:n_remove])
        return [b for b in placed if id(b) not in kill]

    # ------------------------------------------------------------------
    # Main solve
    # ------------------------------------------------------------------
    def solve(self, time_limit: float = 28.0):
        start = time.time()
        deadline = start + time_limit
        rng = random.Random(0xC0FFEE)

        if not self.bay_types:
            stats = self.compute_score([])
            stats["solveTime"] = round(time.time() - start, 3)
            return [], stats

        # ------------------------------------------------------------------
        # Phase 1: exhaustive multi-strategy shelf/column packing.
        # ------------------------------------------------------------------
        construction_budget = min(time_limit * 0.35, 8.0)
        construction_deadline = start + construction_budget

        # Sort candidates for the "primary row" choice.
        # Primary candidates are rotation 0 (rows) and rotation 90 (cols).
        primary_choices = []
        for c in self.primary_candidates:
            primary_choices.append(c)

        # We want to try "good" primaries first.
        primary_choices.sort(
            key=lambda c: (
                # Lower is better:
                (c.price / max(c.n_loads, 1)),  # cheapest per load
                -c.fp_area,                      # then biggest
            )
        )

        # Fill candidates sorted by "fills well": large area + cheap per load.
        fill_cands = sorted(
            self.all_candidates,
            key=lambda c: ((c.price / max(c.n_loads, 1)) / max(c.fp_area, 1.0)),
        )

        best_solution: List[PlacedBay] = []
        best_q = float("inf")

        # The heart: try every primary × {b2b, no b2b} × {row, col} until we
        # run out of budget.
        attempts = 0
        for primary in primary_choices:
            if time.time() >= construction_deadline:
                break
            for back_to_back in (False, True):
                if time.time() >= construction_deadline:
                    break
                # Per-attempt slice of remaining time, capped.
                per_attempt = max(0.4, (construction_deadline - time.time()) /
                                  max(1, len(primary_choices) * 2 - attempts))
                attempt_deadline = min(construction_deadline, time.time() + per_attempt)
                attempts += 1
                if primary.gap_dir in (0, 2):  # row mode
                    sol = self._shelf_pack(primary, fill_cands, back_to_back, attempt_deadline)
                else:  # col mode
                    sol = self._column_pack(primary, fill_cands, back_to_back, attempt_deadline)

                if not sol:
                    continue

                # Quick gap fill before scoring so the comparison is fair.
                gap_deadline = min(deadline, time.time() + 0.5)
                self._gap_fill(sol, gap_deadline)

                q = self._q(sol)
                if q < best_q:
                    best_q = q
                    best_solution = list(sol)

        if not best_solution:
            stats = self.compute_score([])
            stats["solveTime"] = round(time.time() - start, 3)
            return [], stats

        # ------------------------------------------------------------------
        # Phase 2: local-search polish.
        # ------------------------------------------------------------------
        polish_deadline = min(deadline, time.time() + max(2.0, time_limit * 0.15))
        for _ in range(4):
            if time.time() >= polish_deadline:
                break
            improved = False
            improved |= self._gap_fill(best_solution, polish_deadline)
            # Full-polygon anchor sweep, only commit if it improves Q.
            improved |= self._sweep_fill(best_solution, polish_deadline,
                                         only_q_improving=True)
            improved |= self._try_swap_in_place(best_solution, polish_deadline)
            improved |= self._try_remove(best_solution, polish_deadline)
            if not improved:
                break
        best_q = self._q(best_solution)

        # ------------------------------------------------------------------
        # Phase 3: LNS until the deadline.
        # ------------------------------------------------------------------
        iteration = 0
        while time.time() < deadline - 1.0:
            iteration += 1
            base = list(best_solution)
            mode = iteration % 3
            if mode == 0:
                cand = self._destroy_worst(base, ratio=0.18)
            elif mode == 1:
                cand = self._destroy_random_zone(base, rng, ratio=0.25)
            else:
                # Random subset
                k = max(1, int(len(base) * 0.15))
                idxs = set(rng.sample(range(len(base)), min(k, len(base))))
                cand = [b for i, b in enumerate(base) if i not in idxs]

            repair_deadline = min(deadline, time.time() + 1.5)
            self._gap_fill(cand, repair_deadline)
            self._sweep_fill(cand, repair_deadline, only_q_improving=True)
            self._try_swap_in_place(cand, repair_deadline)

            q = self._q(cand)
            if q < best_q - EPS:
                best_q = q
                best_solution = list(cand)

        # Final stats.
        stats = self.compute_score(best_solution)
        stats["solveTime"] = round(time.time() - start, 3)
        return best_solution, stats


# ---------------------------------------------------------------------------
# Parsers (same signatures as the original solver)
# ---------------------------------------------------------------------------

def parse_warehouse(text):
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


def parse_obstacles(text):
    if not text or not text.strip():
        return []
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


def parse_ceiling(text):
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]


def parse_bays(text):
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]