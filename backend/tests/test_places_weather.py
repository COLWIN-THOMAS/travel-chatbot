from urllib.parse import parse_qs, urlparse

from app.services import google_places, weather

RAW_SEARCH = [
    {"id": "ChIJabcdefghij1", "displayName": {"text": "Thalassa"}, "rating": 4.2,
     "priceLevel": "PRICE_LEVEL_VERY_EXPENSIVE", "formattedAddress": "Siolim, Goa"},
    {"id": "ChIJabcdefghij2", "displayName": {"text": "Bomras"}},
]
PHOTO = "places/ChIJabcdefghij1/photos/AbC_123-x"
RAW_DETAIL = {
    "id": "ChIJabcdefghij1", "displayName": {"text": "Thalassa"}, "rating": 4.2,
    "priceLevel": "PRICE_LEVEL_MODERATE", "currentOpeningHours": {"weekdayDescriptions": ["Mon: 9-1"]},
    "photos": [{"name": PHOTO}, {"name": "bad name with spaces"}],
    "reviews": [{"rating": 5, "text": {"text": "Great"}, "authorAttribution": {"displayName": "Sam"}}, {"rating": 3}],
    "editorialSummary": {"text": "Greek taverna"},
}


def test_places_list_maps_google_fields(client, auth, trip, monkeypatch):
    monkeypatch.setattr(google_places, "search_places", lambda dest, cat: RAW_SEARCH)
    r = client.get(f"/places/{trip.id}?category=restaurant", headers=auth.headers)
    assert r.status_code == 200
    first, second = r.json()["places"]
    assert first["price_level"] == "Very Expensive" and first["category"] == "restaurant"
    assert second["price_level"] is None and second["rating"] is None


def test_places_list_validates_category_and_ownership(client, auth, trip):
    from tests.conftest import register
    assert client.get(f"/places/{trip.id}?category=spa", headers=auth.headers).status_code == 422
    other, _ = register(client)
    assert client.get(f"/places/{trip.id}?category=hotel", headers=other).status_code == 404
    assert client.get(f"/places/{trip.id}?category=hotel").status_code == 401


def test_places_upstream_failure_is_502(client, auth, trip, monkeypatch):
    def boom(d, c):
        raise google_places.PlacesError("Places search failed")

    monkeypatch.setattr(google_places, "search_places", boom)
    assert client.get(f"/places/{trip.id}?category=hotel", headers=auth.headers).status_code == 502


def test_place_detail_signs_photos_and_hides_api_key(client, auth, monkeypatch):
    monkeypatch.setattr(google_places, "get_place_details", lambda pid: RAW_DETAIL)
    r = client.get("/places/detail/ChIJabcdefghij1", headers=auth.headers)
    body = r.json()
    assert r.status_code == 200 and body["description"] == "Greek taverna"
    assert len(body["photos"]) == 1  # malformed reference dropped
    assert body["reviews"][1]["text"] is None
    assert "key=" not in body["photos"][0] and "AIza" not in r.text


def test_signed_photo_url_serves_image_and_rejects_tampering(client, auth, monkeypatch):
    monkeypatch.setattr(google_places, "get_place_details", lambda pid: RAW_DETAIL)
    monkeypatch.setattr(google_places, "fetch_photo", lambda name, w: (b"\xff\xd8jpeg", "image/jpeg"))
    url = client.get("/places/detail/ChIJabcdefghij1", headers=auth.headers).json()["photos"][0]

    ok = client.get(url)  # no auth header needed: the signature is the credential
    assert ok.status_code == 200 and ok.content == b"\xff\xd8jpeg" and ok.headers["content-type"] == "image/jpeg"

    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert client.get("/places/photo", params={**q, "w": 1200}).status_code == 403
    assert client.get("/places/photo", params={**q, "sig": "0" * 64}).status_code == 403
    assert client.get("/places/photo", params={**q, "name": "places/x/photos/y"}).status_code == 403
    assert client.get("/places/photo", params={"name": PHOTO}).status_code == 403


def test_place_id_and_photo_name_are_validated_before_use():
    import pytest
    with pytest.raises(google_places.PlacesError):
        google_places.get_place_details("../../etc/passwd")
    with pytest.raises(google_places.PlacesError):
        google_places.fetch_photo("places/x/photos/../../y", 800)


def test_weather_codes_and_advisories():
    assert weather.describe_code(0) == ("Clear sky", "sun")
    assert weather.describe_code(63)[1] == "rain" and weather.describe_code(96)[1] == "storm"
    assert "umbrella" in weather.advisory(61, 28, 22, 20)
    assert "umbrella" in weather.advisory(1, 28, 22, 80)
    assert "hot" in weather.advisory(0, 39, 28, 0).lower()
    assert "warm" in weather.advisory(0, 12, 4, 0).lower()
    assert weather.advisory(0, 27, 20, 10) == "Good day for sightseeing."


