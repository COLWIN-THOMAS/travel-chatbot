"""The chat state machine (see docs/conversation-flow.md).

States: COLLECTING -> CONFIRM -> (GENERATE_PLAN) -> POST_PLAN, with FALLBACK reported for turns
that produced no usable details. LLM calls happen only for extraction, fallback and planning;
all other replies are deterministic templates to keep cost and latency low.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app import config
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.trip import Trip
from app.models.user import User
from app.schemas.trip import clean_preferences
from app.services import assistant, dates, llm, planner
from app.services.itinerary_view import load_days

log = logging.getLogger(__name__)

SLOT_ORDER = ["destination", "budget_total", "days_count", "start_date", "preferences"]
MAX_LLM_FALLBACKS = 2  # consecutive; after that, a canned reprompt (no API cost)
MAX_BUDGET = 10_000_000

QUESTIONS = {
    "destination": "Where would you like to go?",
    "budget_total": "What's your total budget for the trip (in ₹)?",
    "days_count": "How many days will you be travelling?",
    "start_date": "Which day do you start? Pick your dates on the calendar, or tell me (for example \"15 Nov\"). If you haven't decided yet, say so.",
    "preferences": "What do you enjoy most? For example: food, adventure, culture, relaxed, nightlife, shopping.",
}


def inr(amount: float) -> str:
    s = str(int(round(amount)))
    if len(s) > 3:
        head, tail, groups = s[:-3], s[-3:], []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return "₹" + s


def missing_slots(slots: dict) -> List[str]:
    return [k for k in SLOT_ORDER if not slots.get(k)]


def describe(field: str, value) -> str:
    if field == "destination":
        return "destination {}".format(value)
    if field == "budget_total":
        return "budget {}".format(inr(value))
    if field == "days_count":
        return "{} day{}".format(value, "" if value == 1 else "s")
    if field == "start_date":
        if value == dates.UNDECIDED:
            return "dates not fixed yet"
        return "starting {}".format(dates.pretty(dates.parse_iso(value)))
    return "interests: {}".format(", ".join(value))


def dates_line(slots: dict) -> str:
    start = dates.parse_iso(slots.get("start_date")) if slots.get("start_date") != dates.UNDECIDED else None
    if start is None:
        return "Not fixed yet (you can add them later)"
    return dates.pretty_range(start, slots["days_count"])


def recap(slots: dict) -> str:
    return (
        "Here's your trip:\n"
        "• Destination: {}\n• Budget: {}\n• Days: {}\n• Dates: {}\n• Interests: {}\n\n"
        "Shall I build the plan? Reply \"yes\" to confirm, or tell me what to change."
    ).format(
        slots["destination"], inr(slots["budget_total"]), slots["days_count"], dates_line(slots),
        ", ".join(slots["preferences"]),
    )


def merge_slots(slots: dict, extraction: llm.Extraction) -> Tuple[dict, dict, List[str]]:
    """Validate what the LLM extracted and merge it. Returns (new_slots, changed_fields, error_messages)."""
    new, changed, errors = dict(slots), {}, []

    dest = (extraction.destination or "").strip()
    if dest:
        if 2 <= len(dest) <= 100:
            if dest != new.get("destination"):
                new["destination"], changed["destination"] = dest, dest
        else:
            errors.append("That destination doesn't look right.")

    if extraction.budget_total is not None:
        b = float(extraction.budget_total)
        if 0 < b <= MAX_BUDGET:
            if b != new.get("budget_total"):
                new["budget_total"], changed["budget_total"] = b, b
        else:
            errors.append("Please give a budget between ₹1 and {}.".format(inr(MAX_BUDGET)))

    if extraction.days_count is not None:
        d = int(extraction.days_count)
        if 1 <= d <= 14:
            if d != new.get("days_count"):
                new["days_count"], changed["days_count"] = d, d
        else:
            errors.append("I can plan trips of 1 to 14 days.")

    if extraction.start_date:
        start = dates.parse_iso(extraction.start_date)
        if start is None:
            errors.append("I couldn't read that date - try something like 15 Nov.")
        else:
            problem = dates.check_new_trip_date(start)
            if problem:
                errors.append(problem)
            elif start.isoformat() != new.get("start_date"):
                new["start_date"], changed["start_date"] = start.isoformat(), start.isoformat()
    elif extraction.dates_undecided and new.get("start_date") != dates.UNDECIDED:
        new["start_date"], changed["start_date"] = dates.UNDECIDED, dates.UNDECIDED

    if extraction.preferences is not None:
        prefs = clean_preferences(extraction.preferences)
        if prefs and prefs != new.get("preferences"):
            new["preferences"], changed["preferences"] = prefs, prefs

    return new, changed, errors


def next_field(session: ChatSession) -> Optional[str]:
    """Which detail the assistant is currently asking for (drives the calendar button in the app)."""
    if session.state not in ("COLLECTING", "FALLBACK"):
        return None
    missing = missing_slots(session.slots or {})
    return missing[0] if missing else None


def _get_session(db: Session, user: User, session_id: uuid.UUID) -> ChatSession:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).with_for_update().first()
    if session is None:
        session = ChatSession(id=session_id, user_id=user.id, state="COLLECTING", slots={}, fallback_count=0)
        db.add(session)
        db.flush()
    elif session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _enforce_daily_limit(db: Session, user: User) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    used = (
        db.query(func.count(ChatMessage.id))
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .filter(ChatSession.user_id == user.id, ChatMessage.role == "user", ChatMessage.created_at > since)
        .scalar()
    )
    if used >= config.MAX_MESSAGES_PER_DAY:
        raise HTTPException(status_code=429, detail="Daily message limit reached. Please try again tomorrow.")


def load_history(db: Session, session_id: uuid.UUID, limit: int = 12) -> List[dict]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.seq.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _ask_next(slots: dict) -> str:
    return QUESTIONS[missing_slots(slots)[0]]


def _collecting_turn(db, session, history, message) -> dict:
    """COLLECTING and CONFIRM share one path: extract, merge, then decide."""
    state = session.state
    extraction = llm.extract_slots(state, session.slots, history, message)
    slots, changed, errors = merge_slots(session.slots, extraction)
    is_confirm = state == "CONFIRM" and extraction.is_confirmation and not changed and not missing_slots(slots)

    if is_confirm:
        return _generate(db, session, slots)

    if changed:
        session.slots, session.fallback_count = slots, 0
        ack = "Got it – " + ", ".join(describe(k, v) for k, v in changed.items()) + "."
        if errors:
            ack += " " + " ".join(errors)
        if not missing_slots(slots):
            session.state = "CONFIRM"
            return {"reply": ack + "\n\n" + recap(slots), "state": "CONFIRM", "extracted": changed}
        session.state = "COLLECTING"
        return {"reply": ack + " " + _ask_next(slots), "state": "COLLECTING", "extracted": changed}

    if errors:  # understood but invalid values: not a fallback
        session.fallback_count = 0
        follow = recap(slots) if state == "CONFIRM" else _ask_next(slots)
        return {"reply": " ".join(errors) + " " + follow, "state": state, "extracted": None}

    return _fallback(session, history, message)


def _fallback(session, history, message) -> dict:
    state = session.state
    steer = recap(session.slots) if state == "CONFIRM" else _ask_next(session.slots)
    if session.fallback_count < MAX_LLM_FALLBACKS:
        reply = llm.fallback_reply(state, session.slots, history, message)
        text = (reply + "\n\n" + steer) if reply else "Sorry, I didn't catch that. " + steer
    else:
        text = "Sorry, I didn't understand that. " + steer
    session.fallback_count += 1
    return {"reply": text, "state": "FALLBACK", "extracted": None}


def _generate(db, session, slots) -> dict:
    try:
        plan = planner.create_plan(slots)
    except planner.PlanError:
        session.slots = slots
        return {
            "reply": (
                "I couldn't fit a good plan for {} days in {} within {}. "
                "Try a higher budget or fewer days – tell me what to change."
            ).format(slots["days_count"], slots["destination"], inr(slots["budget_total"])),
            "state": "CONFIRM",
            "extracted": None,
        }

    trip = Trip(
        user_id=session.user_id,
        destination=slots["destination"],
        budget_total=slots["budget_total"],
        days_count=slots["days_count"],
        start_date=(None if slots.get("start_date") == dates.UNDECIDED else dates.parse_iso(slots["start_date"])),
        preferences=slots["preferences"],
    )
    db.add(trip)
    db.flush()
    planner.save_plan(db, trip, plan)
    session.slots, session.trip_id, session.state, session.fallback_count = slots, trip.id, "POST_PLAN", 0
    db.execute(update(ChatMessage).where(ChatMessage.session_id == session.id).values(trip_id=trip.id))
    total = planner.plan_total(plan)
    when = " ({})".format(dates.pretty_range(trip.start_date, trip.days_count)) if trip.start_date else ""
    reply = (
        "Your {}-day {} plan{} is ready! Estimated total {} of your {} budget. "
        "You can ask me to mark places visited, log expenses, or tweak the plan."
    ).format(slots["days_count"], slots["destination"], when, inr(total), inr(slots["budget_total"]))
    return {"reply": reply, "state": "GENERATE_PLAN", "extracted": None, "trip": trip, "plan_changed": True}


def _post_plan_turn(db, session, history, message) -> dict:
    trip = db.get(Trip, session.trip_id) if session.trip_id else None
    if trip is None:  # trip was deleted: fall back to the recap so the user can regenerate
        session.state = "CONFIRM"
        return _collecting_turn(db, session, history, message)
    text, outcome = assistant.handle(db, trip, history, message)
    return {"reply": text, "state": "POST_PLAN", "extracted": None, "trip": trip,
            "plan_changed": outcome.itinerary_changed, "actions": outcome.actions}


def handle_turn(db: Session, user: User, session_id: uuid.UUID, message: str) -> dict:
    session = _get_session(db, user, session_id)
    _enforce_daily_limit(db, user)
    history = load_history(db, session.id)

    user_msg = ChatMessage(session_id=session.id, trip_id=session.trip_id, role="user", content=message)
    db.add(user_msg)
    db.flush()

    if session.state == "POST_PLAN":
        result = _post_plan_turn(db, session, history, message)
    else:
        result = _collecting_turn(db, session, history, message)

    user_msg.extracted_fields = result.get("extracted")
    db.add(ChatMessage(session_id=session.id, trip_id=session.trip_id, role="assistant", content=result["reply"]))
    db.commit()

    itinerary = None
    if result.get("plan_changed") and result.get("trip") is not None:
        itinerary = {"days": load_days(db, result["trip"].id)}

    return {
        "session_id": session.id,
        "reply_text": result["reply"],
        "conversation_state": result["state"],
        "extracted_fields": session.slots,
        "next_field": next_field(session),
        "trip_id": session.trip_id,
        "itinerary": itinerary,
        "actions": result.get("actions", []),
    }
