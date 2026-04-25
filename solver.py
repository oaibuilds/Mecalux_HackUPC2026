"""
Warehouse Bay Placement Solver — HackUPC 2026 - Mecalux Challenge
"""

import math
from shapely.geometry import Polygon, box
from shapely.prepared import prep
from shapely.ops import orient
from dataclasses import dataclass
import time

TOUCH_EPSILON = 1.0


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

    def efficiency(self, wh_area: float) -> float:
        return self.price / self.n_loads - self.area / wh_area


@dataclass
class PlacedBay:
    type_id: int
    x: float
    y: float
    rotation: float
    w: float
    d: float
    h: float
    n_loads: int
    price: float
    gap: float
    footprint: object
    gap_poly: object
    fp_bounds: tuple

    @property
    def area(self) -> float:
        return self.w * self.d

    def to_dict(self) -> dict:
        fp_coords = list(self.footprint.exterior.coords)
        gp_coords = (
            list(self.gap_poly.exterior.coords)
            if self.gap_poly and not self.gap_poly.is_empty
            else []
        )
        return {
            "id": self.type_id,
            "x": round(self.x, 2),
            "y": round(self.y, 2),
            "w": self.w,
            "d": self.d,
            "h": self.h,
            "rotation": round(self.rotation, 2),
            "nLoads": self.n_loads,
            "price": self.price,
            "gap": self.gap,
            "footprintCoords": [[round(c[0], 2), round(c[1], 2)] for c in fp_coords],
            "gapCoords": [[round(c[0], 2), round(c[1], 2)] for c in gp_coords],
        }


def make_bay_polygons(x, y, w, d, gap, angle_deg):
    rad = math.radians(angle_deg)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    def rot(px, py):
        return (px * cos_a - py * sin_a + x, px * sin_a + py * cos_a + y)

    fp = Polygon([rot(0, 0), rot(w, 0), rot(w, d), rot(0, d)])
    gp = Polygon([rot(0, d), rot(w, d), rot(w, d + gap), rot(0, d + gap)]) if gap > 0 else Polygon()
    return fp, gp


def get_ceiling_at(x, ceiling):
    """Step function — constant fins al següent breakpoint."""
    if not ceiling:
        return float("inf")
    ceiling = sorted(ceiling, key=lambda c: c[0])
    current = ceiling[0][1]
    for cx, h in ceiling:
        if x >= cx:
            current = h
        else:
            break
    return current


def min_ceiling_over_bounds(minx, maxx, ceiling):
    """Mínim de la ceiling sobre tot el rang x del bay."""
    if not ceiling:
        return float("inf")
    if maxx < minx:
        minx, maxx = maxx, minx
    ceiling = sorted(ceiling, key=lambda c: c[0])
    test_xs = [minx, maxx]
    for cx, _ in ceiling:
        if minx < cx < maxx:
            test_xs += [cx - 0.001, cx + 0.001]
    return min(get_ceiling_at(x, ceiling) for x in test_xs)


def bounds_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def real_overlap(a, b, a_b, b_b):
    if not bounds_overlap(a_b, b_b):
        return False
    if not a.intersects(b):
        return False
    return a.intersection(b).area > TOUCH_EPSILON


