import uuid
from datetime import date, timedelta

import pytest

from app.models.day import Day
from app.models.expense import Expense
from app.models.itinerary_item import ItineraryItem
from app.models.trip import Trip
from app.services import assistant, dates, planner, rebalance, replan, weather
from app.services import llm
from app.services.conversation import merge_slots
from tests.conftest import sample_plan

TODAY = dates.today_ist()


def make_trip(client, db, auth, start_offset=None, days=2, budget=15000):
    """A saved trip with `days` planned days, starting `start_offset` days from today (None = undated)."""
    body = {"destination": "Goa", "budget_total": budget, "days_count": days, "preferences": ["food"]}
    if start_offset is not None:
        body["start_date"] = (TODAY + timedelta(days=start_offset)).isoformat()
    r = client.post("/trips", headers=auth.headers, json=body)
    assert r.status_code == 201, r.text
    trip = db.get(Trip, uuid.UUID(r.json()["id"]))
    planner.save_plan(db, trip, sample_plan(days))
    db.flush()
    return trip


def day_rows(db, trip):
    return db.query(Day).filter(Day.trip_id == trip.id).order_by(Day.day_number).all()


def items_of(db, day):
    return db.query(ItineraryItem).filter(ItineraryItem.day_id == day.id).order_by(ItineraryItem.order_in_day).all()


# ---------- pure date helpers ----------

def test_phase_and_end_date():
    start = date(2026, 11, 10)
    assert dates.end_date(start, 4) == date(2026, 11, 13) and dates.end_date(None, 4) is None
    assert dates.phase(None, 3) == "undated"
    assert dates.phase(start, 4, today=date(2026, 11, 9)) == "upcoming"
    assert dates.phase(start, 4, today=date(2026, 11, 10)) == "ongoing"
    assert dates.phase(start, 4, today=date(2026, 11, 13)) == "ongoing"
    assert dates.phase(start, 4, today=date(2026, 11, 14)) == "completed"
    assert dates.days_elapsed(start, today=date(2026, 11, 12)) == 2
    assert dates.days_elapsed(start, today=date(2026, 11, 1)) == 0 and dates.days_elapsed(None) == 0


# ---------- trips API ----------

def test_trip_with_dates_reports_end_date_and_phase(client, auth):
    start = TODAY + timedelta(days=5)
    r = client.post("/trips", headers=auth.headers, json={
        "destination": "Goa", "budget_total": 9000, "days_count": 3, "start_date": start.isoformat()})
    body = r.json()
    assert r.status_code == 201
    assert body["start_date"] == start.isoformat() and body["end_date"] == (start + timedelta(days=2)).isoformat()
    assert body["phase"] == "upcoming"


def test_trip_without_dates_is_undated_and_absurd_dates_are_rejected(client, auth):
    r = client.post("/trips", headers=auth.headers, json={"destination": "Goa", "budget_total": 9000, "days_count": 2})
    assert r.json()["phase"] == "undated" and r.json()["end_date"] is None
    for bad in (TODAY - timedelta(days=800), TODAY + timedelta(days=900)):
        r = client.post("/trips", headers=auth.headers, json={
            "destination": "Goa", "budget_total": 9000, "days_count": 2, "start_date": bad.isoformat()})
        assert r.status_code == 422


def test_planner_dates_every_day(client, db, auth):
    trip = make_trip(client, db, auth, start_offset=7, days=3)
    assert [d.date for d in day_rows(db, trip)] == [TODAY + timedelta(days=7 + k) for k in range(3)]


def test_set_dates_redates_the_whole_itinerary_and_can_clear_them(client, db, auth):
    trip = make_trip(client, db, auth, start_offset=None, days=2)
    assert all(d.date is None for d in day_rows(db, trip))

    new_start = TODAY + timedelta(days=20)
    r = client.put("/trips/{}/dates".format(trip.id), headers=auth.headers, json={"start_date": new_start.isoformat()})
    assert r.status_code == 200 and r.json()["phase"] == "upcoming"
    detail = client.get("/trips/{}".format(trip.id), headers=auth.headers).json()
    assert [d["date"] for d in detail["days"]] == [new_start.isoformat(), (new_start + timedelta(days=1)).isoformat()]

    r = client.put("/trips/{}/dates".format(trip.id), headers=auth.headers, json={"start_date": None})
    assert r.json()["phase"] == "undated"
    assert all(d["date"] is None for d in client.get("/itinerary/{}".format(trip.id), headers=auth.headers).json()["days"])


