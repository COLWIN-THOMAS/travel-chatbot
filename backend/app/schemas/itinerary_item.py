import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ItineraryItemResponse(BaseModel):
    id: uuid.UUID
    place_name: str
    category: str
    estimated_cost: float
    actual_cost: float = 0.0  # derived: SUM(expenses) linked to this item, never stored
    visited: bool
    order_in_day: int
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
