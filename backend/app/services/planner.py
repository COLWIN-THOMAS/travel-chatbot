"""Itinerary generation: real place candidates -> structured LLM plan -> validated -> persisted."""
import json
import logging
import uuid
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import config
from app.models.day import Day
from app.models.itinerary_item import ItineraryItem
from app.models.trip import Trip
from app.services import google_places, llm

log = logging.getLogger(__name__)


class PlanError(Exception):
    """The planner could not produce a valid plan for these constraints."""


class PlannedItem(BaseModel):
    place_name: str
    category: Literal["hotel", "restaurant", "attraction", "transport"]
    estimated_cost: float
    notes: Optional[str] = None


class PlannedDay(BaseModel):
    day_number: int
    items: List[PlannedItem]


class ItineraryPlan(BaseModel):
    days: List[PlannedDay]


PLANNER_SYSTEM = """You are an expert budget travel planner for India. Build a realistic day-by-day itinerary.

Hard constraints:
- Exactly {days} days, numbered 1..{days}.
- The SUM of every item's estimated_cost across the whole trip must be at most {budget} rupees. Aim for 85-95% of the budget and never exceed it.
- Costs are in Indian rupees for ONE traveller.
- Each day has 4-7 items in chronological order: breakfast, lunch and dinner as category "restaurant"; sightseeing as "attraction"; local getting around as "transport"; and a place to sleep as "hotel" (the nightly rate) on every day EXCEPT the last day.
- Prefer real places from the candidate lists; you may add other well-known real places. Use realistic prices; free attractions cost 0.
- Tailor the plan to the traveller's preferences and keep each day geographically sensible.
- notes: at most one short practical tip per item, or null."""


def gather_candidates(destination: str, per_category: int = 8) -> str:
    lines: List[str] = []
    for category in ("hotel", "restaurant", "attraction"):
        try:
            places = google_places.search_places(destination, category)
        except google_places.PlacesError as e:
            log.warning("candidate search failed for %s: %s", category, e)
            continue
        ranked = sorted(places, key=lambda p: p.get("rating") or 0, reverse=True)[:per_category]
        if not ranked:
            continue
        lines.append("{}:".format(category.upper()))
        for p in ranked:
            price = (p.get("priceLevel") or "").replace("PRICE_LEVEL_", "").title() or "n/a"
            lines.append(
                "- {} (rating {}, price {})".format(
                    p.get("displayName", {}).get("text", "?"), p.get("rating", "n/a"), price
                )
            )
    return "\n".join(lines) if lines else "(no candidate list available; use your own knowledge)"


def plan_total(plan: ItineraryPlan) -> float:
    return sum(i.estimated_cost for d in plan.days for i in d.items)


def validate_plan(plan: ItineraryPlan, days_count: int, budget: float) -> List[str]:
    problems: List[str] = []
    numbers = sorted(d.day_number for d in plan.days)
    if numbers != list(range(1, days_count + 1)):
        problems.append("The plan must contain exactly days 1..{} once each.".format(days_count))
    for d in plan.days:
        if not d.items:
            problems.append("Day {} has no items.".format(d.day_number))
    if any(i.estimated_cost < 0 for d in plan.days for i in d.items):
        problems.append("Costs cannot be negative.")
    total = plan_total(plan)
    if total > budget:
        problems.append(
            "The plan totals {:.0f} rupees which exceeds the {:.0f} rupee budget. Reduce costs (cheaper stays and meals).".format(
                total, budget
            )
        )
    return problems


def _request_plan(slots: dict, candidates: str, feedback: Optional[str]) -> ItineraryPlan:
    client = llm.get_client()
    user = "<trip>{}</trip>\n<candidates>\n{}\n</candidates>".format(
        json.dumps(
            {
                "destination": slots["destination"],
                "budget_total": slots["budget_total"],
                "days_count": slots["days_count"],
                "preferences": slots.get("preferences") or [],
                "extra_instructions": llm.wrap_user_text(slots.get("instructions") or ""),
            },
            ensure_ascii=False,
        ),
        candidates,
    )
    if feedback:
        user += "\n<feedback>{}</feedback>".format(feedback)

    kwargs = {}
    if "haiku" not in config.PLANNER_MODEL:
        kwargs["output_config"] = {"effort": "medium"}

    resp = llm.call_api(
        lambda: client.messages.parse(
            model=config.PLANNER_MODEL,
            max_tokens=12000,
            system=PLANNER_SYSTEM.format(days=slots["days_count"], budget="{:.0f}".format(slots["budget_total"])),
            messages=[{"role": "user", "content": user}],
            output_format=ItineraryPlan,
            **kwargs
        )
    )
    if resp.parsed_output is None:
        raise PlanError("The planner returned no usable plan")
    return resp.parsed_output


def create_plan(slots: dict, attempts: int = 2) -> ItineraryPlan:
    """Generate and validate a plan; retry once with concrete feedback if it breaks a constraint."""
    candidates = gather_candidates(slots["destination"])
    feedback = None
    problems: List[str] = []
    for _ in range(attempts):
        plan = _request_plan(slots, candidates, feedback)
        problems = validate_plan(plan, slots["days_count"], slots["budget_total"])
        if not problems:
            return plan
        feedback = " ".join(problems)
    raise PlanError(" ".join(problems))


def save_plan(db: Session, trip: Trip, plan: ItineraryPlan) -> None:
    """Replace the trip's itinerary with `plan`. Caller commits."""
    for day in db.query(Day).filter(Day.trip_id == trip.id).all():
        db.delete(day)
    db.flush()
    for d in sorted(plan.days, key=lambda x: x.day_number):
        day = Day(id=uuid.uuid4(), trip_id=trip.id, day_number=d.day_number)
        db.add(day)
        db.flush()
        for order, item in enumerate(d.items, start=1):
            db.add(
                ItineraryItem(
                    id=uuid.uuid4(),
                    day_id=day.id,
                    place_name=item.place_name.strip()[:200],
                    category=item.category,
                    estimated_cost=max(item.estimated_cost, 0),
                    order_in_day=order,
                    notes=(item.notes or None) and item.notes.strip()[:300],
                )
            )
    trip.status = "active"
