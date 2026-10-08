import threading
import time
from datetime import date as date_type, timedelta
from typing import Dict, List, Optional, Tuple

import httpx

# Nominatim (OpenStreetMap) resolves regions such as "Goa"; Open-Meteo's own geocoder maps that to Genoa, Italy.
GEOCODE_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "BudgetTravelChatbot/1.0 (trip planning app)"  # required by the Nominatim usage policy
_CACHE_TTL_SECONDS = 1800
_GEOCODE_TTL_SECONDS = 24 * 3600
_cache: Dict[Tuple, Tuple[float, object]] = {}
_geo_cache: Dict[str, Tuple[float, dict]] = {}
_lock = threading.Lock()


class WeatherError(Exception):
    pass


# WMO weather codes -> (label, icon key the client maps to an emoji/icon)
def describe_code(code: int) -> Tuple[str, str]:
    if code == 0:
        return "Clear sky", "sun"
    if code in (1, 2):
        return "Partly cloudy", "partly"
    if code == 3:
        return "Overcast", "cloud"
    if code in (45, 48):
        return "Fog", "fog"
    if 51 <= code <= 57:
        return "Drizzle", "rain"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "Rain", "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "Snow", "snow"
    if code >= 95:
        return "Thunderstorm", "storm"
    return "Mixed", "cloud"


def advisory(code: int, temp_max: float, temp_min: float, rain_prob: int) -> str:
    if code >= 95:
        return "Thunderstorms likely - keep plans flexible and stay indoors if it gets rough."
    if rain_prob >= 50 or (51 <= code <= 67) or (80 <= code <= 82):
        return "Carry an umbrella or rain jacket."
    if temp_max >= 38:
        return "Very hot - hydrate often and keep midday activities indoors."
    if temp_max >= 33:
        return "Hot day - sunscreen, water and light clothes."
    if temp_min <= 8:
        return "Cold - pack warm layers."
    return "Good day for sightseeing."


def _get_json(url: str, params: dict, headers: Optional[dict] = None):
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        raise WeatherError("Weather service unavailable ({})".format(e.__class__.__name__)) from e


def geocode(destination: str) -> dict:
    """Resolve a destination to {name, latitude, longitude} using Nominatim's importance ranking
    (Goa -> the Indian state, Paris -> France, London -> UK)."""
    key = destination.strip().lower()
    now = time.time()
    with _lock:
        hit = _geo_cache.get(key)
        if hit and now - hit[0] < _GEOCODE_TTL_SECONDS:
            return hit[1]

    found = _get_json(
        GEOCODE_URL,
        {"q": destination, "format": "jsonv2", "limit": 1, "accept-language": "en"},
        headers={"User-Agent": USER_AGENT},
    )
    if not found:
        raise WeatherError("Could not locate '{}'".format(destination))
    top = found[0]
    place = {
        "name": top.get("name") or top.get("display_name", destination).split(",")[0],
        "latitude": float(top["lat"]),
        "longitude": float(top["lon"]),
    }
    with _lock:
        if len(_geo_cache) > 500:
            _geo_cache.clear()
        _geo_cache[key] = (now, place)
    return place


FORECAST_WINDOW_DAYS = 16  # the longest range Open-Meteo forecasts


def _forecast_window(destination: str) -> dict:
    """The next 16 days at the destination, cached per destination: {"destination": name, "days": [entry with date]}."""
    key = destination.strip().lower()
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]

    place = geocode(destination)

    data = _get_json(
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": FORECAST_WINDOW_DAYS,
        },
    )
    daily = data.get("daily") or {}
    out: List[dict] = []
    for i, date in enumerate(daily.get("time", [])):
        code = int(daily["weathercode"][i] or 0)
        tmax = float(daily["temperature_2m_max"][i])
        tmin = float(daily["temperature_2m_min"][i])
        prob = int(daily["precipitation_probability_max"][i] or 0)
        label, icon = describe_code(code)
        out.append(
            {
                "date": date,
                "temp_max": tmax,
                "temp_min": tmin,
                "condition": label,
                "icon": icon,
                "precipitation_probability": prob,
                "advisory": advisory(code, tmax, tmin, prob),
            }
        )
    result = {"destination": place["name"], "days": out}
    with _lock:
        if len(_cache) > 200:
            _cache.clear()
        _cache[key] = (now, result)
    return result


def forecast_for(destination: str, days: int, start_date: Optional[date_type] = None) -> dict:
    """Forecast for a trip. With a start date, Day k is matched to start_date + (k-1) by calendar date; days outside the
    16-day forecast window (too far ahead, or already over) are left out, with a note. Without dates (older trips),
    Day k maps to today + (k-1)."""
    days = max(1, min(days, 14))
    window = _forecast_window(destination)
    entries = window["days"]
    note = None

    if start_date is None:
        picked = [dict(e, day_number=i + 1) for i, e in enumerate(entries[:days])]
    else:
        by_date = {e["date"]: e for e in entries}
        picked = []
        for k in range(1, days + 1):
            e = by_date.get((start_date + timedelta(days=k - 1)).isoformat())
            if e:
                picked.append(dict(e, day_number=k))
        if len(picked) < days and entries:
            last = entries[-1]["date"]
            if start_date.isoformat() > last:
                note = "Forecasts only reach {}. Check back closer to your trip.".format(last)
            elif picked:
                note = "Forecast shown only for days within the next {} days.".format(FORECAST_WINDOW_DAYS)
            else:
                note = "No forecast available for these dates (the trip is already over)."
    return {"destination": window["destination"], "days": picked, "note": note}
