# Data Model

## Trip
The top-level object — one per planned trip.

- id — unique identifier
- user_id — who owns this trip
- destination — text, e.g. "Goa"
- budget_total — number, the user's total budget for the whole trip
- days_count — number, how many days the trip spans
- preferences — list of tags, e.g. ["food", "adventure"]
- status — one of: "planning" (still in chat flow) | "active" (plan generated, trip ongoing) | "completed"
- created_at — timestamp

## Day
One per day of the trip. A Trip with days_count = 4 has exactly 4 Day rows.

- id — unique identifier
- trip_id — which Trip this belongs to
- day_number — 1, 2, 3... (order within the trip)
- date — actual calendar date, optional (user might not fix exact dates upfront)
- spend_so_far — running total of confirmed expenses logged against this day's items (see Expense below for how this is calculated, not stored)

## ItineraryItem
One per place/activity slotted into a specific day — this is what the
visited/spend checklist actually checks off.

- id — unique identifier
- day_id — which Day this belongs to
- place_name — e.g. "Baga Beach", "Hotel Sunrise"
- category — one of: "hotel" | "restaurant" | "attraction" | "transport"
- estimated_cost — number, what the plan expected this to cost
- actual_cost — number, nullable — filled in once the user logs a real expense against it
- visited — true/false, defaults to false
- order_in_day — number, so items display in the order they happen (morning → night)
- notes — free text, optional (e.g. "book ahead", user's own note)
Note: `actual_cost` above is not a stored value — it's `SUM(expenses.amount)` for
all Expenses linked to that item. Same logic applies to Day.spend_so_far and the
Trip's overall spend total. Computed-on-read avoids the two numbers ever disagreeing.

## Expense
One per actual money spent — logged by the user via the tracker,
independent of whether it was planned.

- id — unique identifier
- trip_id — which Trip this belongs to
- itinerary_item_id — nullable — linked if this expense is for a planned item (e.g. paying for "Hotel Sunrise"); null if it's an unplanned spend (e.g. "bought water", "tipped a driver")
- amount — number
- category — text, e.g. "food", "transport", "shopping" (useful for a spend breakdown later)
- logged_at — timestamp

## ChatMessage
One per message in the conversation — both user and bot sides.
This is also where the "memory" from the conversation flow lives.

- id — unique identifier
- trip_id — which Trip this belongs to (a Trip is created at CONFIRM — see conversation-flow.md; messages sent before that can be linked once the Trip exists, or held client-side until then)
- role — "user" or "assistant"
- content — the actual text
- extracted_fields — JSON, nullable — whatever slots (destination/budget/days/preferences) were pulled from this specific message, if any
- created_at — timestamp
