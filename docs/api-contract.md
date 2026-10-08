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
  "extracted_fields": { "destination": "Goa", "budget_total": 15000, "days_count": 4, "start_date": "2026-11-14", "preferences": ["food"] },
  "next_field": "preferences | null",
  "trip_id": "uuid | null",
  "itinerary": { "days": [ ... ] } ,
  "actions": ["mark_visited", "log_expense", "update_plan"]
}
```
- `extracted_fields` is the **cumulative** set of details collected so far. `start_date` is `YYYY-MM-DD`, or the literal `"undecided"` when the traveller has no dates yet.
- `next_field` is the detail the assistant is asking for right now (`destination`, `budget_total`, `days_count`, `start_date`, `preferences`), or `null` once everything is collected / the trip exists. The app shows its calendar button when this is `start_date`.
- `conversation_state` is `FALLBACK` for a turn where nothing usable was understood; the session stays in its previous state.
- `GENERATE_PLAN` is returned once, on the turn the plan is created (`trip_id` and `itinerary` are set); afterwards the session is in `POST_PLAN`.
- `itinerary` is non-null only when a plan was created or rebuilt; `actions` lists what the assistant did in `POST_PLAN` so the client can refresh.

`GET /chat/{session_id}` → `{session_id, state, slots, next_field, trip_id, messages:[{role, content, created_at}]}` in order. An unknown session returns an empty history (state `COLLECTING`); another user's session is `404`.

## Trips

| Method | Path | Notes |
|---|---|---|
| POST | `/trips` | `{destination, budget_total (>0), days_count (1–14), preferences[], start_date?}` → `201` trip. Normally the chat creates trips; this is for tests/manual use. |
| GET | `/trips` | The user's **trip history**, newest first: every trip plus how it went (see Trip summary) |
| PUT | `/trips/{trip_id}/dates` | `{start_date: "YYYY-MM-DD" \| null}` → trip. Sets or clears the start date; every day is re-dated to `start_date + (day_number − 1)`. Dates must be within one year back and two years ahead (`422` otherwise). |
| GET | `/trips/{trip_id}` | Trip + `days[].items[]` (see Itinerary) |
| DELETE | `/trips/{trip_id}` | `204`; cascades to days, items, expenses, chat messages |

Trip: `{id, user_id, destination, budget_total, days_count, start_date, end_date, phase, preferences, status ("planning"|"active"|"completed"), created_at}`

- `start_date` is `null` for trips without dates (including every trip made before dates existed). `end_date` is derived: `start_date + days_count − 1`.
- `phase` is derived from the dates and today's date in India (UTC+05:30): `undated` | `upcoming` | `ongoing` | `completed`.
- **Trip summary** (items of `GET /trips`) = Trip + `{estimated_total, spend_total, items_total, items_visited}`. Trips are kept until the user deletes them, so this list is the app's travel history.

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

`POST /itinerary/{trip_id}/regenerate` — body `{"changes": {budget_total?, days_count?, preferences?, instructions?}}`. Rebuilds the plan. If nothing has started yet, the whole plan is rebuilt (expenses stay but are unlinked from removed items). If some days have **started** (a place ticked visited, or the day's date is in the past) those days are kept exactly as they are and only the later days are rebuilt, against the budget still left and the days still left; `days_count` can't go below the number of started days (`422`). `422` if no plan fits the constraints; `503` if the LLM is down. Response: same as `GET /itinerary/{trip_id}`.

## Tracker

| Method | Path | Body → Response |
|---|---|---|
| POST | `/tracker/{trip_id}/visit` | `{itinerary_item_id, visited}` → updated item + `itinerary_notice` |
| POST | `/tracker/{trip_id}/expense` | `{amount (>0), category?, itinerary_item_id?}` → `201 {expense, spend_total, budget_remaining, itinerary_notice}` |
| GET | `/tracker/{trip_id}/expenses` | newest first |
| DELETE | `/tracker/{trip_id}/expense/{expense_id}` | `204` |
| GET | `/tracker/{trip_id}` | `{spend_total, budget_total, remaining, percent_used, items_total, items_visited, spent_by_category}` |

An `itinerary_item_id` from another trip is rejected with `404`.

### Automatic budget rebalancing

After every visit/expense change, the server checks whether the money left can still cover the days that
haven't started yet (a day counts as "started" once any of its places is marked visited, or - for trips with dates - once its date is in the past; today stays editable until something on it is ticked). If not, it
**automatically regenerates only the not-yet-started days** against the actual remaining budget — days
already in progress are never touched. `itinerary_notice` is `null` when nothing needed to change, otherwise:

```json
{
  "rebalanced": true,
  "message": "Heads up: your remaining budget (₹100) couldn't cover Days 2-3 as originally planned (est. ₹1,350), so I've automatically updated those days to fit (new est. ₹95). Day 1 is unchanged.",
  "days_from": 2,
  "days_to": 3
}
```

If even a minimal replan doesn't fit (budget essentially exhausted), `rebalanced` is `false` and the message
asks the user to add budget or adjust the plan themselves — nothing is changed in that case. The same check
also runs inside the chat assistant's `mark_visited`/`log_expense` tools (see `conversation-flow.md`), so it
fires whether the action came from the Tracker screen or from a chat message.

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

`GET /weather/{trip_id}` → `{destination, days:[{day_number, date, temp_max, temp_min, condition, icon, precipitation_probability, advisory}], note}`

Open-Meteo gives a 16-day forecast (destination resolved via OpenStreetMap Nominatim). For a trip with dates, each Day *k* is matched by calendar date (`start_date + k − 1`); days outside the window - too far ahead, or already over - are left out and `note` explains why (e.g. "Forecasts only reach 2026-10-23. Check back closer to your trip."). Trips without dates keep the old mapping, Day *k* = today + (k−1).

## Health

`GET /health` → `{"status":"ok"}` · `GET /health/db` → `{"database":"connected"}` or `503`.
