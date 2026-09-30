import json
import uuid
from types import SimpleNamespace as NS

import pytest

from app.models.trip import Trip
from app.services import assistant, llm, planner
from tests.conftest import sample_plan


def block_tool(name, args, id_="tu_1"):
    return NS(type="tool_use", id=id_, name=name, input=args)


def resp(stop, *blocks):
    return NS(stop_reason=stop, content=list(blocks))


def text(t):
    return NS(type="text", text=t)


class FakeClient:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.messages = NS(create=self._create)

    def _create(self, **kw):
        self.requests.append(kw)
        return self.responses.pop(0)


@pytest.fixture()
def owned(client, db, trip):
    return db.get(Trip, uuid.UUID(trip.id))


def test_mark_visited_and_expense_via_tools(db, owned, monkeypatch):
    fake = FakeClient(
        resp("tool_use", block_tool("mark_visited", {"place_name": "baga"}, "a"),
             block_tool("log_expense", {"amount": 250, "category": "food", "place_name": "Fish Curry"}, "b")),
        resp("end_turn", text("Logged it!")),
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    reply, outcome = assistant.handle(db, owned, [], "went to baga, spent 250 on fish curry")
    assert reply == "Logged it!"
    assert outcome.actions == ["mark_visited", "log_expense"]
    # both tool results returned together in ONE user message
    results = fake.requests[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"] and not any(r["is_error"] for r in results)
    assert "Baga Beach" in fake.requests[1]["messages"][-1]["content"][0]["content"]


def test_ambiguous_or_missing_place_returns_tool_error(db, owned):
    out = assistant.Outcome()
    msg, err = assistant._run_tool(db, owned, "mark_visited", {"place_name": "hotel"}, out)
    assert err and "Ambiguous" in msg
    msg, err = assistant._run_tool(db, owned, "mark_visited", {"place_name": "eiffel"}, out)
    assert err and "No place matching" in msg
    assert out.actions == []


def test_tool_argument_validation(db, owned):
    out = assistant.Outcome()
    _, err = assistant._run_tool(db, owned, "log_expense", {"amount": -3}, out)
    assert err
    _, err = assistant._run_tool(db, owned, "update_plan", {"days_count": 50}, out)
    assert err
    _, err = assistant._run_tool(db, owned, "nonexistent", {}, out)
    assert err and out.actions == []


def test_update_plan_tool_regenerates_and_flags_change(db, owned, monkeypatch):
    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: sample_plan(slots["days_count"]))
    out = assistant.Outcome()
    msg, err = assistant._run_tool(db, owned, "update_plan", {"days_count": 3, "instructions": "more food"}, out)
    assert not err and out.itinerary_changed and owned.days_count == 3
    monkeypatch.setattr(planner, "create_plan", lambda s, attempts=2: (_ for _ in ()).throw(planner.PlanError("tight")))
    before = float(owned.budget_total)
    _, err = assistant._run_tool(db, owned, "update_plan", {"budget_total": 5}, out)
    assert err and float(owned.budget_total) == before  # a failed plan must not leave the trip half-changed


def test_tool_loop_is_bounded(db, owned, monkeypatch):
    forever = [resp("tool_use", block_tool("get_summary", {}, "x%d" % i)) for i in range(assistant.MAX_TOOL_ROUNDS + 2)]
    monkeypatch.setattr(llm, "get_client", lambda: FakeClient(*forever))
    reply, _ = assistant.handle(db, owned, [], "summary?")
    assert "wasn't able" in reply


def test_history_is_normalised_to_alternate_starting_with_user():
    msgs = assistant._to_messages(
        [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"},
         {"role": "assistant", "content": "c"}], "new <b>question</b>")
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "a\nb" and "<" not in msgs[-1]["content"]


def test_post_plan_chat_turn_end_to_end(client, auth, trip, db, monkeypatch, fake_llm):
    from app.models.chat_session import ChatSession
    sid = uuid.uuid4()
    db.add(ChatSession(id=sid, user_id=uuid.UUID(auth.user["id"]), state="POST_PLAN", slots={}, trip_id=uuid.UUID(trip.id)))
    db.flush()
    fake = FakeClient(resp("tool_use", block_tool("get_summary", {})), resp("end_turn", text("You have spent nothing yet.")))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    r = client.post("/chat", headers=auth.headers, json={"session_id": str(sid), "message": "how am I doing?"})
    assert r.status_code == 200
    body = r.json()
    assert body["conversation_state"] == "POST_PLAN" and body["reply_text"] == "You have spent nothing yet."
    assert body["itinerary"] is None and body["trip_id"] == trip.id


def test_post_plan_with_deleted_trip_drops_back_to_confirm(client, auth, db, fake_llm):
    from app.models.chat_session import ChatSession
    sid = uuid.uuid4()
    slots = {"destination": "Goa", "budget_total": 9000, "days_count": 2, "preferences": ["food"]}
    db.add(ChatSession(id=sid, user_id=uuid.UUID(auth.user["id"]), state="POST_PLAN", slots=slots, trip_id=None))
    db.flush()
    r = client.post("/chat", headers=auth.headers, json={"session_id": str(sid), "message": "hello"})
    assert r.status_code == 200 and "Shall I build the plan" in r.json()["reply_text"]
