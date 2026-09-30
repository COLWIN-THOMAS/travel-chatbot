from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_owned_trip
from app.models.trip import Trip
from app.schemas.itinerary import ItineraryResponse, RegenerateRequest
from app.schemas.trip import clean_preferences
from app.services import planner
from app.services.itinerary_view import load_days

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.get("/{trip_id}", response_model=ItineraryResponse)
def get_itinerary(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    return {"days": load_days(db, trip.id)}


@router.post("/{trip_id}/regenerate", response_model=ItineraryResponse)
def regenerate(payload: RegenerateRequest, trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    """Rebuilds the whole itinerary. Visited flags reset; expenses stay but are unlinked from removed items."""
    ch = payload.changes
    slots = {
        "destination": trip.destination,
        "budget_total": ch.budget_total or float(trip.budget_total),
        "days_count": ch.days_count or trip.days_count,
        "preferences": clean_preferences(ch.preferences) if ch.preferences is not None else (trip.preferences or []),
        "instructions": ch.instructions,
    }
    try:
        plan = planner.create_plan(slots)
    except planner.PlanError as e:
        raise HTTPException(status_code=422, detail="Could not build a plan within those limits: {}".format(e))

    trip.budget_total, trip.days_count, trip.preferences = slots["budget_total"], slots["days_count"], slots["preferences"]
    planner.save_plan(db, trip, plan)
    db.commit()
    return {"days": load_days(db, trip.id)}
