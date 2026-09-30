import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_owned_trip
from app.models.day import Day
from app.models.expense import Expense
from app.models.itinerary_item import ItineraryItem
from app.models.trip import Trip
from app.schemas.itinerary_item import ItineraryItemResponse
from app.schemas.tracker import (
    ExpenseCreate,
    ExpenseLogResponse,
    ExpenseOut,
    TrackerSummary,
    VisitUpdate,
)
from app.services.itinerary_view import spend_total

router = APIRouter(prefix="/tracker", tags=["tracker"])


def _trip_item(db: Session, trip_id: uuid.UUID, item_id: uuid.UUID):
    return (
        db.query(ItineraryItem)
        .join(Day, ItineraryItem.day_id == Day.id)
        .filter(ItineraryItem.id == item_id, Day.trip_id == trip_id)
        .first()
    )


def _item_view(db: Session, item: ItineraryItem) -> dict:
    actual = db.query(func.sum(Expense.amount)).filter(Expense.itinerary_item_id == item.id).scalar()
    return {
        "id": item.id,
        "place_name": item.place_name,
        "category": item.category,
        "estimated_cost": float(item.estimated_cost),
        "actual_cost": float(actual or 0),
        "visited": item.visited,
        "order_in_day": item.order_in_day,
        "notes": item.notes,
    }


@router.post("/{trip_id}/visit", response_model=ItineraryItemResponse)
def mark_visited(payload: VisitUpdate, trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    item = _trip_item(db, trip.id, payload.itinerary_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Itinerary item not found for this trip")
    item.visited = payload.visited
    db.commit()
    db.refresh(item)
    return _item_view(db, item)


@router.post("/{trip_id}/expense", response_model=ExpenseLogResponse, status_code=201)
def log_expense(payload: ExpenseCreate, trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    if payload.itinerary_item_id and not _trip_item(db, trip.id, payload.itinerary_item_id):
        raise HTTPException(status_code=404, detail="Itinerary item not found for this trip")

    expense = Expense(
        trip_id=trip.id,
        amount=payload.amount,
        category=payload.category,
        itinerary_item_id=payload.itinerary_item_id,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)

    total = spend_total(db, trip.id)
    return {"expense": expense, "spend_total": total, "budget_remaining": float(trip.budget_total) - total}


@router.get("/{trip_id}/expenses", response_model=List[ExpenseOut])
def list_expenses(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    return db.query(Expense).filter(Expense.trip_id == trip.id).order_by(Expense.logged_at.desc()).all()


@router.delete("/{trip_id}/expense/{expense_id}", status_code=204)
def delete_expense(expense_id: uuid.UUID, trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.trip_id == trip.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    db.delete(expense)
    db.commit()


@router.get("/{trip_id}", response_model=TrackerSummary)
def tracker_summary(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    total = spend_total(db, trip.id)
    budget = float(trip.budget_total)

    counts = (
        db.query(func.count(ItineraryItem.id), func.count(ItineraryItem.id).filter(ItineraryItem.visited.is_(True)))
        .join(Day, ItineraryItem.day_id == Day.id)
        .filter(Day.trip_id == trip.id)
        .one()
    )
    by_category = (
        db.query(func.coalesce(Expense.category, "other"), func.sum(Expense.amount))
        .filter(Expense.trip_id == trip.id)
        .group_by(func.coalesce(Expense.category, "other"))
        .all()
    )
    return {
        "spend_total": total,
        "budget_total": budget,
        "remaining": budget - total,
        "percent_used": round(total / budget * 100, 1) if budget > 0 else 0.0,
        "items_total": counts[0],
        "items_visited": counts[1],
        "spent_by_category": {cat: float(amt) for cat, amt in by_category},
    }
