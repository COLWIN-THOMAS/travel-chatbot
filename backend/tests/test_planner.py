import pytest

from app.services import planner
from tests.conftest import sample_plan

SLOTS = {"destination": "Goa", "budget_total": 15000.0, "days_count": 2, "preferences": ["food"]}


def test_validate_plan_accepts_good_plan():
    assert planner.validate_plan(sample_plan(2), 2, 15000) == []


def test_validate_plan_flags_budget_day_count_and_negative_cost():
    plan = sample_plan(2)
    assert any("exceeds" in p for p in planner.validate_plan(plan, 2, 1000))
    assert any("exactly days" in p for p in planner.validate_plan(plan, 3, 15000))
    plan.days[0].items[0].estimated_cost = -1
    assert any("negative" in p for p in planner.validate_plan(plan, 2, 15000))


def test_create_plan_retries_once_with_feedback(monkeypatch):
    calls = []
    too_expensive = sample_plan(2)
    too_expensive.days[0].items[0].estimated_cost = 99999

    def fake_request(slots, candidates, feedback):
        calls.append(feedback)
        return too_expensive if len(calls) == 1 else sample_plan(2)

    monkeypatch.setattr(planner, "_request_plan", fake_request)
    monkeypatch.setattr(planner, "gather_candidates", lambda d: "")
    plan = planner.create_plan(SLOTS)
    assert calls[0] is None and "exceeds" in calls[1]
    assert planner.plan_total(plan) <= 15000


def test_create_plan_gives_up_after_retries(monkeypatch):
    bad = sample_plan(2)
    bad.days[0].items[0].estimated_cost = 99999
    monkeypatch.setattr(planner, "_request_plan", lambda *a: bad)
    monkeypatch.setattr(planner, "gather_candidates", lambda d: "")
    with pytest.raises(planner.PlanError):
        planner.create_plan(SLOTS)


def test_save_plan_replaces_existing_itinerary(client, db, auth, trip):
    from app.models.trip import Trip
    import uuid
    t = db.get(Trip, uuid.UUID(trip.id))
    planner.save_plan(db, t, sample_plan(3))
    db.flush()
    days = client.get("/itinerary/" + trip.id, headers=auth.headers).json()["days"]
    assert [d["day_number"] for d in days] == [1, 2, 3]


def test_gather_candidates_survives_places_outage(monkeypatch):
    from app.services import google_places

    def boom(dest, cat):
        raise google_places.PlacesError("down")

    monkeypatch.setattr(google_places, "search_places", boom)
    assert "no candidate list" in planner.gather_candidates("Goa")


def test_regenerate_endpoint(client, auth, trip, monkeypatch):
    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: sample_plan(slots["days_count"]))
    r = client.post(f"/itinerary/{trip.id}/regenerate", headers=auth.headers,
                    json={"changes": {"days_count": 3, "budget_total": 20000}})
    assert r.status_code == 200 and len(r.json()["days"]) == 3
    t = client.get("/trips/" + trip.id, headers=auth.headers).json()
    assert t["days_count"] == 3 and t["budget_total"] == 20000


def test_regenerate_reports_infeasible_budget(client, auth, trip, monkeypatch):
    def boom(slots, attempts=2):
        raise planner.PlanError("too tight")

    monkeypatch.setattr(planner, "create_plan", boom)
    r = client.post(f"/itinerary/{trip.id}/regenerate", headers=auth.headers, json={"changes": {"budget_total": 10}})
    assert r.status_code == 422
    assert len(client.get("/itinerary/" + trip.id, headers=auth.headers).json()["days"]) == 2  # untouched
