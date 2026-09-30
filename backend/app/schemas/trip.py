import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.day import DayResponse


def clean_preferences(values: Optional[List[str]]) -> List[str]:
    seen, out = set(), []
    for v in values or []:
        v = v.strip().lower()[:30]
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out[:8]


class TripCreate(BaseModel):
    destination: str = Field(min_length=2, max_length=100)
    budget_total: float = Field(gt=0)
    days_count: int = Field(ge=1, le=14)
    preferences: List[str] = []

    @field_validator("destination")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("preferences")
    @classmethod
    def _prefs(cls, v: List[str]) -> List[str]:
        return clean_preferences(v)


class TripResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    destination: str
    budget_total: float
    days_count: int
    preferences: Optional[List[str]] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TripDetailResponse(TripResponse):
    days: List[DayResponse] = []