def test_set_dates_validation_and_ownership(client, db, auth):
    from tests.conftest import register
    trip = make_trip(client, db, auth)
    url = "/trips/{}/dates".format(trip.id)
    assert client.put(url, headers=auth.headers, json={"start_date": "not-a-date"}).status_code == 422
    far = (TODAY + timedelta(days=1000)).isoformat()
    assert client.put(url, headers=auth.headers, json={"start_date": far}).status_code == 422
    other, _ = register(client)
    assert client.put(url, headers=other, json={"start_date": TODAY.isoformat()}).status_code == 404


# ---------- trip history ----------

def test_trip_list_is_a_history_with_spend_and_progress(client, db, auth):
    done = make_trip(client, db, auth, start_offset=-10, days=2, budget=10000)   # finished
    soon = make_trip(client, db, auth, start_offset=30, days=2)                  # upcoming
    legacy = make_trip(client, db, auth, start_offset=None, days=2)              # no dates
    first_item = items_of(db, day_rows(db, done)[0])[0]
    first_item.visited = True
    db.add(Expense(trip_id=done.id, amount=2500, itinerary_item_id=first_item.id))
    db.flush()

    rows = {r["id"]: r for r in client.get("/trips", headers=auth.headers).json()}
    assert set(rows) == {str(done.id), str(soon.id), str(legacy.id)}
    d = rows[str(done.id)]
    assert d["phase"] == "completed" and d["spend_total"] == 2500
    assert d["items_visited"] == 1 and d["items_total"] == 8
    assert d["estimated_total"] == 2 * (800 + 0 + 250 + 300)  # sample_plan: 1350 a day
    assert rows[str(soon.id)]["phase"] == "upcoming" and rows[str(soon.id)]["spend_total"] == 0
    assert rows[str(legacy.id)]["phase"] == "undated"


# ---------- weather by real date ----------

def _forecast(start, n=16):
    return {"daily": {
        "time": [(start + timedelta(days=i)).isoformat() for i in range(n)],
        "weathercode": [0] * n, "temperature_2m_max": [30.0 + i for i in range(n)],
        "temperature_2m_min": [22.0] * n, "precipitation_probability_max": [10] * n}}


def _fake_weather(monkeypatch):
    weather._cache.clear()
    weather._geo_cache.clear()
    goa = [{"name": "Goa", "lat": "15.30", "lon": "74.08", "display_name": "Goa, India"}]

    def fake_get(url, params, headers=None):
        return goa if "nominatim" in url else _forecast(TODAY)

    monkeypatch.setattr(weather, "_get_json", fake_get)


def test_weather_matches_trip_days_by_calendar_date(client, db, auth, monkeypatch):
    _fake_weather(monkeypatch)
    trip = make_trip(client, db, auth, start_offset=3, days=2)
    body = client.get("/weather/{}".format(trip.id), headers=auth.headers).json()
    assert [d["day_number"] for d in body["days"]] == [1, 2]
    assert [d["date"] for d in body["days"]] == [(TODAY + timedelta(days=3)).isoformat(), (TODAY + timedelta(days=4)).isoformat()]
    assert body["days"][0]["temp_max"] == 33.0 and body["note"] is None  # offset 3 -> 30 + 3


def test_weather_for_a_trip_beyond_the_forecast_window_explains_itself(client, db, auth, monkeypatch):
    _fake_weather(monkeypatch)
    trip = make_trip(client, db, auth, start_offset=60, days=2)
    body = client.get("/weather/{}".format(trip.id), headers=auth.headers).json()
    assert body["days"] == [] and "Forecasts only reach" in body["note"]


def test_weather_partially_in_window_only_returns_covered_days(client, db, auth, monkeypatch):
    _fake_weather(monkeypatch)
    trip = make_trip(client, db, auth, start_offset=15, days=3)  # window covers offsets 0..15
    body = client.get("/weather/{}".format(trip.id), headers=auth.headers).json()
    assert [d["day_number"] for d in body["days"]] == [1] and body["note"]


