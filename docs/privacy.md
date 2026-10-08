# Privacy note

This describes what the Budget Trip Planner app stores, who it shares data with, and how to
delete it. It documents the system as built in this repository — it is not a legal document, and
would need review before any real-world launch.

## What is collected

| Data | Why | Where it lives |
|---|---|---|
| Email + password (hashed) | Sign-in | `users` table, Postgres |
| Trip details (destination, budget, days, dates, preferences) | The thing the app does | `trips` table |
| Generated itinerary (places, estimated costs) | The plan itself | `days` / `itinerary_items` tables |
| Expenses you log | Budget tracking | `expenses` table |
| Chat messages | Conversation memory, so the assistant doesn't re-ask what it already knows | `chat_messages` table |

Passwords are hashed with bcrypt before storage — the plaintext password is never saved and
cannot be recovered, only reset by setting a new one.

## Third parties the app talks to

| Service | What it receives | What it's used for |
|---|---|---|
| Anthropic (Claude API) | Your chat messages, trip details, and the itinerary being planned | Understanding your messages and generating the plan |
| Google Places API | The trip's destination and category searched | Real hotel/restaurant/attraction listings, photos, reviews |
| Open-Meteo | The destination's coordinates | Weather forecast |
| OpenStreetMap Nominatim | The destination name you typed | Resolving a place name to coordinates |

None of these services receive your email, password, or account identifiers — only the trip
content needed to answer that specific request. See each provider's own privacy policy for how
long they retain request data on their side; this app does not control that.

## How long data is kept

Everything above is kept until you delete it — there is no automatic expiry. Deleting a trip
removes that trip's days, items, and expenses immediately. Signing out does not delete anything;
it only removes the login token from your device.

## Deleting your account

`DELETE /auth/me` (re-enter your password to confirm) permanently removes:
- your account and login credentials,
- every trip, day, itinerary item and expense you created,
- every chat session and message.

This is enforced at the database level (foreign keys with `ON DELETE CASCADE`), not just in
application code, so no linked record can be left behind by a bug in a single endpoint. There is
no recovery after this — it is not a soft delete or a trash/undo period.

## What this app does not do

- It does not sell or share your data with advertisers.
- It does not make real payments or bookings on your behalf (see `README.md` → Known limitations).
- It does not track you outside the app (no third-party analytics or ad SDKs are included).

## Contact / data requests

This is a student/personal project, not a company with a formal privacy office. For a real
deployment, replace this section with an actual contact method and a defined response time for
access/deletion requests, and add a retention schedule and breach-notification process.