NOMINATIM_GOA = [{"name": "Goa", "lat": "15.30", "lon": "74.08", "display_name": "Goa, India"}]


def _fake_get(calls=None, geo=NOMINATIM_GOA):
    def fake_get(url, params, headers=None):
        if calls is not None:
            calls.append((url, dict(params), headers))
        if "nominatim" in url:
            return geo(params) if callable(geo) else geo
        return {"daily": {"time": ["2026-09-25", "2026-09-26"], "weathercode": [0, 63],
                          "temperature_2m_max": [31.0, 27.5], "temperature_2m_min": [24.0, 23.0],
                          "precipitation_probability_max": [5, 80]}}
    return fake_get


def _reset_weather_caches():
    weather._cache.clear()
    weather._geo_cache.clear()


def test_weather_endpoint(client, auth, trip, monkeypatch):
    _reset_weather_caches()
    calls = []
    monkeypatch.setattr(weather, "_get_json", _fake_get(calls))
    r = client.get("/weather/" + trip.id, headers=auth.headers)
    assert r.status_code == 200
    body = r.json()
    assert body["destination"] == "Goa"
    assert [d["day_number"] for d in body["days"]] == [1, 2] and body["days"][1]["condition"] == "Rain"
    assert "umbrella" in body["days"][1]["advisory"]
    forecast_call = [c for c in calls if "open-meteo" in c[0]][0]
    assert forecast_call[1]["latitude"] == 15.30 and forecast_call[1]["longitude"] == 74.08
    geo_call = [c for c in calls if "nominatim" in c[0]][0]
    assert geo_call[1]["q"] == "Goa" and "BudgetTravelChatbot" in geo_call[2]["User-Agent"]


def test_geocode_caches_by_normalised_destination(monkeypatch):
    _reset_weather_caches()
    calls = []
    paris = [{"name": "Paris", "lat": "48.85", "lon": "2.35", "display_name": "Paris, France"}]
    monkeypatch.setattr(weather, "_get_json", _fake_get(calls, geo=paris))
    assert weather.geocode("Paris")["latitude"] == 48.85
    weather.geocode(" paris ")
    assert len(calls) == 1


def test_weather_unknown_place_is_502(client, auth, trip, monkeypatch):
    _reset_weather_caches()
    monkeypatch.setattr(weather, "_get_json", _fake_get(geo=[]))
    assert client.get("/weather/" + trip.id, headers=auth.headers).status_code == 502


def test_places_list_includes_coordinates(client, auth, trip, monkeypatch):
    raw_with_loc = [{**RAW_SEARCH[0], "location": {"latitude": 15.3, "longitude": 73.8}}]
    monkeypatch.setattr(google_places, "search_places", lambda dest, cat: raw_with_loc)
    r = client.get(f"/places/{trip.id}?category=restaurant", headers=auth.headers)
    place = r.json()["places"][0]
    assert place["lat"] == 15.3 and place["lon"] == 73.8


def test_place_detail_includes_coordinates(client, auth, monkeypatch):
    detail_with_loc = {**RAW_DETAIL, "location": {"latitude": 15.3005, "longitude": 73.8012}}
    monkeypatch.setattr(google_places, "get_place_details", lambda pid: detail_with_loc)
    r = client.get("/places/detail/ChIJabcdefghij1", headers=auth.headers)
    body = r.json()
    assert body["lat"] == 15.3005 and body["lon"] == 73.8012


def test_ride_link_endpoint(client, auth, monkeypatch):
    detail_with_loc = {**RAW_DETAIL, "location": {"latitude": 15.3, "longitude": 73.8}}
    monkeypatch.setattr(google_places, "get_place_details", lambda pid: detail_with_loc)
    r = client.get("/places/detail/ChIJabcdefghij1/ride-link", headers=auth.headers, params={"name": "Thalassa"})
    assert r.status_code == 200
    body = r.json()
    assert body["uber"]["app_url"].startswith("uber://riderequest")
    assert "pickup=my_location" in body["uber"]["app_url"]
    assert body["rapido"]["app_url"] is None


def test_ride_link_without_location_is_422(client, auth, monkeypatch):
    monkeypatch.setattr(google_places, "get_place_details", lambda pid: RAW_DETAIL)  # no location key
    r = client.get("/places/detail/ChIJabcdefghij1/ride-link", headers=auth.headers, params={"name": "Thalassa"})
    assert r.status_code == 422


def test_ride_link_requires_auth(client):
    assert client.get("/places/detail/x/ride-link", params={"name": "y"}).status_code == 401
