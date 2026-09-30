import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.user import User
from app.schemas.chat import ChatHistoryResponse, ChatRequest, ChatResponse
from app.services import conversation

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return conversation.handle_turn(db, user, payload.session_id, payload.message)


@router.get("/{session_id}", response_model=ChatHistoryResponse)
def history(session_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = db.get(ChatSession, session_id)
    if session is None:  # a brand-new conversation: nothing stored yet
        return {"session_id": session_id, "state": "COLLECTING", "slots": {}, "trip_id": None, "messages": []}
    if session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.seq)
        .all()
    )
    return {
        "session_id": session.id,
        "state": session.state,
        "slots": session.slots or {},
        "trip_id": session.trip_id,
        "messages": messages,
    }
