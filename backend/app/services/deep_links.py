"""Builds deep links out to external booking/ride apps for a place or trip. Each link opens the
app if installed, or its mobile site otherwise (the OS handles that fallback automatically for a
registered https:// universal link; app:// scheme links are paired with an explicit web fallback
URL the caller can offer if the scheme link does nothing).

Provenance (checked at build time, not guessed):
- Uber: documented at developer.uber.com/docs/riders/ride-requests/tutorials/deep-links -
  `uber://riderequest` (native) and `https://m.uber.com/looking` (universal link), both with
  pickup/dropoff as nested lat/lon params. No client_id is sent here (that's only required for
  Uber's OAuth ride-booking flow; opening the app with a prefilled destination works without it).
- Booking.com: `https://www.booking.com/searchresults.html?ss=...&checkin=...&checkout=...` is
  Booking.com's own public search URL (what its search box produces) - a stable, widely used
  pattern, not from Booking's partner API docs (that page returned 404 when checked). No separate
  `booking://` scheme is used here - Booking.com's app registers as an Android App Link / iOS
  Universal Link for this same https:// URL, so the one link opens the app if installed and the
  mobile site otherwise; there is nothing to independently verify as a custom scheme.
- IRCTC: no public URL scheme for pre-filling a search is published anywhere findable; IRCTC's
  search is a client-side form, not a GET-parameterised page. The link here opens the train
  search page itself with nothing pre-filled - documented as a known limitation, not guessed.
- Rapido: no public deep-link scheme is documented or discoverable. The link here opens Rapido's
  website; there is no app:// link to offer.

Every function returns {"app_url": str | None, "web_url": str, "prefilled": bool} so the caller
(and the UI) can tell a genuine deep link from a plain "open the site and search yourself" link.
"""
from typing import Optional
from urllib.parse import quote, urlencode


def _json_loc(lat: float, lon: float, label: str) -> str:
    # Uber's documented location object shape, URL-safe JSON.
    import json
    return json.dumps({"latitude": lat, "longitude": lon, "addressLine1": label[:100]})


def uber_ride(pickup_lat: float, pickup_lon: float, pickup_label: str,
              drop_lat: float, drop_lon: float, drop_label: str) -> dict:
    """Both pickup and dropoff fixed to known points."""
    pickup = _json_loc(pickup_lat, pickup_lon, pickup_label)
    drop = _json_loc(drop_lat, drop_lon, drop_label)
    app_params = {
        "action": "setPickup",
        "pickup[latitude]": pickup_lat, "pickup[longitude]": pickup_lon, "pickup[nickname]": pickup_label[:100],
        "dropoff[latitude]": drop_lat, "dropoff[longitude]": drop_lon, "dropoff[nickname]": drop_label[:100],
    }
    web_params = {"pickup": pickup, "drop[0]": drop}
    return {
        "app_url": "uber://riderequest?" + urlencode(app_params, quote_via=quote),
        "web_url": "https://m.uber.com/looking?" + urlencode(web_params, quote_via=quote),
        "prefilled": True,
    }


def uber_ride_to(drop_lat: float, drop_lon: float, drop_label: str) -> dict:
    """Ride to a known destination, pickup = wherever the rider actually is. The native app
    link uses Uber's documented `pickup=my_location` shortcut; the universal web link omits
    pickup entirely (Uber's own web flow then asks for it via GPS/search)."""
    app_params = {
        "action": "setPickup", "pickup": "my_location",
        "dropoff[latitude]": drop_lat, "dropoff[longitude]": drop_lon, "dropoff[nickname]": drop_label[:100],
    }
    web_params = {"drop[0]": _json_loc(drop_lat, drop_lon, drop_label)}
    return {
        "app_url": "uber://riderequest?" + urlencode(app_params, quote_via=quote),
        "web_url": "https://m.uber.com/looking?" + urlencode(web_params, quote_via=quote),
        "prefilled": True,
    }


def rapido_ride(pickup_label: str, drop_label: str) -> dict:
    return {"app_url": None, "web_url": "https://rapido.bike/", "prefilled": False}


def irctc_train_search(origin_station_code: Optional[str] = None, destination_station_code: Optional[str] = None,
                        travel_date: Optional[str] = None) -> dict:
    return {"app_url": None, "web_url": "https://www.irctc.co.in/nget/train-search", "prefilled": False}


def booking_hotels(destination: str, checkin: str, checkout: str, adults: int = 1) -> dict:
    """`checkin`/`checkout` are YYYY-MM-DD. No separate app_url: this https:// URL is itself the
    App Link/Universal Link Booking.com's app registers for, so it opens the app directly on a
    device that has it installed, and the web search otherwise - see module docstring."""
    params = {"ss": destination, "checkin": checkin, "checkout": checkout, "group_adults": adults, "no_rooms": 1}
    web_url = "https://www.booking.com/searchresults.html?" + urlencode(params, quote_via=quote)
    return {"app_url": None, "web_url": web_url, "prefilled": True}
