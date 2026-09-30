import uuid
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class Expense(Base):
    __tablename__ = "expenses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False)
    itinerary_item_id = Column(UUID(as_uuid=True), ForeignKey("itinerary_items.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric, nullable=False)
    category = Column(String, nullable=True)
    logged_at = Column(DateTime(timezone=True), server_default=func.now())
