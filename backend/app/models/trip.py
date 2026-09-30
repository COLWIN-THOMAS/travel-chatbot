import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.database import Base

class Trip(Base):
    __tablename__ = "trips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    destination = Column(String, nullable=False)
    budget_total = Column(Numeric, nullable=False)
    days_count = Column(Integer, nullable=False)
    preferences = Column(ARRAY(String))
    status = Column(String, nullable=False, default="planning")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
