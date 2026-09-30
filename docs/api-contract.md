# API Contract

Base URL in development: `http://127.0.0.1:8000`. Interactive docs: `/docs`.

Conventions
- JSON everywhere. Money is in **Indian rupees (₹)**. Ids are UUIDs.
- Every route except `/health*`, `/auth/register`, `/auth/login` and the signed `/places/photo` URL needs `Authorization: Bearer <token>`.
- Other people's trips/sessions return **404** (not 403) so ids can't be probed.
- Errors: `{"detail": "message"}`; validation errors (422) use FastAPI's `{"detail": [{"loc": [...], "msg": "..."}]}`.
- Upstream problems: `503` = assistant (LLM) unavailable, `502` = places/weather provider unavailable, `429` = daily chat limit. Messages are generic; details are in the server log.

## Auth

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/register` | `{email, password}` (password 8–72 bytes) | `201 {access_token, token_type, user:{id,email}}`; `409` if the email exists |
| POST | `/auth/login` | `{email, password}` | `{access_token, token_type, user}`; `401` for wrong email **or** password (identical response) |
| GET | `/auth/me` | – | `{id, email}` |

## Chat — `POST /chat`

The conversation engine (see `conversation-flow.md`). The client generates a `session_id` (UUID) when a chat starts and sends it on every call; that is how the server remembers earlier answers before a trip exists.

Request
```json
{ "session_id": "uuid", "message": "Goa, 15k, 4 days, love food" }
```
`message`: 1–1000 chars, not blank.

Response
```json
{
  "session_id": "uuid",
  "reply_text": "Here's your trip: ...",
  "conversation_state": "COLLECTING | CONFIRM | GENERATE_PLAN | POST_PLAN | FALLBACK",
  "extracted_fields": { "destination": "Goa", "budget_total": 15000, "days_count": 4, "preferences": ["food"] },
  "trip_id": "uuid | null",
  "itinerary": { "days": [ ... ] } ,
  "actions": ["mark_visited", "log_expense", "update_plan"]
}
```
- `extracted_fields` is the **cumulative** set of details collected so far.
- `conversation_state` is `FALLBACK` for a turn where nothing usable was understood; the session stays in its previous state.
- `GENERATE_PLAN` is returned once, on the turn the plan is created (`trip_id` and `itinerary` are set); afterwards the session is in `POST_PLAN`.
- `itinerary` is non-null only when a plan was created or rebuilt; `actions` lists what the assistant did in `POST_PLAN` so the client can refresh.

`GET /chat/{session_id}` → `{session_id, state, slots, trip_id, messages:[{role, content, created_at}]}` in order. An unknown session returns an empty history (state `COLLECTING`); another user's session is `404`.

## Trips

| Method | Path | Notes |
|---|---|---|
| POST | `/trips` | `{destination, budget_total (>0), days_count (1–14), preferences[]}` → `201` trip. Normally the chat creates trips; this is for tests/manual use. |
| GET | `/trips` | Current user's trips, newest first |
| GET | `/trips/{trip_id}` | Trip + `days[].items[]` (see Itinerary) |
| DELETE | `/trips/{trip_id}` | `204`; cascades to days, items, expenses, chat messages |

Trip: `{id, user_id, destination, budget_total, days_count, preferences, status ("planning"|"active"|"completed"), created_at}`

## Itinerary

`GET /itinerary/{trip_id}` → `{days: [Day]}`

```json
{
  "id": "uuid", "day_number": 1, "date": null,
  "estimated_total": 2300.0, "spend_so_far": 0.0,
  "items": [{
    "id": "uuid", "place_name": "Baga Beach", "category": "attraction | hotel | restaurant | transport",
    "estimated_cost": 0.0, "actual_cost": 0.0, "visited": false, "order_in_day": 1, "notes": null
  }]
}
```
`actual_cost` and `spend_so_far` are **derived** (sum of expenses linked to the item / day's items), never stored.

`POST /itinerary/{trip_id}/regenerate` — body `{"changes": {budget_total?, days_count?, preferences?, instructions?}}`. Rebuilds the whole plan (visited flags reset; expenses stay but are unlinked from removed items). `422` if no plan fits the constraints; `503` if the LLM is down. Response: same as `GET /itinerary/{trip_id}`.

## Tracker

| Method | Path | Body → Response |
|---|---|---|
| POST | `/tracker/{trip_id}/visit` | `{itinerary_item_id, visited}` → updated item |
| POST | `/tracker/{trip_id}/expense` | `{amount (>0), category?, itinerary_item_id?}` → `201 {expense, spend_total, budget_remaining}` |
| GET | `/tracker/{trip_id}/expenses` | newest first |
| DELETE | `/tracker/{trip_id}/expense/{expense_id}` | `204` |
| GET | `/tracker/{trip_id}` | `{spend_total, budget_total, remaining, percent_used, items_total, items_visited, spent_by_category}` |

An `itinerary_item_id` from another trip is rejected with `404`.

## Places (Google Places API, New)

| Method | Path | Response |
|---|---|---|
| GET | `/places/{trip_id}?category=hotel\|restaurant\|attraction` | `{places:[{id, name, category, price_level, rating, address}]}` for the trip's destination |
| GET | `/places/detail/{place_id}` | `{id, name, address, rating, price_level, opening_hours[], website, phone, description, photos[], reviews[{author_name, rating, text}]}` |
| GET | `/places/photo?name=&w=&exp=&sig=` | image bytes; **only** for URLs signed by the server (returned in `photos`), valid ~6 h |

- `price_level` is Google's tier text (`Free`, `Inexpensive`, `Moderate`, `Expensive`, `Very Expensive`) or `null` — Google does not supply rupee prices, so none are invented.
- The list uses Pro-tier fields only; photos/reviews come from the detail call (Enterprise + Atmosphere SKU), which fires once per place a user opens.
- `photos` are relative signed URLs; the Google API key never reaches clients.

## Weather

`GET /weather/{trip_id}` → `{destination, days:[{day_number, date, temp_max, temp_min, condition, icon, precipitation_probability, advisory}]}`

Forecast for the next `days_count` days starting today (Open-Meteo; destination resolved via OpenStreetMap Nominatim). Trips have no fixed dates, so Day *k* maps to today + (k−1).

## Health

`GET /health` → `{"status":"ok"}` · `GET /health/db` → `{"database":"connected"}` or `503`.
