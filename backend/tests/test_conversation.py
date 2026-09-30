import uuid

from app.services import conversation, llm, planner
from app.services.conversation import inr, merge_slots, recap
from tests.conftest import sample_plan

E = llm.Extraction


def say(client, auth, sid, text):
    r = client.post("/chat", headers=auth.headers, json={"session_id": sid, "message": text})
    assert r.status_code == 200, r.text
    return r.json()


def new_sid():
    return str(uuid.uuid4())


def test_inr_formatting_uses_indian_grouping():
    assert inr(500) == "₹500"
    assert inr(15000) == "​₹15,000".replace("​", "")
    assert inr(150000) == "₹1,50,000"
    assert inr(12345678) == "₹1,23,45,678"


def test_merge_slots_validates_and_reports_changes():
    slots, changed, errors = merge_slots({}, E(destination=" Goa ", budget_total=15000, days_count=4, preferences=["Food", "food", "Adventure"]))
    assert slots == {"destination": "Goa", "budget_total": 15000.0, "days_count": 4, "preferences": ["food", "adventure"]}
    assert set(changed) == {"destination", "budget_total", "days_count", "preferences"} and not errors

    _, changed, errors = merge_slots(slots, E(destination="Goa"))  # unchanged value is not a change
    assert changed == {} and errors == []

    _, changed, errors = merge_slots({}, E(budget_total=-5, days_count=40))
    assert changed == {} and len(errors) == 2


def test_happy_path_collect_confirm_generate(client, auth, fake_llm):
    sid = new_sid()
    fake_llm.extractions = [
        E(destination="Goa"),
        E(budget_total=15000),
        E(days_count=3),
        E(preferences=["food", "beaches"]),
        E(is_confirmation=True),
    ]
    r = say(client, auth, sid, "I want to go to Goa")
    assert r["conversation_state"] == "COLLECTING" and "budget" in r["reply_text"].lower()
    assert r["extracted_fields"] == {"destination": "Goa"} and r["trip_id"] is None

    r = say(client, auth, sid, "15k")
    assert "days" in r["reply_text"].lower()
    r = say(client, auth, sid, "3 days")
    assert "enjoy" in r["reply_text"].lower()

    r = say(client, auth, sid, "food and beaches")
    assert r["conversation_state"] == "CONFIRM"
    assert "Goa" in r["reply_text"] and "₹15,000" in r["reply_text"] and r["itinerary"] is None

    r = say(client, auth, sid, "yes")
    assert r["conversation_state"] == "GENERATE_PLAN"
    assert r["trip_id"] and len(r["itinerary"]["days"]) == 3
    assert fake_llm.last_slots["destination"] == "Goa"

    # the trip exists, belongs to the user, and the whole conversation is linked to it
    trip = client.get("/trips/" + r["trip_id"], headers=auth.headers).json()
    assert trip["status"] == "active" and trip["preferences"] == ["food", "beaches"]
    hist = client.get("/chat/" + sid, headers=auth.headers).json()
    assert hist["state"] == "POST_PLAN" and hist["trip_id"] == r["trip_id"]
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant"] * 5


def test_everything_in_one_message_goes_straight_to_confirm(client, auth, fake_llm):
    fake_llm.extractions = [E(destination="Delhi", budget_total=8000, days_count=2, preferences=["culture"])]
    r = say(client, auth, new_sid(), "Delhi, 8k, 2 days, culture")
    assert r["conversation_state"] == "CONFIRM" and "Shall I build the plan" in r["reply_text"]


def test_confirm_is_never_skipped_even_if_llm_says_confirmation_early(client, auth, fake_llm):
    fake_llm.extractions = [E(destination="Goa", is_confirmation=True)]
    r = say(client, auth, new_sid(), "Goa, yes")
    assert r["conversation_state"] == "COLLECTING" and r["trip_id"] is None


