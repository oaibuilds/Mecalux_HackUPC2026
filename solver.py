"""
Warehouse Bay Placement Solver — HackUPC 2026 - Mecalux Challenge
"""

import math
from shapely.geometry import Polygon, box
from shapely.prepared import prep
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
        """
        Heuristic ordering aligned with the official Q formula.

        Lower is better:
        - price / loads penalizes expensive bays with low capacity.
        - area / warehouse_area rewards larger area usage.
        """
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
        return (
            px * cos_a - py * sin_a + x,
            px * sin_a + py * cos_a + y,
        )

    footprint = Polygon([
        rot(0, 0),
        rot(w, 0),
        rot(w, d),
        rot(0, d),
    ])

    gap_poly = (
        Polygon([
            rot(0, d),
            rot(w, d),
            rot(w, d + gap),
            rot(0, d + gap),
        ])
        if gap > 0
        else Polygon()
    )

    return footprint, gap_poly


def get_ceiling_at(x, ceiling):
    if not ceiling:
        return float("inf")

    if x <= ceiling[0][0]:
        return ceiling[0][1]

    if x >= ceiling[-1][0]:
        return ceiling[-1][1]

    for i in range(len(ceiling) - 1):
        x0, h0 = ceiling[i]
        x1, h1 = ceiling[i + 1]

        if x0 <= x <= x1:
            return h0 + (x - x0) / (x1 - x0) * (h1 - h0)

    return ceiling[-1][1]


def min_ceiling_over_bounds(minx, maxx, ceiling, steps=10):
    if not ceiling:
        return float("inf")

    return min(
        get_ceiling_at(minx + (maxx - minx) * i / steps, ceiling)
        for i in range(steps + 1)
    )


def bounds_overlap(a, b):
    return not (
        a[2] <= b[0]
        or b[2] <= a[0]
        or a[3] <= b[1]
        or b[3] <= a[1]
    )


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
        self.prepared = prep(self.polygon)
        self.wh_area = self.polygon.area

        self.obstacles = obstacles
        self.obstacle_polys = [
            box(o[0], o[1], o[0] + o[2], o[1] + o[3])
            for o in obstacles
        ]
        self.obstacle_bounds = [p.bounds for p in self.obstacle_polys]

        self.ceiling = sorted(ceiling, key=lambda c: c[0])

        self.bay_types = [
            BayType(
                id=int(b[0]),
                w=b[1],
                d=b[2],
                h=b[3],
                gap=b[4],
                n_loads=int(b[5]),
                price=b[6],
            )
            for b in bay_types
        ]

        bds = self.polygon.bounds
        self.min_x, self.min_y, self.max_x, self.max_y = bds

    def can_place(self, x, y, bt, angle, placed):
        fp, gp = make_bay_polygons(x, y, bt.w, bt.d, bt.gap, angle)
        fp_b = fp.bounds

        # Bay footprint must be inside warehouse
        if not self.prepared.contains(fp):
            return None

        # Ceiling check
        if min_ceiling_over_bounds(fp_b[0], fp_b[2], self.ceiling) < bt.h:
            return None

        # Bay footprint vs obstacles
        for poly, bds in zip(self.obstacle_polys, self.obstacle_bounds):
            if real_overlap(fp, poly, fp_b, bds):
                return None

        # Bay footprint vs placed bays and placed gaps
        for p in placed:
            if real_overlap(fp, p.footprint, fp_b, p.fp_bounds):
                return None

            if p.gap_poly and not p.gap_poly.is_empty:
                if real_overlap(fp, p.gap_poly, fp_b, p.gap_poly.bounds):
                    return None

        # Gap validation
        if bt.gap > 0 and not gp.is_empty:
            gp_b = gp.bounds

            # Gap must also be inside warehouse
            if not self.prepared.contains(gp):
                return None

            # Gap vs obstacles
            for poly, bds in zip(self.obstacle_polys, self.obstacle_bounds):
                if real_overlap(gp, poly, gp_b, bds):
                    return None

            # Gap cannot overlap bay footprints
            # Gaps can overlap other gaps.
            for p in placed:
                if real_overlap(gp, p.footprint, gp_b, p.fp_bounds):
                    return None

        return fp, gp

    def _do_place(self, x, y, bt, angle, placed):
        result = self.can_place(x, y, bt, angle, placed)

        if result:
            fp, gp = result

            placed.append(
                PlacedBay(
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
            )

            return True

        return False

    def compute_score(self, placed):
        """
        Official quality function from the slides:

        Q = (sum(price / loads)) ^ (2 - sum(area_bay) / area_warehouse)

        Lower Q is better.
        """
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

        sum_price_loads = sum(b.price / b.n_loads for b in placed)
        sum_area = sum(b.area for b in placed)

        exponent = 2 - (sum_area / self.wh_area)
        score = sum_price_loads ** exponent

        return {
            "score": score,
            "totalBays": len(placed),
            "totalLoads": sum(b.n_loads for b in placed),
            "totalArea": sum_area,
            "warehouseArea": self.wh_area,
            "areaUsage": sum_area / self.wh_area * 100,
            "totalCost": sum(b.price for b in placed),
        }

    def solve(self, time_limit=25.0, extra_angles=None):
        start = time.time()

        all_angles = [0.0, 90.0, 180.0, 270.0] + (extra_angles or [])

        sorted_types = sorted(
            self.bay_types,
            key=lambda b: b.efficiency(self.wh_area),
        )

        candidates = [
            (bt, ang)
            for bt in sorted_types
            for ang in all_angles
        ]

        placed = []

        min_dim = min(min(bt.w, bt.d) for bt in self.bay_types)

        # PASS 1: Strip packing
        step = max(50.0, min_dim / 2)

        y = self.min_y
        while y < self.max_y and time.time() - start < time_limit * 0.35:
            x = self.min_x

            while x < self.max_x:
                ok = False

                for bt, ang in candidates:
                    if self._do_place(x, y, bt, ang, placed):
                        x = placed[-1].fp_bounds[2]
                        ok = True
                        break

                if not ok:
                    x += step

            y += step

        # PASS 2: Gap filling
        step2 = max(25.0, min_dim / 4)

        for bt, ang in candidates:
            if time.time() - start > time_limit * 0.65:
                break

            y = self.min_y

            while y < self.max_y:
                x = self.min_x

                while x < self.max_x:
                    self._do_place(x, y, bt, ang, placed)
                    x += step2

                y += step2

        # PASS 3: Edge-snapping
        if time.time() - start < time_limit * 0.85:
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

            for bt, ang in candidates:
                if time.time() - start > time_limit * 0.95:
                    break

                for y in sorted(ys):
                    for x in sorted(xs):
                        self._do_place(x, y, bt, ang, placed)

        stats = self.compute_score(placed)
        stats["solveTime"] = round(time.time() - start, 3)

        return placed, stats


def parse_warehouse(text):
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.startswith("#")
    ]


def parse_obstacles(text):
    # Empty obstacles.csv means there are no obstacles.
    if not text.strip():
        return []

    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.startswith("#")
    ]


def parse_ceiling(text):
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.startswith("#")
    ]


def parse_bays(text):
    return [
        tuple(map(float, l.split(",")))
        for l in text.strip().splitlines()
        if l.strip() and not l.startswith("#")
    ]