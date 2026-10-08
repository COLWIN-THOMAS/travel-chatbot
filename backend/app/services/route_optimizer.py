"""Geography-aware itinerary shaping: cluster places into days, order each day's stops to cut
backtracking, and pick which candidates fit a day's budget. Pure algorithms, no network calls, so
every function here is fully testable on synthetic coordinates - this is the "Route Optimizer"
component: clustering + routing + budget-constrained selection, independent of the LLM planner.

Coordinates are plain (lat, lon) floats in degrees (WGS84, what Google Places returns).
"""
import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

EARTH_RADIUS_KM = 6371.0088


@dataclass
class Place:
    name: str
    lat: float
    lon: float
    cost: float = 0.0
    category: str = "attraction"
    tags: Sequence[str] = field(default_factory=tuple)  # interest tags this place satisfies, e.g. ("food", "culture")


def haversine_km(a: Place, b: Place) -> float:
    """Great-circle distance between two points, in kilometres."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def route_distance_km(route: Sequence[Place]) -> float:
    """Total distance of visiting `route` in the given order (no return leg)."""
    return sum(haversine_km(route[i], route[i + 1]) for i in range(len(route) - 1))


# ---------------------------------------------------------------------------
# Clustering: split N places into `days` geographically coherent groups.
# ---------------------------------------------------------------------------

def _centroid(points: Sequence[Place]) -> tuple:
    return (sum(p.lat for p in points) / len(points), sum(p.lon for p in points) / len(points))


def cluster_into_days(places: Sequence[Place], days: int, seed: int = 0) -> List[List[Place]]:
    """K-means (by haversine distance) grouping `places` into `days` clusters, balanced so no
    cluster is left empty and no cluster absorbs everything. Deterministic for a given `seed`.
    `days` is clamped to `[1, len(places)]`."""
    places = list(places)
    if not places:
        return [[] for _ in range(max(days, 1))]
    k = max(1, min(days, len(places)))
    if k == 1:
        return [places]

    # Deterministic seed: evenly spaced points along the list sorted by longitude then latitude,
    # so the initial centroids are already spread out geographically rather than clustered together.
    ordered = sorted(places, key=lambda p: (p.lon, p.lat))
    step = len(ordered) / k
    centroids = [_centroid([ordered[min(int(i * step), len(ordered) - 1)]]) for i in range(k)]

    assignment = [0] * len(places)
    for _ in range(50):
        changed = False
        for i, p in enumerate(places):
            dists = [haversine_km(p, Place("c", c[0], c[1])) for c in centroids]
            best = min(range(k), key=lambda j: dists[j])
            if assignment[i] != best:
                assignment[i] = best
                changed = True
        clusters: List[List[Place]] = [[] for _ in range(k)]
        for i, p in enumerate(places):
            clusters[assignment[i]].append(p)
        # Re-seed any empty cluster from the largest cluster's farthest-from-centroid point,
        # so no group silently vanishes.
        for j, c in enumerate(clusters):
            if not c:
                donor = max(range(k), key=lambda x: len(clusters[x]))
                if len(clusters[donor]) > 1:
                    dc = _centroid(clusters[donor])
                    far = max(clusters[donor], key=lambda p: haversine_km(p, Place("c", *dc)))
                    clusters[donor].remove(far)
                    clusters[j].append(far)
                    idx = places.index(far)
                    assignment[idx] = j
                    changed = True
        centroids = [_centroid(c) if c else centroids[j] for j, c in enumerate(clusters)]
        if not changed:
            break

    clusters = [[] for _ in range(k)]
    for i, p in enumerate(places):
        clusters[assignment[i]].append(p)
    return clusters


# ---------------------------------------------------------------------------
# Ordering: nearest-neighbour construction + 2-opt local search (fine for the
# 4-8 stops a single day realistically has).
# ---------------------------------------------------------------------------

def order_day(places: Sequence[Place], start: Optional[Place] = None) -> List[Place]:
    """Order a day's stops to minimise total travel distance. If `start` is given (e.g. the
    hotel), the route begins there; `start` is excluded from the returned order unless it is
    also in `places`."""
    remaining = list(places)
    if not remaining:
        return []
    if len(remaining) == 1:
        return remaining

    if start is None:
        current = remaining.pop(0)
        route: List[Place] = [current]
    else:
        current = start
        route = []
    while remaining:
        nxt = min(remaining, key=lambda p: haversine_km(current, p))
        route.append(nxt)
        remaining.remove(nxt)
        current = nxt

    return _two_opt(route)


def _two_opt(route: List[Place]) -> List[Place]:
    improved = True
    while improved and len(route) > 3:
        improved = False
        for i in range(len(route) - 2):
            for j in range(i + 2, len(route)):
                if i == 0 and j == len(route) - 1:
                    continue
                a, b, c, d = route[i], route[i + 1], route[j], route[(j + 1) % len(route)] if j + 1 < len(route) else None
                before = haversine_km(a, b) + (haversine_km(c, d) if d else 0)
                after = haversine_km(a, c) + (haversine_km(b, d) if d else 0)
                if after < before - 1e-9:
                    route[i + 1:j + 1] = reversed(route[i + 1:j + 1])
                    improved = True
    return route


# ---------------------------------------------------------------------------
# Budget-constrained selection: pick which candidates to keep for a day,
# maximising interest-match within a cost cap (0/1 knapsack).
# ---------------------------------------------------------------------------

def interest_score(place: Place, preferences: Sequence[str]) -> float:
    if not preferences:
        return 1.0
    hits = len(set(t.lower() for t in place.tags) & set(p.lower() for p in preferences))
    return 1.0 + hits  # every place scores at least 1 so budget still gets spent on plain picks


def fit_budget(candidates: Sequence[Place], day_budget: float, preferences: Sequence[str] = (), must_keep: Sequence[Place] = ()) -> List[Place]:
    """0/1 knapsack over `candidates` maximising total interest_score subject to `day_budget`.
    `must_keep` items (e.g. the night's hotel) are always included and their cost is deducted
    from the budget first; raises ValueError if must_keep alone exceeds the budget."""
    must_keep = list(must_keep)
    reserved = sum(p.cost for p in must_keep)
    if reserved > day_budget + 1e-9:
        raise ValueError("must_keep items ({:.2f}) already exceed the day budget ({:.2f})".format(reserved, day_budget))
    budget_left = day_budget - reserved

    pool = [p for p in candidates if p not in must_keep]
    # Cents-granularity knapsack (costs are rupees with up to 2 decimals); cap the table size.
    scale = 100
    cap = min(int(round(budget_left * scale)), 2_000_000)
    weights = [max(0, int(round(p.cost * scale))) for p in pool]
    values = [interest_score(p, preferences) for p in pool]

    n = len(pool)
    # dp[w] = best value achievable with total weight <= w, using items seen so far
    dp = [0.0] * (cap + 1)
    choice = [[False] * (cap + 1) for _ in range(n)]
    for i in range(n):
        w_i, v_i = weights[i], values[i]
        for w in range(cap, w_i - 1, -1):
            candidate_value = dp[w - w_i] + v_i
            if candidate_value > dp[w] + 1e-9:
                dp[w] = candidate_value
                choice[i][w] = True
        # propagate the "not taken" dp values for w < w_i already in place (dp unchanged)

    # Reconstruct selection from the choice table.
    selected = []
    w = cap
    for i in range(n - 1, -1, -1):
        if choice[i][w]:
            selected.append(pool[i])
            w -= weights[i]
    return must_keep + list(reversed(selected))