def test_editing_at_confirm_reuses_extraction_and_recaps(client, auth, fake_llm):
    sid = new_sid()
    fake_llm.extractions = [
        E(destination="Goa", budget_total=10000, days_count=2, preferences=["food"]),
        E(budget_total=20000),
    ]
    say(client, auth, sid, "goa 10k 2 days food")
    r = say(client, auth, sid, "actually make it 20000")
    assert r["conversation_state"] == "CONFIRM" and "₹20,000" in r["reply_text"]
    assert r["trip_id"] is None and fake_llm.calls[-1][0] == "CONFIRM"


def test_fallback_uses_llm_twice_then_canned(client, auth, fake_llm):
    sid = new_sid()
    r1 = say(client, auth, sid, "hello there")
    r2 = say(client, auth, sid, "what's the weather like?")
    r3 = say(client, auth, sid, "blah")
    for r in (r1, r2, r3):
        assert r["conversation_state"] == "FALLBACK"
        assert "Where would you like to go?" in r["reply_text"]  # always steers back
    assert "LLM fallback reply." in r1["reply_text"] and "LLM fallback reply." in r2["reply_text"]
    assert "LLM fallback reply." not in r3["reply_text"]
    assert fake_llm.fallback_calls == 2

    fake_llm.extractions = [E(destination="Goa")]  # a good turn resets the counter
    say(client, auth, sid, "Goa")
    say(client, auth, sid, "hmm")
    assert fake_llm.fallback_calls == 3


def test_invalid_values_get_a_specific_message_not_a_fallback(client, auth, fake_llm):
    fake_llm.extractions = [E(days_count=60)]
    r = say(client, auth, new_sid(), "60 days")
    assert "1 to 14 days" in r["reply_text"] and r["conversation_state"] != "FALLBACK"
    assert fake_llm.fallback_calls == 0


def test_plan_failure_keeps_user_at_confirm_without_creating_a_trip(client, auth, fake_llm):
    sid = new_sid()
    fake_llm.extractions = [E(destination="Goa", budget_total=100, days_count=5, preferences=["food"]), E(is_confirmation=True)]
    say(client, auth, sid, "goa 100 rupees 5 days food")
    fake_llm.plan_error = planner.PlanError("too tight")
    r = say(client, auth, sid, "yes")
    assert r["conversation_state"] == "CONFIRM" and "couldn't fit" in r["reply_text"] and r["trip_id"] is None
    assert client.get("/trips", headers=auth.headers).json() == []


def test_sessions_are_private_to_their_owner(client, auth, fake_llm):
    from tests.conftest import register
    sid = new_sid()
    say(client, auth, sid, "hi")
    other, _ = register(client)
    assert client.post("/chat", headers=other, json={"session_id": sid, "message": "hi"}).status_code == 404
    assert client.get("/chat/" + sid, headers=other).status_code == 404


def test_chat_input_validation_and_auth(client, auth):
    assert client.post("/chat", json={"session_id": new_sid(), "message": "hi"}).status_code == 401
    for bad in ({"session_id": "nope", "message": "hi"}, {"session_id": new_sid(), "message": "   "},
                {"session_id": new_sid(), "message": "x" * 1001}):
        assert client.post("/chat", headers=auth.headers, json=bad).status_code == 422


def test_daily_message_limit(client, auth, fake_llm, monkeypatch):
    monkeypatch.setattr(conversation.config, "MAX_MESSAGES_PER_DAY", 2)
    sid = new_sid()
    say(client, auth, sid, "a")
    say(client, auth, sid, "b")
    assert client.post("/chat", headers=auth.headers, json={"session_id": sid, "message": "c"}).status_code == 429


def test_llm_outage_returns_503_and_does_not_persist_the_turn(client, auth, monkeypatch):
    def down(*a, **k):
        raise llm.LLMUnavailable("no key")

    monkeypatch.setattr(llm, "extract_slots", down)
    sid = new_sid()
    r = client.post("/chat", headers=auth.headers, json={"session_id": sid, "message": "hi"})
    assert r.status_code == 503


def test_recap_lists_all_details():
    text = recap({"destination": "Noida", "budget_total": 9000, "days_count": 2, "preferences": ["food", "shopping"]})
    assert "Noida" in text and "food, shopping" in text
