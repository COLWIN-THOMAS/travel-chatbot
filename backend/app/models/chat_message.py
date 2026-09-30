import uuid
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Identity, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq = Column(BigInteger, Identity(always=True), nullable=False, index=True)  # total order within and across turns
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    trip_id = Column(UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=True)
    role = Column(String, nullable=False)  # 'user' | 'assistant'
    content = Column(String, nullable=False)
    extracted_fields = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
