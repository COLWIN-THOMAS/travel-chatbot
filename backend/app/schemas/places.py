from typing import List, Optional
from pydantic import BaseModel

class PlaceSummary(BaseModel):
    id: str
    name: str
    category: str
    price_level: Optional[str] = None
    rating: Optional[float] = None
    address: Optional[str] = None

class PlacesListResponse(BaseModel):
    places: List[PlaceSummary]

class ReviewSummary(BaseModel):
    author_name: Optional[str] = None
    rating: Optional[float] = None
    text: Optional[str] = None

class PlaceDetail(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    rating: Optional[float] = None
    price_level: Optional[str] = None
    opening_hours: Optional[List[str]] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None
    photos: List[str] = []  # signed, expiring URLs served by GET /places/photo
    reviews: List[ReviewSummary] = []
