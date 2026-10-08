from fastapi import APIRouter, Depends

from app.deps import get_owned_trip
from app.models.trip import Trip
from app.schemas.weather import WeatherResponse
from app.services import weather

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/{trip_id}", response_model=WeatherResponse)
def trip_weather(trip: Trip = Depends(get_owned_trip)):
    """Forecast for the trip's days at the destination, matched by calendar date (trips without dates: Day k = today + k-1)."""
    return weather.forecast_for(trip.destination, trip.days_count, start_date=trip.start_date)
