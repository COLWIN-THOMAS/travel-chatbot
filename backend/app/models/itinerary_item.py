import uuid
from sqlalchemy import Column, String, Integer, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class ItineraryItem(Base):
    __tablename__ = "itinerary_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    day_id = Column(UUID(as_uuid=True), ForeignKey("days.id", ondelete="CASCADE"), nullable=False)
    place_name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # 'hotel' | 'restaurant' | 'attraction' | 'transport'
    estimated_cost = Column(Numeric, nullable=False)
    visited = Column(Boolean, nullable=False, default=False)
    order_in_day = Column(Integer, nullable=False)
    notes = Column(String, nullable=True)
