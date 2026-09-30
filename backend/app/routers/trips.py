import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_owned_trip
from app.models.trip import Trip
from app.models.user import User
from app.schemas.trip import TripCreate, TripDetailResponse, TripResponse
from app.services.itinerary_view import load_days

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("", response_model=TripResponse, status_code=201)
def create_trip(payload: TripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = Trip(user_id=user.id, **payload.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("", response_model=List[TripResponse])
def list_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Trip).filter(Trip.user_id == user.id).order_by(Trip.created_at.desc()).all()


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    data = TripResponse.model_validate(trip).model_dump()
    data["days"] = load_days(db, trip.id)
    return data


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    db.delete(trip)
    db.commit()
