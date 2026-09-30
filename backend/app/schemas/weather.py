from typing import List
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
