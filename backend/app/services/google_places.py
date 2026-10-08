import re
import threading
import time
from typing import Callable, Dict, List, Tuple
from urllib.parse import urlparse

import httpx

from app import config

BASE_URL = "https://places.googleapis.com/v1"

CATEGORY_QUERY_TERMS = {
    "hotel": "hotels",
    "restaurant": "restaurants",
    "attraction": "tourist attractions",
}

# Pro-tier fields only (cheaper, larger free quota). Photos/reviews live on the detail call.
# `location` (lat/lng) is Essentials-tier - no extra cost - and is what the deep-link builders need.
SEARCH_FIELD_MASK = "places.id,places.displayName,places.rating,places.priceLevel,places.formattedAddress,places.location"
DETAIL_FIELD_MASK = (
    "id,displayName,formattedAddress,location,rating,priceLevel,currentOpeningHours,"
    "websiteUri,nationalPhoneNumber,photos,reviews,editorialSummary"
)

PLACE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,300}$")
PHOTO_NAME_RE = re.compile(r"^places/[A-Za-z0-9_-]+/photos/[A-Za-z0-9_-]+$")
_ALLOWED_PHOTO_HOSTS = ("googleusercontent.com", "ggpht.com")
_MAX_PHOTO_BYTES = 5 * 1024 * 1024

# Short-lived cache only: absorbs repeated taps without retaining place content.
_CACHE_TTL_SECONDS = 600
_cache: Dict[Tuple, Tuple[float, object]] = {}
_cache_lock = threading.Lock()


class PlacesError(Exception):
    """Google Places is unreachable, misconfigured, or rejected the request."""


def _cached(key: Tuple, loader: Callable[[], object]):
    now = time.time()
    with _cache_lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _CACHE_TTL_SECONDS:
            return hit[1]
    value = loader()
    with _cache_lock:
        if len(_cache) > 500:
            _cache.clear()
        _cache[key] = (now, value)
    return value


def _headers(field_mask: str = "") -> dict:
    if not config.GOOGLE_PLACES_API_KEY:
        raise PlacesError("GOOGLE_PLACES_API_KEY is not set")
    headers = {"X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    return headers


def search_places(destination: str, category: str) -> List[dict]:
    term = CATEGORY_QUERY_TERMS.get(category, category)
    query = "{} in {}".format(term, destination)

    def load():
        try:
            resp = httpx.post(
                BASE_URL + "/places:searchText",
                headers={**_headers(SEARCH_FIELD_MASK), "Content-Type": "application/json"},
                json={"textQuery": query},
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise PlacesError("Places search failed: {}".format(e.__class__.__name__)) from e
        return resp.json().get("places", [])

    return _cached(("search", destination.strip().lower(), category), load)


def get_place_details(place_id: str) -> dict:
    if not PLACE_ID_RE.match(place_id):
        raise PlacesError("Invalid place id")

    def load():
        try:
            resp = httpx.get(
                "{}/places/{}".format(BASE_URL, place_id),
                headers=_headers(DETAIL_FIELD_MASK),
                timeout=10.0,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise PlacesError("Place details failed: {}".format(e.__class__.__name__)) from e
        return resp.json()

    return _cached(("detail", place_id), load)


def fetch_photo(name: str, width: int) -> Tuple[bytes, str]:
    """Resolve a photo reference to image bytes without ever exposing the API key to the client."""
    if not PHOTO_NAME_RE.match(name):
        raise PlacesError("Invalid photo reference")
    try:
        meta = httpx.get(
            "{}/{}/media".format(BASE_URL, name),
            headers=_headers(),
            params={"maxWidthPx": width, "skipHttpRedirect": "true"},
            timeout=10.0,
        )
        meta.raise_for_status()
        uri = meta.json().get("photoUri", "")
        host = urlparse(uri).hostname or ""
        if not any(host == h or host.endswith("." + h) for h in _ALLOWED_PHOTO_HOSTS):
            raise PlacesError("Unexpected photo host")
        img = httpx.get(uri, timeout=15.0)
        img.raise_for_status()
    except httpx.HTTPError as e:
        raise PlacesError("Photo fetch failed: {}".format(e.__class__.__name__)) from e
    if len(img.content) > _MAX_PHOTO_BYTES:
        raise PlacesError("Photo too large")
    return img.content, img.headers.get("content-type", "image/jpeg")