def test_weather_for_undated_trips_keeps_the_old_today_based_mapping(client, db, auth, monkeypatch):
    _fake_weather(monkeypatch)
    trip = make_trip(client, db, auth, start_offset=None, days=2)
    body = client.get("/weather/{}".format(trip.id), headers=auth.headers).json()
    assert [d["day_number"] for d in body["days"]] == [1, 2] and body["days"][0]["date"] == TODAY.isoformat()


# ---------- finished days are never rewritten ----------

def cheap(slots, attempts=2):
    return planner.ItineraryPlan(days=[
        planner.PlannedDay(day_number=d, items=[planner.PlannedItem(place_name="Free Walk", category="attraction", estimated_cost=0)])
        for d in range(1, slots["days_count"] + 1)])


def test_started_through_counts_past_days_even_if_nothing_was_ticked(client, db, auth):
    assert rebalance.started_through(db, make_trip(client, db, auth, start_offset=-1, days=3)) == 1
    assert rebalance.started_through(db, make_trip(client, db, auth, start_offset=0, days=3)) == 0  # today is still editable
    assert rebalance.started_through(db, make_trip(client, db, auth, start_offset=-30, days=3)) == 3  # capped at the last day
    assert rebalance.started_through(db, make_trip(client, db, auth, start_offset=None, days=3)) == 0


def test_rebalance_treats_a_past_day_as_finished_without_any_ticks(client, db, auth, monkeypatch):
    monkeypatch.setattr(planner, "create_plan", cheap)
    trip = make_trip(client, db, auth, start_offset=-1, days=2)   # day 1 was yesterday
    day1 = day_rows(db, trip)[0]
    before = [i.id for i in items_of(db, day1)]
    db.add(Expense(trip_id=trip.id, amount=14990))                 # money for day 2 is nearly gone
    db.flush()

    notice = rebalance.maybe_rebalance(db, trip)
    assert notice.rebalanced and (notice.days_from, notice.days_to) == (2, 2)
    after = day_rows(db, trip)
    assert after[0].id == day1.id and [i.id for i in items_of(db, after[0])] == before
    assert [i.place_name for i in items_of(db, after[1])] == ["Free Walk"]
    assert after[1].date == TODAY  # the rebuilt day keeps its real date


def test_rebalance_passes_the_remaining_start_date_to_the_planner(client, db, auth, monkeypatch):
    seen = {}

    def spy(slots, attempts=2):
        seen.update(slots)
        return cheap(slots)

    monkeypatch.setattr(planner, "create_plan", spy)
    trip = make_trip(client, db, auth, start_offset=-1, days=2)
    db.add(Expense(trip_id=trip.id, amount=14990))
    db.flush()
    rebalance.maybe_rebalance(db, trip)
    assert seen["start_date"] == TODAY.isoformat() and seen["days_count"] == 1


def test_manual_replan_keeps_started_days_and_only_rebuilds_the_rest(client, db, auth, monkeypatch):
    monkeypatch.setattr(planner, "create_plan", cheap)
    trip = make_trip(client, db, auth, start_offset=None, days=3)
    d1 = day_rows(db, trip)[0]
    item = items_of(db, d1)[0]
    item.visited = True
    db.add(Expense(trip_id=trip.id, amount=1000, itinerary_item_id=item.id))
    db.flush()
    d1_items = [i.id for i in items_of(db, d1)]

    r = client.post("/itinerary/{}/regenerate".format(trip.id), headers=auth.headers,
                    json={"changes": {"budget_total": 6000, "instructions": "cheaper"}})
    assert r.status_code == 200
    days = r.json()["days"]
    assert [i["id"] for i in days[0]["items"]] == [str(x) for x in d1_items]   # day 1 untouched
    assert days[0]["items"][0]["visited"] is True and days[0]["items"][0]["actual_cost"] == 1000
    assert [i["place_name"] for i in days[1]["items"]] == ["Free Walk"] and len(days) == 3
    assert db.get(Trip, trip.id).budget_total == 6000


def test_replan_can_extend_the_trip_after_it_has_started(client, db, auth, monkeypatch):
    seen = {}

    def spy(slots, attempts=2):
        seen.update(slots)
        return cheap(slots)

    monkeypatch.setattr(planner, "create_plan", spy)
    trip = make_trip(client, db, auth, start_offset=-1, days=2)
    r = client.post("/itinerary/{}/regenerate".format(trip.id), headers=auth.headers, json={"changes": {"days_count": 4}})
    assert r.status_code == 200 and len(r.json()["days"]) == 4
    assert seen["days_count"] == 3 and seen["budget_total"] == 15000   # nothing spent yet, 3 days left to fill
    assert r.json()["days"][3]["date"] == (TODAY + timedelta(days=2)).isoformat()


