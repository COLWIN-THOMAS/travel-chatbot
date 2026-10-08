"""User-requested replans (Adjust plan screen, "change my plan" in chat) that never rewrite finished days.

If nothing has started yet this is a full rebuild, exactly as before. Once some days have started (a place
ticked visited, or the day's calendar date has passed) those days are frozen: only the days after them are
regenerated, against the budget that is actually left and the number of days that are actually left.
"""
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.trip import Trip
from app.schemas.trip import clean_preferences
from app.services import dates, planner
from app.services.itinerary_view import spend_total
from app.services.rebalance import MIN_REPLAN_BUDGET, started_through


class ReplanResult(BaseModel):
    plan_total: float
    budget_total: float
    locked_days: int  # days 1..locked_days were left untouched


def apply_changes(
    db: Session,
    trip: Trip,
    budget_total: Optional[float] = None,
    days_count: Optional[int] = None,
    preferences: Optional[List[str]] = None,
    instructions: Optional[str] = None,
) -> ReplanResult:
    """Plans first, then writes; raises planner.PlanError / llm.LLMUnavailable before anything is modified.
    Caller commits."""
    new_budget = budget_total or float(trip.budget_total)
    new_days = days_count or trip.days_count
    new_prefs = clean_preferences(preferences) if preferences is not None else (trip.preferences or [])
    locked = started_through(db, trip)

    slots = {
        "destination": trip.destination,
        "budget_total": new_budget,
        "days_count": new_days,
        "preferences": new_prefs,
        "instructions": instructions,
        "start_date": trip.start_date.isoformat() if trip.start_date else None,
    }

    if locked == 0:
        plan = planner.create_plan(slots)
        trip.budget_total, trip.days_count, trip.preferences = new_budget, new_days, new_prefs
        planner.save_plan(db, trip, plan)
        db.flush()
        return ReplanResult(plan_total=planner.plan_total(plan), budget_total=new_budget, locked_days=0)

    remaining_days = new_days - locked
    if remaining_days < 1:
        raise planner.PlanError(
            "The first {} day(s) have already started, so the trip can't be shorter than that. "
            "Choose at least {} days.".format(locked, locked + 1)
        )
    left = new_budget - spend_total(db, trip.id)
    slots["days_count"] = remaining_days
    slots["budget_total"] = max(left, MIN_REPLAN_BUDGET)
    slots["start_date"] = dates.day_date(trip.start_date, locked + 1).isoformat() if trip.start_date else None
    plan = planner.create_plan(slots)

    trip.budget_total, trip.days_count, trip.preferences = new_budget, new_days, new_prefs
    planner.replace_days_from(db, trip, plan, from_day_number=locked + 1)
    db.flush()
    return ReplanResult(plan_total=planner.plan_total(plan), budget_total=new_budget, locked_days=locked)
