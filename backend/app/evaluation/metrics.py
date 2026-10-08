"""Scoring functions for an itinerary plan: budget adherence, travel distance per day, and
how well the plan matches the traveller's stated interests. These operate on plain `Place`
objects (see `app.services.route_optimizer`) grouped by day, so they work equally on an
LLM-only plan or a route-optimizer-adjusted one - that's what makes the two comparable.
"""
from dataclasses import dataclass
from typing import Dict, List, Sequence

from app.services.route_optimizer import Place, interest_score, route_distance_km


@dataclass
class BudgetAdherence:
    total_cost: float
    budget: float
    overshoot: float  # positive = over budget, 0 if within
    within_budget: bool
    percent_used: float


def budget_adherence(days: Sequence[Sequence[Place]], budget_total: float) -> BudgetAdherence:
    total = sum(p.cost for day in days for p in day)
    overshoot = max(0.0, total - budget_total)
    return BudgetAdherence(
        total_cost=total, budget=budget_total, overshoot=overshoot,
        within_budget=overshoot == 0, percent_used=round(total / budget_total * 100, 1) if budget_total > 0 else 0.0,
    )


@dataclass
class DistanceMetrics:
    per_day_km: List[float]
    total_km: float
    average_per_day_km: float
    max_day_km: float


def distance_metrics(days: Sequence[Sequence[Place]]) -> DistanceMetrics:
    per_day = [round(route_distance_km(day), 2) for day in days]
    total = round(sum(per_day), 2)
    return DistanceMetrics(
        per_day_km=per_day, total_km=total,
        average_per_day_km=round(total / len(per_day), 2) if per_day else 0.0,
        max_day_km=max(per_day) if per_day else 0.0,
    )


@dataclass
class InterestMatch:
    average_score: float  # mean interest_score across all places (1.0 = no tag overlap on average)
    matched_fraction: float  # fraction of places with at least one matching tag


def interest_match(days: Sequence[Sequence[Place]], preferences: Sequence[str]) -> InterestMatch:
    places = [p for day in days for p in day]
    if not places:
        return InterestMatch(0.0, 0.0)
    scores = [interest_score(p, preferences) for p in places]
    matched = sum(1 for p in places if set(t.lower() for t in p.tags) & set(x.lower() for x in preferences))
    return InterestMatch(
        average_score=round(sum(scores) / len(scores), 3),
        matched_fraction=round(matched / len(places), 3),
    )


@dataclass
class PlanScore:
    label: str
    budget: BudgetAdherence
    distance: DistanceMetrics
    interests: InterestMatch
    items_count: int

    def as_row(self) -> Dict[str, object]:
        return {
            "plan": self.label,
            "items": self.items_count,
            "cost_total": self.budget.total_cost,
            "budget_used_pct": self.budget.percent_used,
            "over_budget_by": self.budget.overshoot,
            "avg_km_per_day": self.distance.average_per_day_km,
            "max_km_in_a_day": self.distance.max_day_km,
            "interest_match_pct": round(self.interests.matched_fraction * 100, 1),
        }


def score_plan(label: str, days: Sequence[Sequence[Place]], budget_total: float, preferences: Sequence[str]) -> PlanScore:
    return PlanScore(
        label=label,
        budget=budget_adherence(days, budget_total),
        distance=distance_metrics(days),
        interests=interest_match(days, preferences),
        items_count=sum(len(d) for d in days),
    )
