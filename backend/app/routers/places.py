from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_owned_trip
from app.models.trip import Trip
from app.models.user import User
from app.schemas.places import PlaceDetail, PlacesListResponse, PlaceSummary, ReviewSummary
from app.security import sign_photo, verify_photo
from app.services import google_places

router = APIRouter(prefix="/places", tags=["places"])

MAX_PHOTOS = 6


def _clean_price_level(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    return raw.replace("PRICE_LEVEL_", "").replace("_", " ").title()


# Static paths first: "/{trip_id}" would otherwise swallow them.
@router.get("/photo")
def photo(name: str, w: int = Query(800, ge=100, le=1600), exp: int = 0, sig: str = ""):
    """Public but only for URLs this server signed, so the Google key never reaches clients."""
    if not google_places.PHOTO_NAME_RE.match(name) or not verify_photo(name, w, exp, sig):
        raise HTTPException(status_code=403, detail="Invalid or expired photo link")
    data, content_type = google_places.fetch_photo(name, w)
    return Response(content=data, media_type=content_type, headers={"Cache-Control": "public, max-age=3600"})


@router.get("/detail/{place_id}", response_model=PlaceDetail)
def get_place_detail(place_id: str, user: User = Depends(get_current_user)):
    raw = google_places.get_place_details(place_id)

    photos = []
    for p in (raw.get("photos") or [])[:MAX_PHOTOS]:
        name = p.get("name", "")
        if google_places.PHOTO_NAME_RE.match(name):
            photos.append("/places/photo?" + urlencode(sign_photo(name)))

    reviews = [
        ReviewSummary(
            author_name=r.get("authorAttribution", {}).get("displayName"),
            rating=r.get("rating"),
            text=(r.get("text") or {}).get("text"),
        )
        for r in raw.get("reviews", [])
    ]
    return PlaceDetail(
        id=raw.get("id", place_id),
        name=(raw.get("displayName") or {}).get("text", "Unknown"),
        address=raw.get("formattedAddress"),
        rating=raw.get("rating"),
        price_level=_clean_price_level(raw.get("priceLevel")),
        opening_hours=(raw.get("currentOpeningHours") or {}).get("weekdayDescriptions"),
        website=raw.get("websiteUri"),
        phone=raw.get("nationalPhoneNumber"),
        description=(raw.get("editorialSummary") or {}).get("text"),
        photos=photos,
        reviews=reviews,
    )


@router.get("/{trip_id}", response_model=PlacesListResponse)
def get_places(
    category: str = Query(..., pattern="^(hotel|restaurant|attraction)$"),
    trip: Trip = Depends(get_owned_trip),
):
    raw_places = google_places.search_places(trip.destination, category)
    return {
        "places": [
            PlaceSummary(
                id=p["id"],
                name=(p.get("displayName") or {}).get("text", "Unknown"),
                category=category,
                price_level=_clean_price_level(p.get("priceLevel")),
                rating=p.get("rating"),
                address=p.get("formattedAddress"),
            )
            for p in raw_places
        ]
    }