def test_replan_cannot_shrink_below_days_that_already_started(client, db, auth, monkeypatch):
    monkeypatch.setattr(planner, "create_plan", cheap)
    trip = make_trip(client, db, auth, start_offset=-2, days=4)  # days 1-2 are over
    r = client.post("/itinerary/{}/regenerate".format(trip.id), headers=auth.headers, json={"changes": {"days_count": 2}})
    assert r.status_code == 422 and "already started" in r.json()["detail"]
    assert len(client.get("/itinerary/{}".format(trip.id), headers=auth.headers).json()["days"]) == 4


def test_full_replan_when_nothing_has_started_still_rebuilds_everything(client, db, auth, monkeypatch):
    monkeypatch.setattr(planner, "create_plan", cheap)
    trip = make_trip(client, db, auth, start_offset=10, days=2)
    r = client.post("/itinerary/{}/regenerate".format(trip.id), headers=auth.headers, json={"changes": {"budget_total": 5000}})
    assert [i["place_name"] for d in r.json()["days"] for i in d["items"]] == ["Free Walk", "Free Walk"]


# ---------- assistant ----------

def test_assistant_can_move_the_trip_dates(client, db, auth):
    trip = make_trip(client, db, auth, start_offset=2, days=2)
    out = assistant.Outcome()
    new_start = TODAY + timedelta(days=40)
    text, is_error = assistant._run_tool(db, trip, "set_trip_dates", {"start_date": new_start.isoformat()}, out)
    assert not is_error and out.actions == ["set_trip_dates"] and out.itinerary_changed
    assert [d.date for d in day_rows(db, trip)] == [new_start, new_start + timedelta(days=1)]
    text, is_error = assistant._run_tool(db, trip, "set_trip_dates", {"start_date": "soon"}, assistant.Outcome())
    assert is_error


def test_assistant_system_prompt_knows_today_and_the_trip_dates(client, db, auth):
    trip = make_trip(client, db, auth, start_offset=2, days=2)
    prompt = assistant._system_prompt(db, trip)
    assert dates.pretty(TODAY) in prompt and dates.pretty(TODAY + timedelta(days=2)) in prompt


# ---------- chat slot rules ----------

def test_merge_slots_rejects_past_dates_and_accepts_undecided():
    past = (TODAY - timedelta(days=1)).isoformat()
    slots, changed, errors = merge_slots({}, llm.Extraction(start_date=past))
    assert "start_date" not in slots and errors and "passed" in errors[0]

    _, _, errors = merge_slots({}, llm.Extraction(start_date="banana"))
    assert errors and "couldn't read" in errors[0]

    slots, changed, errors = merge_slots({}, llm.Extraction(dates_undecided=True))
    assert slots["start_date"] == dates.UNDECIDED and changed == {"start_date": dates.UNDECIDED} and not errors

    slots, changed, _ = merge_slots({}, llm.Extraction(start_date=TODAY.isoformat()))  # today is allowed
    assert slots["start_date"] == TODAY.isoformat()


def test_chat_can_create_an_undated_trip(client, auth, fake_llm):
    sid = str(uuid.uuid4())
    fake_llm.extractions = [
        llm.Extraction(destination="Goa", budget_total=9000, days_count=2, dates_undecided=True, preferences=["food"]),
        llm.Extraction(is_confirmation=True),
    ]
    first = client.post("/chat", headers=auth.headers, json={"session_id": sid, "message": "goa 9k 2 days, dates not sure"}).json()
    assert "Not fixed yet" in first["reply_text"]
    second = client.post("/chat", headers=auth.headers, json={"session_id": sid, "message": "yes"}).json()
    trip = client.get("/trips/" + second["trip_id"], headers=auth.headers).json()
    assert trip["start_date"] is None and trip["phase"] == "undated"


def test_chat_history_endpoint_reports_the_next_field(client, auth):
    sid = str(uuid.uuid4())
    assert client.get("/chat/" + sid, headers=auth.headers).json()["next_field"] == "destination"
