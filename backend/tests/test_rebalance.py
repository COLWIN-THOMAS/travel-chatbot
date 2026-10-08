import uuid

from app.models.day import Day
from app.models.expense import Expense
from app.models.itinerary_item import ItineraryItem
from app.models.trip import Trip
from app.services import rebalance
from tests.conftest import sample_plan


def cheap_plan(days_count):
    """A plan whose items cost far less than sample_plan's, so the planner stub can prove it
    actually built something cheaper for the remaining days."""
    items = lambda: [
        __import__("app.services.planner", fromlist=["PlannedItem"]).PlannedItem(
            place_name="Free Beach Walk", category="attraction", estimated_cost=0
        ),
        __import__("app.services.planner", fromlist=["PlannedItem"]).PlannedItem(
            place_name="Budget Thali", category="restaurant", estimated_cost=50
        ),
    ]
    PlannedDay = __import__("app.services.planner", fromlist=["PlannedDay"]).PlannedDay
    ItineraryPlan = __import__("app.services.planner", fromlist=["ItineraryPlan"]).ItineraryPlan
    return ItineraryPlan(days=[PlannedDay(day_number=d, items=items()) for d in range(1, days_count + 1)])


def visit(db, item_id):
    item = db.get(ItineraryItem, item_id)
    item.visited = True
    db.flush()


def spend(db, trip_id, amount, item_id=None):
    db.add(Expense(trip_id=trip_id, amount=amount, itinerary_item_id=item_id))
    db.flush()


def get_trip(db, trip_id):
    return db.get(Trip, uuid.UUID(trip_id))


def days_of(db, trip_id):
    return db.query(Day).filter(Day.trip_id == trip_id).order_by(Day.day_number).all()


def test_no_rebalance_when_within_budget(db, trip):
    t = get_trip(db, trip.id)
    spend(db, t.id, 100)  # well within the 15000 budget / 5100 planned total
    assert rebalance.maybe_rebalance(db, t) is None


def test_rebalances_only_future_days_when_overspent(db, trip, monkeypatch):
    from app.services import planner

    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: cheap_plan(slots["days_count"]))
    t = get_trip(db, trip.id)
    before = days_of(db, t.id)
    # lock day 1 by visiting one of its items, then blow almost the whole budget on it
    day1_items = db.query(ItineraryItem).filter(ItineraryItem.day_id == before[0].id).all()
    visit(db, day1_items[0].id)
    spend(db, t.id, 14900, item_id=day1_items[0].id)  # only 100 left for days 2 (sample_plan plans ~1550/day)

    notice = rebalance.maybe_rebalance(db, t)
    assert notice is not None and notice.rebalanced
    assert notice.days_from == 2 and notice.days_to == 2
    assert "Days 1-1 are unchanged" in notice.message

    after = days_of(db, t.id)
    assert len(after) == 2
    assert after[0].id == before[0].id  # day 1 itself untouched (same row)
    day1_after_items = db.query(ItineraryItem).filter(ItineraryItem.day_id == after[0].id).all()
    assert {i.id for i in day1_after_items} == {i.id for i in day1_items}  # same items, nothing deleted
    visited_item = next(i for i in day1_after_items if i.id == day1_items[0].id)
    assert visited_item.visited is True  # visited flag preserved on the one we marked

    day2_items = db.query(ItineraryItem).filter(ItineraryItem.day_id == after[1].id).all()
    assert {i.place_name for i in day2_items} == {"Free Beach Walk", "Budget Thali"}  # replaced with the cheap plan
    assert sum(float(i.estimated_cost) for i in day2_items) <= 100


def test_no_days_started_yet_still_rebalances_from_day_one(db, trip, monkeypatch):
    from app.services import planner

    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: cheap_plan(slots["days_count"]))
    t = get_trip(db, trip.id)
    spend(db, t.id, 14980)  # nothing visited yet, but almost nothing left for either day

    notice = rebalance.maybe_rebalance(db, t)
    assert notice is not None and notice.rebalanced
    assert notice.days_from == 1 and notice.days_to == 2
    assert "unchanged" not in notice.message  # nothing was locked, so no such claim is made

    after = days_of(db, t.id)
    assert len(after) == 2
    for d in after:
        items = db.query(ItineraryItem).filter(ItineraryItem.day_id == d.id).all()
        assert {i.place_name for i in items} == {"Free Beach Walk", "Budget Thali"}


def test_trip_fully_locked_returns_none(db, trip):
    t = get_trip(db, trip.id)
    for d in days_of(db, t.id):
        for i in db.query(ItineraryItem).filter(ItineraryItem.day_id == d.id).all():
            visit(db, i.id)
    spend(db, t.id, 14999)
    assert rebalance.maybe_rebalance(db, t) is None  # no remaining days to touch


