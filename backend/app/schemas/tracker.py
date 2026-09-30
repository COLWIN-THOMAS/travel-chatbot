import uuid
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class VisitUpdate(BaseModel):
    itinerary_item_id: uuid.UUID
    visited: bool


class ExpenseCreate(BaseModel):
    amount: float = Field(gt=0)
    category: Optional[str] = Field(default=None, max_length=40)
    itinerary_item_id: Optional[uuid.UUID] = None


class ExpenseOut(BaseModel):
    id: uuid.UUID
    amount: float
    category: Optional[str] = None
    itinerary_item_id: Optional[uuid.UUID] = None
    logged_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseLogResponse(BaseModel):
    expense: ExpenseOut
    spend_total: float
    budget_remaining: float


class TrackerSummary(BaseModel):
    spend_total: float
    budget_total: float
    remaining: float
    percent_used: float
    items_total: int = 0
    items_visited: int = 0
    spent_by_category: Dict[str, float] = {}
