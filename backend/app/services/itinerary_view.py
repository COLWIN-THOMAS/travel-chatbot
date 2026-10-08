"""Read-side helpers: build nested day/item views with derived spend in a constant number of queries."""
import uuid
from typing import Dict, List

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.day import Day
from app.models.expense import Expense
from app.models.itinerary_item import ItineraryItem


def load_days(db: Session, trip_id: uuid.UUID) -> List[dict]:
    days = db.query(Day).filter(Day.trip_id == trip_id).order_by(Day.day_number).all()
    if not days:
        return []

    day_ids = [d.id for d in days]
    items = (
        db.query(ItineraryItem)
        .filter(ItineraryItem.day_id.in_(day_ids))
        .order_by(ItineraryItem.order_in_day)
        .all()
    )

    spent: Dict[uuid.UUID, float] = {}
    if items:
        rows = (
            db.query(Expense.itinerary_item_id, func.sum(Expense.amount))
            .filter(Expense.itinerary_item_id.in_([i.id for i in items]))
            .group_by(Expense.itinerary_item_id)
            .all()
        )
        spent = {item_id: float(total) for item_id, total in rows}

    by_day: Dict[uuid.UUID, List[dict]] = {d.id: [] for d in days}
    for i in items:
        by_day[i.day_id].append(
            {
                "id": i.id,
                "place_name": i.place_name,
                "category": i.category,
                "estimated_cost": float(i.estimated_cost),
                "actual_cost": spent.get(i.id, 0.0),
                "visited": i.visited,
                "order_in_day": i.order_in_day,
                "notes": i.notes,
            }
        )

    return [
        {
            "id": d.id,
            "day_number": d.day_number,
            "date": d.date,
            "estimated_total": sum(x["estimated_cost"] for x in by_day[d.id]),
            "spend_so_far": sum(x["actual_cost"] for x in by_day[d.id]),
            "items": by_day[d.id],
        }
        for d in days
    ]


def spend_total(db: Session, trip_id: uuid.UUID) -> float:
    total = db.query(func.sum(Expense.amount)).filter(Expense.trip_id == trip_id).scalar()
    return float(total or 0)


def trip_stats(db: Session, trip_ids: List[uuid.UUID]) -> Dict[uuid.UUID, dict]:
    """Per-trip planned total, actual spend and visited progress for many trips in three queries."""
    stats = {tid: {"estimated_total": 0.0, "spend_total": 0.0, "items_total": 0, "items_visited": 0} for tid in trip_ids}
    if not trip_ids:
        return stats

    item_rows = (
        db.query(
            Day.trip_id,
            func.count(ItineraryItem.id),
            func.coalesce(func.sum(ItineraryItem.estimated_cost), 0),
            func.coalesce(func.sum(case((ItineraryItem.visited.is_(True), 1), else_=0)), 0),
        )
        .join(ItineraryItem, ItineraryItem.day_id == Day.id)
        .filter(Day.trip_id.in_(trip_ids))
        .group_by(Day.trip_id)
        .all()
    )
    for trip_id, count, estimated, visited in item_rows:
        stats[trip_id].update(items_total=int(count), estimated_total=float(estimated), items_visited=int(visited))

    spend_rows = (
        db.query(Expense.trip_id, func.sum(Expense.amount))
        .filter(Expense.trip_id.in_(trip_ids))
        .group_by(Expense.trip_id)
        .all()
    )
    for trip_id, total in spend_rows:
        stats[trip_id]["spend_total"] = float(total or 0)
    return stats