def test_replan_failure_leaves_everything_untouched_and_reports_it(db, trip, monkeypatch):
    from app.services import planner

    def boom(slots, attempts=2):
        raise planner.PlanError("nothing fits")

    monkeypatch.setattr(planner, "create_plan", boom)
    t = get_trip(db, trip.id)
    before_ids = [d.id for d in days_of(db, t.id)]
    spend(db, t.id, 14990)

    notice = rebalance.maybe_rebalance(db, t)
    assert notice is not None and notice.rebalanced is False
    assert "couldn't" in notice.message or "isn't enough" in notice.message

    after_ids = [d.id for d in days_of(db, t.id)]
    assert after_ids == before_ids  # nothing was deleted or replaced


def test_tiny_shortfall_from_rounding_is_ignored(db, trip):
    t = get_trip(db, trip.id)
    # sample_plan's 2-day total is 2*(800+0+250+300)=2700; spend right up to a sub-rupee shortfall
    spend(db, t.id, 15000 - 2700 + 0.5)
    assert rebalance.maybe_rebalance(db, t) is None


def test_visit_endpoint_triggers_rebalance_and_returns_notice(client, auth, trip, db, monkeypatch):
    from app.services import planner

    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: cheap_plan(slots["days_count"]))
    t = get_trip(db, trip.id)
    day1 = days_of(db, t.id)[0]
    first_item = db.query(ItineraryItem).filter(ItineraryItem.day_id == day1.id).first()
    spend(db, t.id, 14950)
    db.commit()

    r = client.post(
        f"/tracker/{trip.id}/visit",
        headers=auth.headers,
        json={"itinerary_item_id": str(first_item.id), "visited": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["visited"] is True
    assert body["itinerary_notice"] is not None and body["itinerary_notice"]["rebalanced"] is True

    days = client.get("/itinerary/" + trip.id, headers=auth.headers).json()["days"]
    assert len(days) == 2
    assert {i["place_name"] for i in days[1]["items"]} == {"Free Beach Walk", "Budget Thali"}


def test_expense_endpoint_triggers_rebalance_and_returns_notice(client, auth, trip, db, monkeypatch):
    from app.services import planner

    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: cheap_plan(slots["days_count"]))
    t = get_trip(db, trip.id)
    day1 = days_of(db, t.id)[0]
    first_item = db.query(ItineraryItem).filter(ItineraryItem.day_id == day1.id).first()
    visit(db, first_item.id)
    db.commit()

    r = client.post(
        f"/tracker/{trip.id}/expense",
        headers=auth.headers,
        json={"amount": 14950, "category": "stay", "itinerary_item_id": str(first_item.id)},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["itinerary_notice"] is not None and body["itinerary_notice"]["rebalanced"] is True
    assert body["itinerary_notice"]["days_from"] == 2

    item_still_there = client.get("/trips/" + trip.id, headers=auth.headers).json()
    day1_item = item_still_there["days"][0]["items"][0]
    assert day1_item["id"] == str(first_item.id)  # day 1 (locked) untouched by the API-level call too


def test_expense_endpoint_without_shortfall_returns_no_notice(client, auth, trip):
    r = client.post(f"/tracker/{trip.id}/expense", headers=auth.headers, json={"amount": 50})
    assert r.status_code == 201
    assert r.json()["itinerary_notice"] is None


def test_assistant_tool_relays_rebalance_notice(db, auth, trip, monkeypatch):
    from app.services import assistant, llm, planner
    from app.models.trip import Trip as TripModel
    from types import SimpleNamespace as NS

    monkeypatch.setattr(planner, "create_plan", lambda slots, attempts=2: cheap_plan(slots["days_count"]))
    t = get_trip(db, trip.id)
    day1 = days_of(db, t.id)[0]
    first_item = db.query(ItineraryItem).filter(ItineraryItem.day_id == day1.id).first()
    visit(db, first_item.id)
    db.commit()

    def block_tool(name, args, id_="tu_1"):
        return NS(type="tool_use", id=id_, name=name, input=args)

    def resp(stop, *blocks):
        return NS(stop_reason=stop, content=list(blocks))

    class FakeClient:
        def __init__(self, *responses):
            self.responses, self.requests = list(responses), []
            self.messages = NS(create=self._create)

        def _create(self, **kw):
            self.requests.append(kw)
            return self.responses.pop(0)

    fake = FakeClient(
        resp("tool_use", block_tool("log_expense", {"amount": 14950, "category": "stay"})),
        resp("end_turn", NS(type="text", text="Logged it, and I had to tweak tomorrow's plan to fit.")),
    )
    monkeypatch.setattr(llm, "get_client", lambda: fake)

    reply, outcome = assistant.handle(db, t, [], "spent 14950 on the hotel")
    assert "tweak" in reply
    assert "auto_rebalance" in outcome.actions and outcome.itinerary_changed is True
    sent_tool_result = fake.requests[1]["messages"][-1]["content"][0]["content"]
    assert "itinerary_notice" in sent_tool_result
