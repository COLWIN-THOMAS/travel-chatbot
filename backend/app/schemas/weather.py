from typing import List, Optional
from pydantic import BaseModel


class DayForecast(BaseModel):
    day_number: int
    date: str
    temp_max: float
    temp_min: float
    condition: str
    icon: str
    precipitation_probability: int
    advisory: str


class WeatherResponse(BaseModel):
    destination: str
    days: List[DayForecast] = []
    note: Optional[str] = None  # e.g. why some trip days have no forecast yet
