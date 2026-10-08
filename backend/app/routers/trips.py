import uuid
import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_owned_trip
from app.models.trip import Trip
from app.models.user import User
from app.models.day import Day
from app.schemas.trip import TripCreate, TripDatesUpdate, TripDetailResponse, TripResponse, TripSummary
from app.services import dates, deep_links
from app.services.itinerary_view import load_days, trip_stats

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post("", response_model=TripResponse, status_code=201)
def create_trip(payload: TripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = Trip(user_id=user.id, **payload.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("", response_model=List[TripSummary])
def list_trips(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every trip the user has made with the app (their history), newest first, with how each one went."""
    trips = db.query(Trip).filter(Trip.user_id == user.id).order_by(Trip.created_at.desc()).all()
    stats = trip_stats(db, [t.id for t in trips])
    out = []
    for t in trips:
        data = TripResponse.model_validate(t).model_dump()
        data.update(stats[t.id])
        out.append(data)
    return out


@router.get("/{trip_id}", response_model=TripDetailResponse)
def get_trip(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    data = TripResponse.model_validate(trip).model_dump()
    data["days"] = load_days(db, trip.id)
    return data


@router.put("/{trip_id}/dates", response_model=TripResponse)
def set_trip_dates(payload: TripDatesUpdate, trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    """Set (or clear) the start date; every day of the itinerary is re-dated to start_date + (day_number - 1)."""
    trip.start_date = payload.start_date
    for day in db.query(Day).filter(Day.trip_id == trip.id).all():
        day.date = dates.day_date(trip.start_date, day.day_number)
    db.commit()
    db.refresh(trip)
    return trip


@router.delete("/{trip_id}", status_code=204)
def delete_trip(trip: Trip = Depends(get_owned_trip), db: Session = Depends(get_db)):
    db.delete(trip)
    db.commit()


@router.get("/{trip_id}/links/hotels")
def hotel_search_link(trip: Trip = Depends(get_owned_trip)):
    """Booking.com search for this trip's destination, prefilled with dates if the trip has them."""
    checkin = trip.start_date or (dates.today_ist() + datetime.timedelta(days=30))
    checkout = dates.end_date(checkin, trip.days_count) or (checkin + datetime.timedelta(days=max(trip.days_count, 1)))
    return deep_links.booking_hotels(trip.destination, checkin.isoformat(), checkout.isoformat())


@router.get("/{trip_id}/links/trains")
def train_search_link(trip: Trip = Depends(get_owned_trip)):
    """No reliable public prefill exists for IRCTC (see app.services.deep_links) - this opens
    train search with nothing filled in; the user searches for `trip.destination` themselves."""
    return deep_links.irctc_train_search()
