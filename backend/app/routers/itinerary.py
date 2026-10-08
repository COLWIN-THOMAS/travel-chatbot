from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_owned_trip
from app.models.trip import Trip
from app.schemas.itinerary import ItineraryResponse, RegenerateRequest
from app.services import planner, replan
from app.services.itinerary_view import load_days

router = APIRouter(prefix="/itinerary", tags=["itinerary"])


@router.get("/{trip_id}", response_model=ItineraryResponse)
def get_itinerary(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    return {"days": load_days(db, trip.id)}


@router.post("/{trip_id}/regenerate", response_model=ItineraryResponse)
def regenerate(payload: RegenerateRequest, trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    """Rebuilds the itinerary. If some days have already started (ticked visited, or their date has passed) those
    days are kept exactly as they are and only the days after them are rebuilt, from the budget that is left."""
    ch = payload.changes
    try:
        replan.apply_changes(
            db, trip,
            budget_total=ch.budget_total, days_count=ch.days_count,
            preferences=ch.preferences, instructions=ch.instructions,
        )
    except planner.PlanError as e:
        raise HTTPException(status_code=422, detail="Could not build a plan within those limits: {}".format(e))
    db.commit()
    return {"days": load_days(db, trip.id)}
