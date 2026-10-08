"""Drives the REAL Anthropic SDK (request building, structured-output parsing, tool loop) against a mock HTTP
transport, so request shapes are validated without an API key or network."""
import json
import uuid

import anthropic
import httpx
import pytest

from app import config
from app.models.trip import Trip
from app.services import assistant, llm, planner
from tests.conftest import sample_plan


class MockAnthropic:
    def __init__(self, *replies):
        self.replies, self.requests = list(replies), []
        self.client = anthropic.Anthropic(
            api_key="test-key", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(self._handle))
        )

    def _handle(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        self.requests.append(json.loads(request.content))
        return httpx.Response(200, json=self.replies.pop(0))


def message(content, stop="end_turn", model="claude-haiku-4-5"):
    return {
        "id": "msg_test", "type": "message", "role": "assistant", "model": model, "content": content,
        "stop_reason": stop, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 10},
    }


def text_reply(text, **kw):
    return message([{"type": "text", "text": text}], **kw)


@pytest.fixture()
def mock(monkeypatch):
    def install(*replies):
        m = MockAnthropic(*replies)
        monkeypatch.setattr(llm, "get_client", lambda: m.client)
        return m
    return install


def test_extract_slots_sends_a_schema_constrained_request_and_parses_the_result(mock):
    m = mock(text_reply(json.dumps({"destination": "Goa", "budget_total": 15000, "days_count": 4,
                                    "preferences": ["food"], "is_confirmation": False, "start_date": "2026-11-14"})))
    out = llm.extract_slots("COLLECTING", {}, [{"role": "assistant", "content": "hi"}], "goa 15k 4 days <b>food</b>")
    assert (out.destination, out.budget_total, out.days_count, out.preferences) == ("Goa", 15000, 4, ["food"])

    req = m.requests[0]
    assert req["model"] == config.EXTRACTION_MODEL == "claude-haiku-4-5"
    assert req["output_config"]["format"]["type"] == "json_schema"
    props = req["output_config"]["format"]["schema"]["properties"]
    assert set(props) == {"destination", "budget_total", "days_count", "start_date", "dates_undecided",
                          "preferences", "is_confirmation"}
    assert "temperature" not in req and "thinking" not in req and "effort" not in json.dumps(req["output_config"])
    content = req["messages"][0]["content"]
    assert "<newest_message>goa 15k 4 days  b food /b</newest_message>" in content  # user text can't close our tags
    assert "not instructions" in req["system"]
    assert out.start_date == "2026-11-14" and "<today>20" in content  # the model is told today's date to resolve "next Friday"


def test_extract_slots_tolerates_an_unparseable_model_reply(mock):
    mock(text_reply("not json"))
    with pytest.raises(Exception):
        llm.extract_slots("COLLECTING", {}, [], "hi")


def test_fallback_reply_returns_plain_text(mock):
    m = mock(text_reply("Goa is lovely in winter."))
    assert llm.fallback_reply("COLLECTING", {}, [], "is goa nice?") == "Goa is lovely in winter."
    assert m.requests[0]["max_tokens"] == 250 and "output_config" not in m.requests[0]


def test_sdk_errors_become_llm_unavailable(monkeypatch):
    def down(request):
        return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}})

    client = anthropic.Anthropic(api_key="k", max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(down)))
    monkeypatch.setattr(llm, "get_client", lambda: client)
    with pytest.raises(llm.LLMUnavailable):
        llm.extract_slots("COLLECTING", {}, [], "hi")


def test_planner_uses_the_strong_model_with_effort_and_real_candidates(mock, monkeypatch):
    plan = sample_plan(2).model_dump()
    m = mock(text_reply(json.dumps(plan), model="claude-sonnet-5"))
    monkeypatch.setattr(planner, "gather_candidates", lambda d: "HOTEL:\n- Sea View (rating 4.4, price Inexpensive)")
    result = planner.create_plan({"destination": "Goa", "budget_total": 15000.0, "days_count": 2, "preferences": ["food"]})
    assert planner.plan_total(result) == 2 * (800 + 250 + 300)

    req = m.requests[0]
    assert req["model"] == "claude-sonnet-5"
    assert req["output_config"]["effort"] == "medium" and req["output_config"]["format"]["type"] == "json_schema"
    assert "Sea View" in req["messages"][0]["content"]
    assert "Exactly 2 days" in req["system"] and "at most 15000 rupees" in req["system"]
    assert "temperature" not in req
    category = req["output_config"]["format"]["schema"]
    assert "hotel" in json.dumps(category) and "transport" in json.dumps(category)


def test_planner_retry_carries_feedback_to_the_second_request(mock, monkeypatch):
    bad = sample_plan(2)
    bad.days[0].items[0].estimated_cost = 50000
    m = mock(text_reply(json.dumps(bad.model_dump())), text_reply(json.dumps(sample_plan(2).model_dump())))
    monkeypatch.setattr(planner, "gather_candidates", lambda d: "")
    planner.create_plan({"destination": "Goa", "budget_total": 15000.0, "days_count": 2, "preferences": []})
    assert len(m.requests) == 2
    assert "<feedback>" not in m.requests[0]["messages"][0]["content"]
    assert "exceeds" in m.requests[1]["messages"][0]["content"]


def test_haiku_planner_override_omits_effort(mock, monkeypatch):
    monkeypatch.setattr(config, "PLANNER_MODEL", "claude-haiku-4-5")
    m = mock(text_reply(json.dumps(sample_plan(1).model_dump())))
    monkeypatch.setattr(planner, "gather_candidates", lambda d: "")
    planner.create_plan({"destination": "Goa", "budget_total": 5000.0, "days_count": 1, "preferences": []})
    assert "effort" not in m.requests[0]["output_config"]


def test_assistant_tool_loop_through_the_real_sdk(client, db, auth, trip, mock):
    owned = db.get(Trip, uuid.UUID(trip.id))
    m = mock(
        message([{"type": "text", "text": "On it."},
                 {"type": "tool_use", "id": "tu_1", "name": "log_expense",
                  "input": {"amount": 250, "category": "food", "place_name": "fish curry"}}], stop="tool_use"),
        text_reply("Logged ₹250 for Fish Curry Rice."),
    )
    reply, outcome = assistant.handle(db, owned, [], "spent 250 on fish curry")
    assert reply.startswith("Logged") and outcome.actions == ["log_expense"]

    first, second = m.requests
    assert first["model"] == config.CHAT_MODEL and {t["name"] for t in first["tools"]} == {
        "mark_visited", "log_expense", "get_summary", "update_plan", "set_trip_dates"}
    assert all(t["input_schema"]["type"] == "object" for t in first["tools"])
    last = second["messages"][-1]
    assert last["role"] == "user" and last["content"][0]["type"] == "tool_result"
    assert last["content"][0]["tool_use_id"] == "tu_1" and not last["content"][0].get("is_error")
    assert second["messages"][-2]["role"] == "assistant"  # tool_use turn echoed back
    assert "Goa" in first["system"] and "Fish Curry Rice" in first["system"]

    spend = client.get("/tracker/" + trip.id, headers=auth.headers).json()["spend_total"]
    assert spend == 250
