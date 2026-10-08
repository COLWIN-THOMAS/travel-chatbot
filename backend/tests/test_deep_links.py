from urllib.parse import parse_qs, urlparse

from app.services import deep_links


class TestUber:
    def test_builds_both_app_and_web_links_with_coordinates(self):
        r = deep_links.uber_ride(15.30, 73.80, "Beachfront Hostel", 15.35, 73.85, "Old Fort")
        assert r["prefilled"] is True
        assert r["app_url"].startswith("uber://riderequest?")
        assert r["web_url"].startswith("https://m.uber.com/looking?")

    def test_app_url_params_round_trip(self):
        r = deep_links.uber_ride(15.30, 73.80, "Hotel", 15.35, 73.85, "Fort")
        q = parse_qs(urlparse(r["app_url"]).query)
        assert q["pickup[latitude]"] == ["15.3"] and q["dropoff[longitude]"] == ["73.85"]
        assert q["action"] == ["setPickup"]

    def test_web_url_carries_json_locations(self):
        import json
        r = deep_links.uber_ride(15.30, 73.80, "Hotel", 15.35, 73.85, "Fort")
        q = parse_qs(urlparse(r["web_url"]).query)
        pickup = json.loads(q["pickup"][0])
        assert pickup["latitude"] == 15.30 and pickup["addressLine1"] == "Hotel"

    def test_long_labels_are_truncated_not_rejected(self):
        r = deep_links.uber_ride(0, 0, "X" * 500, 0, 0, "Y" * 500)
        assert r["app_url"] is not None  # no exception, still a valid link


class TestBooking:
    def test_builds_a_prefilled_search_with_no_separate_app_scheme(self):
        r = deep_links.booking_hotels("Goa", "2026-11-15", "2026-11-18", adults=2)
        assert r["prefilled"] is True
        assert r["app_url"] is None
        assert r["web_url"].startswith("https://www.booking.com/searchresults.html?")

    def test_params_present_and_correct(self):
        r = deep_links.booking_hotels("Jaipur, Rajasthan", "2026-12-01", "2026-12-03")
        q = parse_qs(urlparse(r["web_url"]).query)
        assert q["ss"] == ["Jaipur, Rajasthan"]
        assert q["checkin"] == ["2026-12-01"] and q["checkout"] == ["2026-12-03"]
        assert q["group_adults"] == ["1"]

    def test_destination_is_url_escaped(self):
        r = deep_links.booking_hotels("São Paulo & Region", "2026-01-01", "2026-01-02")
        assert "São Paulo & Region" not in r["web_url"]  # raw ampersand/unicode must be encoded
        assert "%26" in r["web_url"] or "+" in r["web_url"]


class TestHonestFallbacks:
    """Rapido and IRCTC have no publicly documented deep-link / prefill scheme - these must say
    so (prefilled=False, no app_url) rather than fabricate one that would silently fail on a
    real phone."""

    def test_rapido_has_no_fabricated_scheme(self):
        r = deep_links.rapido_ride("Hotel", "Fort")
        assert r["app_url"] is None and r["prefilled"] is False
        assert r["web_url"] == "https://rapido.bike/"

    def test_irctc_has_no_fabricated_prefill(self):
        r = deep_links.irctc_train_search("NDLS", "BCT", "2026-11-15")
        assert r["app_url"] is None and r["prefilled"] is False
        assert "irctc.co.in" in r["web_url"]


class TestUberRideTo:
    def test_uses_my_location_shortcut_for_pickup(self):
        from app.services import deep_links
        r = deep_links.uber_ride_to(15.30, 73.80, "Baga Beach")
        assert "pickup=my_location" in r["app_url"]
        assert "dropoff%5Blatitude%5D=15.3" in r["app_url"]
        assert "pickup" not in parse_qs(urlparse(r["web_url"]).query)  # web asks the user instead
