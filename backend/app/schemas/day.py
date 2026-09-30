import uuid
from datetime import date as date_type
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.itinerary_item import ItineraryItemResponse


class DayResponse(BaseModel):
    id: uuid.UUID
    day_number: int
    date: Optional[date_type] = None
    estimated_total: float = 0.0
    spend_so_far: float = 0.0  # derived from expenses linked to this day's items
    items: List[ItineraryItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
