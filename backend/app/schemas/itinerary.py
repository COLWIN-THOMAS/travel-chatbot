from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.day import DayResponse


class ItineraryResponse(BaseModel):
    days: List[DayResponse] = []


class RegenerateChanges(BaseModel):
    budget_total: Optional[float] = Field(default=None, gt=0)
    days_count: Optional[int] = Field(default=None, ge=1, le=14)
    preferences: Optional[List[str]] = None
    instructions: Optional[str] = Field(default=None, max_length=500)


class RegenerateRequest(BaseModel):
    changes: RegenerateChanges = RegenerateChanges()