class WarehouseSolver:
    def __init__(self, warehouse_vertices, obstacles, ceiling, bay_types):
        self.vertices = warehouse_vertices
        self.polygon = Polygon([(v[0], v[1]) for v in warehouse_vertices])
        if not self.polygon.is_valid:
            self.polygon = self.polygon.buffer(0)
        self.polygon = orient(self.polygon, sign=1.0)
        self.prepared = prep(self.polygon)
        self.wh_area = self.polygon.area

        self.obstacles = obstacles
        self.obstacle_polys = [box(o[0], o[1], o[0] + o[2], o[1] + o[3]) for o in obstacles]
        self.obstacle_bounds = [p.bounds for p in self.obstacle_polys]

        self.ceiling = sorted(ceiling, key=lambda c: c[0])
        self.bay_types = [
            BayType(
                id=int(b[0]),
                w=float(b[1]),
                d=float(b[2]),
                h=float(b[3]),
                gap=float(b[4]),
                n_loads=int(b[5]),
                price=float(b[6]),
            )
            for b in bay_types
        ]

        bds = self.polygon.bounds
        self.min_x, self.min_y, self.max_x, self.max_y = bds

    def can_place(self, x, y, bt, angle, placed, exclude_idx=None):
        fp, gp = make_bay_polygons(x, y, bt.w, bt.d, bt.gap, angle)
        fp_b = fp.bounds

        if not self.prepared.contains(fp):
            return None

        if min_ceiling_over_bounds(fp_b[0], fp_b[2], self.ceiling) < bt.h:
            return None

        for poly, bds in zip(self.obstacle_polys, self.obstacle_bounds):
            if real_overlap(fp, poly, fp_b, bds):
                return None

        for i, p in enumerate(placed):
            if i == exclude_idx:
                continue

            if real_overlap(fp, p.footprint, fp_b, p.fp_bounds):
                return None

            if p.gap_poly and not p.gap_poly.is_empty:
                if real_overlap(fp, p.gap_poly, fp_b, p.gap_poly.bounds):
                    return None

        if bt.gap > 0 and not gp.is_empty:
            gp_b = gp.bounds

            if not self.prepared.contains(gp):
                return None

            for poly, bds in zip(self.obstacle_polys, self.obstacle_bounds):
                if real_overlap(gp, poly, gp_b, bds):
                    return None

            for i, p in enumerate(placed):
                if i == exclude_idx:
                    continue

                if real_overlap(gp, p.footprint, gp_b, p.fp_bounds):
                    return None

        return fp, gp

    def _make_bay(self, x, y, bt, angle, fp, gp):
        return PlacedBay(
            type_id=bt.id,
            x=x,
            y=y,
            rotation=angle,
            w=bt.w,
            d=bt.d,
            h=bt.h,
            n_loads=bt.n_loads,
            price=bt.price,
            gap=bt.gap,
            footprint=fp,
            gap_poly=gp,
            fp_bounds=fp.bounds,
        )

    def _place_first(self, x, y, candidates, placed):
        """Col·loca el primer candidat vàlid — ràpid per omplir."""
        for bt, ang in candidates:
            result = self.can_place(x, y, bt, ang, placed)
            if result:
                fp, gp = result
                placed.append(self._make_bay(x, y, bt, ang, fp, gp))
                return True
        return False

    def _place_best_q(self, x, y, candidates, placed, exclude_idx=None):
        """Col·loca el candidat que minimitza la Q — per optimitzar."""
        best_bay, best_q = None, float("inf")

        for bt, ang in candidates:
            result = self.can_place(x, y, bt, ang, placed, exclude_idx)
            if not result:
                continue

            fp, gp = result
            candidate = self._make_bay(x, y, bt, ang, fp, gp)
            q = self.compute_score(placed + [candidate])["score"]

            if q < best_q:
                best_q = q
                best_bay = candidate

        if best_bay is not None:
            placed.append(best_bay)
            return True

        return False

    def compute_score(self, placed):
        if not placed:
            return {
                "score": float("inf"),
                "totalBays": 0,
                "totalLoads": 0,
                "totalArea": 0,
                "warehouseArea": self.wh_area,
                "areaUsage": 0,
                "totalCost": 0,
            }

        sum_pl = sum(b.price / b.n_loads for b in placed)
        sum_area = sum(b.area for b in placed)
        exponent = 2 - (sum_area / self.wh_area)
        score = sum_pl ** exponent

        return {
            "score": score,
            "totalBays": len(placed),
            "totalLoads": sum(b.n_loads for b in placed),
            "totalArea": sum_area,
            "warehouseArea": self.wh_area,
            "areaUsage": sum_area / self.wh_area * 100,
            "totalCost": sum(b.price for b in placed),
        }

    def _collect_edge_positions(self, placed):
        xs = set([self.min_x, self.max_x])
        ys = set([self.min_y, self.max_y])

        for p in placed:
            b = p.fp_bounds
            xs.update([b[0], b[2]])
            ys.update([b[1], b[3]])

            if p.gap_poly and not p.gap_poly.is_empty:
                gb = p.gap_poly.bounds
                xs.update([gb[0], gb[2]])
                ys.update([gb[1], gb[3]])

        for o in self.obstacles:
            xs.update([o[0], o[0] + o[2]])
            ys.update([o[1], o[1] + o[3]])

        for v in self.vertices:
            xs.add(v[0])
            ys.add(v[1])

        return sorted(xs), sorted(ys)

    def _local_search(self, placed, candidates, time_limit, start):
        while time.time() - start < time_limit * 0.95:
            improved = False
            current_q = self.compute_score(placed)["score"]

            # ── Swap ─────────────────────────────────────────────────────
            for i in range(len(placed)):
                if time.time() - start > time_limit * 0.95:
                    break

                p = placed[i]
                best_swap, best_q = None, current_q

                for bt, angle in candidates:
                    if bt.id == p.type_id and angle == p.rotation:
                        continue

                    result = self.can_place(p.x, p.y, bt, angle, placed, exclude_idx=i)
                    if not result:
                        continue

                    fp, gp = result
                    new_bay = self._make_bay(p.x, p.y, bt, angle, fp, gp)
                    q = self.compute_score(placed[:i] + [new_bay] + placed[i + 1:])["score"]

                    if q < best_q:
                        best_q = q
                        best_swap = new_bay

                if best_swap is not None:
                    placed[i] = best_swap
                    current_q = best_q
                    improved = True

            # ── Move (NOU) ────────────────────────────────────────────────
            # Intenta moure cada bay a una altra posició (edge positions)
            xs, ys = self._collect_edge_positions(placed)

            for i in range(len(placed)):
                if time.time() - start > time_limit * 0.95:
                    break

                p = placed[i]
                best_move, best_q = None, current_q

                # Busca el BayType original una vegada per bay
                bt = next((b for b in self.bay_types if b.id == p.type_id), None)
                if bt is None:
                    continue

                # Prova el mateix tipus i rotació a totes les posicions edge
                for ny in ys:
                    if time.time() - start > time_limit * 0.95:
                        break

                    for nx in xs:
                        if time.time() - start > time_limit * 0.95:
                            break

                        if nx == p.x and ny == p.y:
                            continue

                        result = self.can_place(nx, ny, bt, p.rotation, placed, exclude_idx=i)
                        if not result:
                            continue

                        fp, gp = result
                        new_bay = self._make_bay(nx, ny, bt, p.rotation, fp, gp)
                        test = placed[:i] + [new_bay] + placed[i + 1:]
                        q = self.compute_score(test)["score"]

                        if q < best_q:
                            best_q = q
                            best_move = new_bay

                if best_move is not None:
                    placed[i] = best_move
                    current_q = best_q
                    improved = True

                    # Actualitza edge positions amb la nova posició
                    xs, ys = self._collect_edge_positions(placed)

            # ── Removal ──────────────────────────────────────────────────
            i = 0
            while i < len(placed):
                if time.time() - start > time_limit * 0.95:
                    break

                candidate = placed[:i] + placed[i + 1:]
                new_q = self.compute_score(candidate)["score"]

                if new_q < current_q:
                    placed.pop(i)
                    current_q = new_q
                    improved = True
                else:
                    i += 1

            # ── Fill buits ────────────────────────────────────────────────
            xs, ys = self._collect_edge_positions(placed)

            for y in ys:
                if time.time() - start > time_limit * 0.95:
                    break

                for x in xs:
                    if time.time() - start > time_limit * 0.95:
                        break

                    if self._place_best_q(x, y, candidates, placed):
                        improved = True

            if not improved:
                step = min(
                    min(bt.w for bt in self.bay_types),
                    min(bt.d for bt in self.bay_types),
                ) / 2

                y = self.min_y
                while y < self.max_y and time.time() - start < time_limit * 0.95:
                    x = self.min_x

                    while x < self.max_x and time.time() - start < time_limit * 0.95:
                        if self._place_best_q(x, y, candidates, placed):
                            improved = True
                        x += step

                    y += step

                break

        return placed

    def solve(self, time_limit=28.0, extra_angles=None):
        start = time.time()

        all_angles = [0.0, 90.0, 180.0, 270.0] + (extra_angles or [])
        sorted_types = sorted(self.bay_types, key=lambda b: b.efficiency(self.wh_area))
        candidates = [(bt, ang) for bt in sorted_types for ang in all_angles]

        placed = []

        if not self.bay_types:
            stats = self.compute_score(placed)
            stats["solveTime"] = round(time.time() - start, 3)
            return placed, stats

        min_dim = min(min(bt.w, bt.d) for bt in self.bay_types)

        # PASS 1: Strip packing ràpid ─────────────────────────────────
        step = max(50.0, min_dim / 2)

        y = self.min_y
        while y < self.max_y and time.time() - start < time_limit * 0.2:
            x = self.min_x

            while x < self.max_x and time.time() - start < time_limit * 0.2:
                if self._place_first(x, y, candidates, placed):
                    x = placed[-1].fp_bounds[2]
                else:
                    x += step

            y += step

        # PASS 2: Gap filling fi ──────────────────────────────────────
        step2 = max(25.0, min_dim / 4)

        y = self.min_y
        while y < self.max_y and time.time() - start < time_limit * 0.35:
            x = self.min_x

            while x < self.max_x and time.time() - start < time_limit * 0.35:
                self._place_first(x, y, candidates, placed)
                x += step2

            y += step2

        # PASS 3: Edge-snapping ───────────────────────────────────────
        if time.time() - start < time_limit * 0.45:
            xs, ys = self._collect_edge_positions(placed)

            for y in ys:
                if time.time() - start > time_limit * 0.45:
                    break

                for x in xs:
                    if time.time() - start > time_limit * 0.45:
                        break

                    self._place_first(x, y, candidates, placed)

        # PASS 4: Local search fins esgotar el temps ──────────────────
        placed = self._local_search(placed, candidates, time_limit, start)

        stats = self.compute_score(placed)
        stats["solveTime"] = round(time.time() - start, 3)

        return placed, stats


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