import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app as fastapi_app
from app.security import login_throttle
from app.services import llm, planner


@pytest.fixture(autouse=True)
def _fresh_throttle():
    login_throttle.clear()
    yield
    login_throttle.clear()


@pytest.fixture()
def db():
    """Every test runs inside a transaction that is rolled back, so the real database stays clean."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    fastapi_app.dependency_overrides[get_db] = lambda: db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def register(client, email=None, password="password123"):
    email = email or "{}@example.com".format(uuid.uuid4().hex[:10])
    r = client.post("/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": "Bearer " + body["access_token"]}, body["user"]


@pytest.fixture()
def auth(client):
    headers, user = register(client)
    return SimpleNamespace(headers=headers, user=user)


def sample_plan(days=2):
    items = lambda d: [
        planner.PlannedItem(place_name="Hotel Stay {}".format(d), category="hotel", estimated_cost=800),
        planner.PlannedItem(place_name="Baga Beach", category="attraction", estimated_cost=0),
        planner.PlannedItem(place_name="Fish Curry Rice", category="restaurant", estimated_cost=250),
        planner.PlannedItem(place_name="Local Taxi", category="transport", estimated_cost=300),
    ]
    return planner.ItineraryPlan(days=[planner.PlannedDay(day_number=d, items=items(d)) for d in range(1, days + 1)])


@pytest.fixture()
def trip(client, db, auth):
    """A trip owned by `auth` with a saved 2-day plan."""
    r = client.post(
        "/trips",
        headers=auth.headers,
        json={"destination": "Goa", "budget_total": 15000, "days_count": 2, "preferences": ["food"]},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    from app.models.trip import Trip

    planner.save_plan(db, db.get(Trip, uuid.UUID(data["id"])), sample_plan(2))
    db.flush()
    return SimpleNamespace(id=data["id"], data=data)


@pytest.fixture()
def fake_llm(monkeypatch):
    """Scriptable stand-in for the LLM layer: push Extraction objects, inspect what was called."""
    state = SimpleNamespace(extractions=[], calls=[], fallback_calls=0, plan=sample_plan(3), plan_error=None)

    def extract(state_name, known, history, message):
        state.calls.append((state_name, dict(known), message))
        return state.extractions.pop(0) if state.extractions else llm.Extraction()

    def fallback(state_name, known, history, message):
        state.fallback_calls += 1
        return "LLM fallback reply."

    def create_plan(slots, attempts=2):
        if state.plan_error:
            raise state.plan_error
        state.last_slots = slots
        return state.plan

    monkeypatch.setattr(llm, "extract_slots", extract)
    monkeypatch.setattr(llm, "fallback_reply", fallback)
    monkeypatch.setattr(planner, "create_plan", create_plan)
    return state
