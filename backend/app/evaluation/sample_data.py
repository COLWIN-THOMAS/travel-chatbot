"""Scripted sample plans for the evaluation harness. These are hand-built, not from a live LLM
call or live Places data, so results here demonstrate the SCORING and the route-optimizer's
effect on a plan - not real AI quality. Real AI numbers need a live run (see scripts/run_evaluation.py --live).
"""
import random
from typing import List

from app.services.route_optimizer import Place

# A fictional but realistic small-city layout: a cluster of beach-side spots and a cluster of
# old-town spots, ~6km apart, so clustering/ordering has something real to do.
BEACH = [
    Place("Beachfront Hostel", 15.300, 73.800, cost=900, category="hotel", tags=("beaches", "relaxed")),
    Place("Seafood Shack", 15.302, 73.802, cost=350, category="restaurant", tags=("food",)),
    Place("Sunset Point", 15.298, 73.799, cost=0, category="attraction", tags=("beaches", "relaxed")),
    Place("Water Sports Center", 15.303, 73.805, cost=600, category="attraction", tags=("adventure",)),
    Place("Beach Shack Bar", 15.301, 73.803, cost=400, category="restaurant", tags=("nightlife", "food")),
]
OLD_TOWN = [
    Place("Heritage Inn", 15.350, 73.850, cost=1100, category="hotel", tags=("culture", "relaxed")),
    Place("Old Fort", 15.352, 73.852, cost=50, category="attraction", tags=("culture", "history")),
    Place("Spice Market", 15.349, 73.849, cost=0, category="attraction", tags=("culture", "food")),
    Place("Thali House", 15.351, 73.851, cost=300, category="restaurant", tags=("food",)),
    Place("Rooftop Cafe", 15.353, 73.853, cost=450, category="restaurant", tags=("food", "nightlife")),
]

ALL_PLACES: List[Place] = BEACH + OLD_TOWN
TRIP_BUDGET = 8000.0
TRIP_DAYS = 2
PREFERENCES = ["food", "culture", "beaches"]


def baseline_plan(seed: int = 7) -> List[List[Place]]:
    """What an LLM-only plan commonly looks like: a reasonable grouping, but stops listed in
    whatever order the model wrote them, not geographically ordered, and not budget-checked
    against each individual day (only checked against the whole trip)."""
    rnd = random.Random(seed)
    shuffled = ALL_PLACES[:]
    rnd.shuffle(shuffled)
    mid = len(shuffled) // 2
    return [shuffled[:mid], shuffled[mid:]]


def optimized_plan(preferences=PREFERENCES, day_budget: float = TRIP_BUDGET / TRIP_DAYS) -> List[List[Place]]:
    """The same candidate pool run through the route optimizer: clustered geographically,
    budget-fit per day, and ordered to cut backtracking."""
    from app.services.route_optimizer import cluster_into_days, fit_budget, order_day

    clusters = cluster_into_days(ALL_PLACES, days=TRIP_DAYS)
    days = []
    for cluster in clusters:
        hotel = next((p for p in cluster if p.category == "hotel"), None)
        kept = fit_budget(cluster, day_budget=day_budget, preferences=preferences, must_keep=[hotel] if hotel else [])
        days.append(order_day(kept, start=hotel))
    return days
