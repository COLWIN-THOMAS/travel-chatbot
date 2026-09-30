# Budget Trip Planner

A chat assistant that plans budget-friendly trips. Tell it where, how long and how much; it builds a day-by-day plan that fits the budget, then helps you track visits and spending during the trip.

- **Chat → plan:** the assistant collects destination, budget, days and interests (in any order), recaps, and on confirmation generates a structured itinerary grounded in real places.
- **During the trip:** tick places off, log expenses, watch spend vs. budget, see the weather per day, browse hotels / restaurants / things to do with photos and reviews.
- **Costs are bounded:** the LLM is used only for extraction, off-topic replies and planning; every other reply is templated (see `docs/conversation-flow.md`).

| Layer | Tech |
|---|---|
| App | React Native (Expo SDK 57, Expo Router), TypeScript, TanStack Query — runs on iOS, Android and web |
| API | FastAPI (Python 3.9+), SQLAlchemy 2, Alembic, Pydantic v2 |
| Database | PostgreSQL |
| AI | Claude API — Haiku 4.5 (extraction, chat), Sonnet 5 (planning), structured outputs |
| Data | Google Places API (New), Open-Meteo (weather), OpenStreetMap Nominatim (geocoding) |

## Repository layout

```
backend/    FastAPI app  (app/routers, app/services, app/models, app/schemas, alembic/, tests/)
frontend/   Expo app     (src/app = screens, src/components, src/lib = api/auth/hooks, src/__tests__)
docs/       design docs  (conversation-flow, data-model, db-schema, api-contract, wireframes/)
```

The design docs describe **what was built**; `docs/api-contract.md` is the API reference.

## Run it locally

### 1. Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then fill in the values (see below)
alembic upgrade head        # creates/updates the tables
uvicorn app.main:app --reload
```

`.env` (never commit it — it is git-ignored):

| Variable | Needed for |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (a free Neon/Supabase DB works) |
| `JWT_SECRET` | signing login tokens and photo links — `python3 -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `ANTHROPIC_API_KEY` | the chat assistant. Without it `/chat` returns 503; everything else works |
| `GOOGLE_PLACES_API_KEY` | hotels / restaurants / attractions / photos / reviews. Restrict the key to *Places API (New)* |

Optional: `EXTRACTION_MODEL`, `CHAT_MODEL`, `PLANNER_MODEL`, `MAX_MESSAGES_PER_DAY` (default 300), `JWT_EXPIRE_MINUTES`, `CORS_ORIGINS`. The server logs a warning at startup for any missing required key.

API docs: http://127.0.0.1:8000/docs

### 2. App

```bash
cd frontend
npm install
npm run web          # or: npx expo start  (then press i / a, or scan with Expo Go)
```

The app finds the API automatically in development (same host as the Expo dev server, port 8000; `10.0.2.2` on the Android emulator). To point elsewhere set `EXPO_PUBLIC_API_URL` (see `frontend/.env.example`). Web dev uses CORS origins `localhost:8081/19006`; add others via `CORS_ORIGINS`.

## Tests

```bash
cd backend  && pytest                 # 67 tests: API, auth, tracker, conversation state machine, planner, tool loop, SDK request shapes
cd frontend && npm test && npm run typecheck
```

Backend tests run inside a rolled-back transaction on the configured database (nothing persists) and never call Claude or Google: the LLM layer is scripted, and `tests/test_llm_sdk.py` drives the real Anthropic SDK against a mock HTTP transport to check request shapes and structured-output parsing.

## Design decisions worth knowing

- **Server-side conversation memory.** The client sends a `session_id` on every message; slots and state live in `chat_sessions`, so the bot never forgets earlier answers and never re-derives them from text.
- **Derived money, not stored money.** Spend per item/day/trip is always `SUM(expenses)`; there is no cached total that can drift.
- **Plans are validated, not trusted.** The planner must return exactly N days and a total within budget; otherwise it retries once with concrete feedback, then tells the user rather than saving a bad plan.
- **Real places.** The planner is given Google Places candidates for the destination so plans use real names.
- **Google's key never reaches clients.** Photos are served through a proxy that only honours URLs the server signed (HMAC, expiring).
- **Price tiers, not invented prices.** Google returns a price *tier*, so the app shows ₹–₹₹₹₹ and a "Budget-friendly" badge for Free/Inexpensive rather than fabricating rupee amounts.
- **Auth.** bcrypt password hashing (direct, not passlib), JWT bearer tokens, constant-shape login errors, ownership enforced on every trip/session route.

## Known limitations

- Costs are estimates in ₹ for one traveller; there are no live prices or bookings.
- Trips have no calendar dates; weather for "Day k" is today + (k−1).
- Place data is only cached for 10 minutes in memory, per Google's terms; each place detail view is a billable Enterprise-tier call (Google's free monthly quota is generous for development).
- The chat assistant needs `ANTHROPIC_API_KEY`; the LLM-dependent behaviour was verified with scripted/mock models, so run a few real conversations before relying on prompt quality.
- In-process caches and the per-session lock assume a single API process or Postgres-level locking; use a shared cache (Redis) if you scale out.
