import uuid
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
from app.schemas.day import DayResponse
from app.services import dates


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
    start_date: Optional[date] = None

    @field_validator("start_date")
    @classmethod
    def _start_ok(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            problem = dates.check_edit_date(v)
            if problem:
                raise ValueError(problem)
        return v

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
    start_date: Optional[date] = None
    preferences: Optional[List[str]] = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def end_date(self) -> Optional[date]:
        return dates.end_date(self.start_date, self.days_count)

    @computed_field
    @property
    def phase(self) -> str:
        """undated | upcoming | ongoing | completed"""
        return dates.phase(self.start_date, self.days_count)


class TripSummary(TripResponse):
    """A trip as shown in the history list: dates plus how it actually went."""
    estimated_total: float = 0.0
    spend_total: float = 0.0
    items_total: int = 0
    items_visited: int = 0


class TripDatesUpdate(BaseModel):
    start_date: Optional[date] = None  # null clears the dates

    @field_validator("start_date")
    @classmethod
    def _start_ok(cls, v: Optional[date]) -> Optional[date]:
        if v is not None:
            problem = dates.check_edit_date(v)
            if problem:
                raise ValueError(problem)
        return v


class TripDetailResponse(TripResponse):
    days: List[DayResponse] = []
