import uuid

from tests.conftest import register


def item_ids(client, auth, trip_id):
    days = client.get("/itinerary/" + trip_id, headers=auth.headers).json()["days"]
    return [i for d in days for i in d["items"]]


def test_create_list_get_trip(client, auth, trip):
    assert client.get("/trips", headers=auth.headers).json()[0]["id"] == trip.id
    body = client.get("/trips/" + trip.id, headers=auth.headers).json()
    assert body["destination"] == "Goa" and len(body["days"]) == 2
    assert [i["order_in_day"] for i in body["days"][0]["items"]] == [1, 2, 3, 4]
    assert body["status"] == "active"


def test_trip_validation(client, auth):
    bad = {"destination": "Goa", "budget_total": 0, "days_count": 3}
    assert client.post("/trips", headers=auth.headers, json=bad).status_code == 422
    bad = {"destination": "Goa", "budget_total": 100, "days_count": 99}
    assert client.post("/trips", headers=auth.headers, json=bad).status_code == 422


def test_other_users_cannot_see_or_touch_trip(client, trip):
    other, _ = register(client)
    for method, url in [("get", "/trips/" + trip.id), ("get", "/tracker/" + trip.id),
                        ("get", "/itinerary/" + trip.id), ("delete", "/trips/" + trip.id)]:
        assert getattr(client, method)(url, headers=other).status_code == 404
    assert client.get("/trips", headers=other).json() == []


def test_unknown_or_malformed_trip_id(client, auth):
    assert client.get("/trips/" + str(uuid.uuid4()), headers=auth.headers).status_code == 404
    assert client.get("/trips/not-a-uuid", headers=auth.headers).status_code == 422


def test_expense_flow_and_derived_totals(client, auth, trip):
    first = item_ids(client, auth, trip.id)[0]
    r = client.post(f"/tracker/{trip.id}/expense", headers=auth.headers,
                    json={"amount": 500, "category": "stay", "itinerary_item_id": first["id"]})
    assert r.status_code == 201
    assert r.json()["spend_total"] == 500 and r.json()["budget_remaining"] == 14500
    client.post(f"/tracker/{trip.id}/expense", headers=auth.headers, json={"amount": 100.5, "category": "food"})

    s = client.get("/tracker/" + trip.id, headers=auth.headers).json()
    assert s["spend_total"] == 600.5 and s["remaining"] == 14399.5
    assert s["percent_used"] == round(600.5 / 15000 * 100, 1)
    assert s["spent_by_category"] == {"stay": 500.0, "food": 100.5}

    days = client.get("/itinerary/" + trip.id, headers=auth.headers).json()["days"]
    assert days[0]["items"][0]["actual_cost"] == 500 and days[0]["spend_so_far"] == 500


def test_mark_visited_updates_progress(client, auth, trip):
    items = item_ids(client, auth, trip.id)
    r = client.post(f"/tracker/{trip.id}/visit", headers=auth.headers,
                    json={"itinerary_item_id": items[1]["id"], "visited": True})
    assert r.status_code == 200 and r.json()["visited"] is True
    s = client.get("/tracker/" + trip.id, headers=auth.headers).json()
    assert s["items_total"] == 8 and s["items_visited"] == 1
    client.post(f"/tracker/{trip.id}/visit", headers=auth.headers,
                json={"itinerary_item_id": items[1]["id"], "visited": False})
    assert client.get("/tracker/" + trip.id, headers=auth.headers).json()["items_visited"] == 0


def test_expense_validation(client, auth, trip):
    url = f"/tracker/{trip.id}/expense"
    assert client.post(url, headers=auth.headers, json={"amount": -5}).status_code == 422
    assert client.post(url, headers=auth.headers, json={"amount": 0}).status_code == 422
    foreign = {"amount": 10, "itinerary_item_id": str(uuid.uuid4())}
    assert client.post(url, headers=auth.headers, json=foreign).status_code == 404


def test_cannot_link_expense_to_another_trips_item(client, auth, trip):
    other = client.post("/trips", headers=auth.headers,
                        json={"destination": "Delhi", "budget_total": 5000, "days_count": 1}).json()
    item = item_ids(client, auth, trip.id)[0]
    r = client.post(f"/tracker/{other['id']}/expense", headers=auth.headers,
                    json={"amount": 10, "itinerary_item_id": item["id"]})
    assert r.status_code == 404


def test_delete_expense(client, auth, trip):
    e = client.post(f"/tracker/{trip.id}/expense", headers=auth.headers, json={"amount": 40}).json()["expense"]
    assert client.delete(f"/tracker/{trip.id}/expense/{e['id']}", headers=auth.headers).status_code == 204
    assert client.get("/tracker/" + trip.id, headers=auth.headers).json()["spend_total"] == 0


def test_delete_trip_cascades(client, auth, trip):
    assert client.delete("/trips/" + trip.id, headers=auth.headers).status_code == 204
    assert client.get("/trips/" + trip.id, headers=auth.headers).status_code == 404
