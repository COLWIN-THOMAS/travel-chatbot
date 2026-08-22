# API Contract

## POST /chat
The core endpoint — every message in the conversation flow (conversation-flow.md) goes through this.

**Request body:**
```json
{
  "trip_id": "uuid or null (null until CONFIRM creates the Trip)",
  "message": "the user's text"
}
```

**Response body:**
```json
{
  "reply_text": "what the bot says back",
  "conversation_state": "GREETING | COLLECTING | CONFIRM | GENERATE_PLAN | POST_PLAN | FALLBACK",
  "extracted_fields": { "destination": "Goa", "budget_total": null, "days_count": null, "preferences": null },
  "trip_id": "uuid (set once CONFIRM creates the Trip, otherwise same as request or null)",
  "itinerary": "null, unless conversation_state is GENERATE_PLAN — then the full day-wise plan"
}
```

`conversation_state` in the response is what the frontend uses to know how to render the current turn (e.g. show a "confirm/edit" button pair only when state is `CONFIRM`) — this is why it's part of every response, not just an internal backend detail.

---

## POST /trips
Rarely called directly by the frontend (normally /chat creates the Trip at CONFIRM) — useful for testing the backend before the chat flow works, or letting a user start a second trip manually.

**Request body:**
```json
{ "destination": "Goa", "budget_total": 15000, "days_count": 4, "preferences": ["food", "adventure"] }
```

**Response body:** the created Trip row (id, user_id, destination, budget_total, days_count, preferences, status, created_at)

---

## GET /trips/{trip_id}
Fetch one trip with everything nested inside it.

**Response body:**
```json
{
  "id": "...", "destination": "Goa", "budget_total": 15000, "days_count": 4, "status": "active",
  "days": [
    { "day_number": 1, "items": [ { "place_name": "Baga Beach", "category": "attraction", "estimated_cost": 200, "visited": false, "order_in_day": 1 } ] }
  ]
}
```

---

## GET /itinerary/{trip_id}
Same nested `days[].items[]` shape as above, but without the trip-level fields — use this when a screen only needs the plan, not the whole trip object.

---

## POST /itinerary/{trip_id}/regenerate

**Request body:**
```json
{ "changes": { "budget_total": 20000 } }
```

**Response body:** same shape as GET /itinerary/{trip_id}, updated

---

## POST /tracker/{trip_id}/visit
Mark a place visited.

**Request body:**
```json
{ "itinerary_item_id": "uuid", "visited": true }
```

**Response body:** the updated ItineraryItem

---

## POST /tracker/{trip_id}/expense
Log an expense.

**Request body:**
```json
{ "amount": 250, "category": "food", "itinerary_item_id": "uuid or null" }
```

**Response body:**
```json
{
  "expense": { "id": "...", "amount": 250, "category": "food" },
  "spend_total": 3200,
  "budget_remaining": 11800
}
```

---

## GET /tracker/{trip_id}
Spend-vs-budget summary — powers the progress bar on the checklist screen.

**Response body:**
```json
{
  "spend_total": 3200,
  "budget_total": 15000,
  "remaining": 11800,
  "percent_used": 21.3
}
```

---

## GET /places/{trip_id}
Suggestions for the trip's destination — feeds the hotel cards and restaurant list screens.

**Query params:** `category` — one of `hotel` | `restaurant` | `attraction`

**Response body:**
```json
{
  "places": [
    {
      "id": "uuid",
      "name": "Hotel Sunrise",
      "category": "hotel",
      "cost_estimate": 1800,
      "rating": 4.2,
      "description": "Beachfront stay, 10 min from Baga Beach"
    }
  ]
}
```

Note: this reads from wherever you source place data (a places API, or your own curated dataset — decide this in Module B1). It does not read from `itinerary_items` — those are places already *chosen* into the plan; `/places` is the browse/suggestion list before choosing.

---

## GET /places/detail/{place_id}
Full detail view for one place — feeds the place-guide detail screen.

**Response body:**
```json
{
  "id": "uuid",
  "name": "Hotel Sunrise",
  "category": "hotel",
  "cost_estimate": 1800,
  "rating": 4.2,
  "description": "Beachfront stay, 10 min from Baga Beach",
  "opening_hours": "24 hours (check-in 12pm)",
  "images": ["url1", "url2"]
}
```
