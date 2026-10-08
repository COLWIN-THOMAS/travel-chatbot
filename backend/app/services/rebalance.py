"""Automatic mid-trip budget rebalancing.

The itinerary is generated once up front against the full budget. As the trip actually happens, real
spending can diverge from the estimate. After every action that could change that picture (logging an
expense, marking a place visited), we check: can the money that's left still cover the days that haven't
happened yet, as currently planned? If not, we regenerate ONLY the not-yet-started days against whatever
budget is actually left, and leave every already-started day completely untouched.

"Already started" is inferred, not tracked explicitly. A day counts as started once the user has ticked at
least one of its places visited, and - when the trip has real dates - also once its calendar date is in the
past (that day is over, whether or not anything was ticked). Today itself stays editable until something on
it is ticked. The first day that has not started, and every day after it, is "remaining" and eligible to be
rebuilt. If nothing has started yet, every day is still "remaining".
"""
import logging
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.day import Day
from app.models.itinerary_item import ItineraryItem
from app.models.trip import Trip
from app.services import dates, planner
from app.services.itinerary_view import spend_total

log = logging.getLogger(__name__)

# A replan is only worth doing if the shortfall is material - avoids rebuilding the
# remaining days over a shortfall of a few rupees from rounding.
MIN_SHORTFALL = 1.0
# The planner requires a positive budget; an exhausted or negative balance still gets this much
# to work with (realistically close to "free attractions only" for the remaining days).
MIN_REPLAN_BUDGET = 50.0


class RebalanceNotice(BaseModel):
    rebalanced: bool
    message: str
    days_from: Optional[int] = None
    days_to: Optional[int] = None


def started_through(db: Session, trip: Trip) -> int:
    """Highest day number that has started (0 = nothing has started). Those days are never rewritten."""
    visited = (
        db.query(func.max(Day.day_number))
        .join(ItineraryItem, ItineraryItem.day_id == Day.id)
        .filter(Day.trip_id == trip.id, ItineraryItem.visited.is_(True))
        .scalar()
    )
    last_day = db.query(func.max(Day.day_number)).filter(Day.trip_id == trip.id).scalar() or 0
    past = min(dates.days_elapsed(trip.start_date), int(last_day))
    return max(int(visited or 0), past)


def maybe_rebalance(db: Session, trip: Trip) -> Optional[RebalanceNotice]:
    """Checks feasibility and, if needed, rebuilds the remaining days in place. Does not commit -
    the caller's existing commit (for the expense/visit that triggered this) covers it too."""
    last_started = started_through(db, trip)
    remaining_days: List[Day] = (
        db.query(Day).filter(Day.trip_id == trip.id, Day.day_number > last_started).order_by(Day.day_number).all()
    )
    if not remaining_days:
        return None  # trip is finished or has no itinerary yet

    remaining_day_ids = [d.id for d in remaining_days]
    remaining_planned_cost = float(
        db.query(func.coalesce(func.sum(ItineraryItem.estimated_cost), 0))
        .filter(ItineraryItem.day_id.in_(remaining_day_ids))
        .scalar()
        or 0
    )
    remaining_actual_budget = float(trip.budget_total) - spend_total(db, trip.id)

    shortfall = remaining_planned_cost - remaining_actual_budget
    if shortfall <= MIN_SHORTFALL:
        return None  # what's left still covers the plan as it stands

    from_day = remaining_days[0].day_number
    to_day = remaining_days[-1].day_number
    target_budget = max(remaining_actual_budget, MIN_REPLAN_BUDGET)

    slots = {
        "destination": trip.destination,
        "budget_total": target_budget,
        "days_count": len(remaining_days),
        "preferences": trip.preferences or [],
        "start_date": (dates.day_date(trip.start_date, from_day).isoformat() if trip.start_date else None),
        "instructions": (
            "The traveller has overspent on earlier days of this same trip, so money for these remaining days "
            "is very tight. Prioritise free and low-cost options and keep quality reasonable."
        ),
    }

    try:
        plan = planner.create_plan(slots)
    except planner.PlanError:
        log.warning("rebalance: could not replan days %s-%s for trip %s within %.0f", from_day, to_day, trip.id, target_budget)
        return RebalanceNotice(
            rebalanced=False,
            message=(
                "Heads up: your remaining budget (₹{:.0f}) isn't enough to cover Days {}-{} as planned "
                "(est. ₹{:.0f}), and I couldn't find a cheaper plan that still works. You may want to add "
                "budget or adjust the plan yourself."
            ).format(remaining_actual_budget, from_day, to_day, remaining_planned_cost),
            days_from=from_day,
            days_to=to_day,
        )

    planner.replace_days_from(db, trip, plan, from_day_number=from_day)
    db.flush()
    new_total = planner.plan_total(plan)
    unchanged_note = " Days 1-{} are unchanged.".format(last_started) if last_started > 0 else ""
    return RebalanceNotice(
        rebalanced=True,
        message=(
            "Heads up: your remaining budget (₹{:.0f}) couldn't cover Days {}-{} as originally planned "
            "(est. ₹{:.0f}), so I've automatically updated those days to fit (new est. ₹{:.0f})."
        ).format(remaining_actual_budget, from_day, to_day, remaining_planned_cost, new_total)
        + unchanged_note,
        days_from=from_day,
        days_to=to_day,
    )
