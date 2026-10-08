# Budget Trip Planner

A chat assistant that plans budget-friendly trips. Tell it where, how long and how much; it builds a day-by-day plan that fits the budget, then helps you track visits and spending during the trip.

- **Chat → plan:** the assistant collects destination, budget, days, dates and interests (in any order), recaps, and on confirmation generates a structured itinerary grounded in real places.
- **During the trip:** tick places off, log expenses, watch spend vs. budget, see the weather per day, browse hotels / restaurants / things to do with photos and reviews, and jump straight to Uber or Booking.com to actually book.
- **Costs are bounded:** the LLM is used only for extraction, off-topic replies and planning; every other reply is templated (see `docs/conversation-flow.md`).
- **Overspend doesn't break the plan:** if real spending means the remaining budget can no longer cover the days that haven't started, the rebalancer automatically replans just those days — days already underway are never touched.

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
            app/services/route_optimizer.py  - clustering/ordering/budget-fit, independent of the LLM
            app/evaluation/                  - scoring + comparison harness for the optimizer
            scripts/run_evaluation.py        - CLI: writes evaluation/results/ (table, CSV, charts)
            scripts/load_test.py             - Locust load test against a running API
            scripts/smoke_chat.py            - one live conversation end-to-end, for sanity-checking a deploy
frontend/   Expo app     (src/app = screens, src/components, src/lib = api/auth/hooks, src/__tests__)
docs/       design docs  (conversation-flow, data-model, db-schema, api-contract, privacy, wireframes/)
.github/workflows/ci.yml  - backend pytest + frontend tsc/lint/jest on every push/PR
```

The design docs describe **what was built**; `docs/api-contract.md` is the API reference, `docs/privacy.md` is the data/privacy note.

## Run it locally

### 1. Backend

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then fill in the values (see below)
alembic upgrade head        # creates/updates the tables (run this after pulling: the latest migration adds trips.start_date)
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
cd backend  && pytest                 # 156 tests: API, auth, tracker, dates & history, rebalancing, route optimizer,
                                       # evaluation harness, deep links, conversation state machine, planner, tool loop,
                                       # SDK request shapes
cd frontend && npm test && npm run typecheck && npx expo lint
```

Backend tests run inside a rolled-back transaction on the configured database (nothing persists) and never call Claude or Google: the LLM layer is scripted, and `tests/test_llm_sdk.py` drives the real Anthropic SDK against a mock HTTP transport to check request shapes and structured-output parsing. `pytest.ini` restricts collection to `tests/` — without it, bare `pytest` also tries to import `scripts/load_test.py` (it matches the default `*_test.py` glob by filename), which pulls in Locust's gevent monkey-patch and corrupts socket state for every test that runs afterward.

### Route optimizer evaluation

```bash
cd backend && python scripts/run_evaluation.py           # scripted sample data, no API calls, no cost
cd backend && python scripts/run_evaluation.py --live    # + N real planner calls against Claude (uses API credit)
```

Writes a comparison table (`evaluation/results/comparison.md`/`.csv`) and bar charts scoring an LLM-order baseline against the same places run through the route optimizer (`app/services/route_optimizer.py`: geographic clustering, nearest-neighbour + 2-opt ordering, 0/1-knapsack budget fit) on budget adherence, travel distance per day, and interest match. On the bundled sample data this cuts average daily travel distance from ~20 km to ~1.2 km. The optimizer is a standalone, independently-tested module — it is not yet wired into the live `/chat` planning flow.

### Load test

```bash
cd backend && pip install locust && locust -f scripts/load_test.py --host http://127.0.0.1:8000
```

Simulates users hitting the read-heavy, non-LLM screens (`/trips`, `/itinerary`, `/tracker`); chat/planning calls are deliberately excluded since they cost real money per request.

## Design decisions worth knowing

- **Server-side conversation memory.** The client sends a `session_id` on every message; slots and state live in `chat_sessions`, so the bot never forgets earlier answers and never re-derives them from text.
- **Derived money, not stored money.** Spend per item/day/trip is always `SUM(expenses)`; there is no cached total that can drift.
- **Plans are validated, not trusted.** The planner must return exactly N days and a total within budget; otherwise it retries once with concrete feedback, then tells the user rather than saving a bad plan.
- **Real dates, frozen history.** Trips have a start date picked on an in-app calendar (or asked for in chat); each day gets its calendar date and weather is matched by date. Days that have started - a place ticked, or the date has passed - are never rewritten by any replan (automatic rebalance, Adjust plan, or the chat assistant).
- **Trip history.** Every trip stays in the Trips screen (happening now / upcoming / past) with dates, spend versus budget and places visited, until you delete it.
- **Real places.** The planner is given Google Places candidates for the destination so plans use real names.
- **Google's key never reaches clients.** Photos are served through a proxy that only honours URLs the server signed (HMAC, expiring).
- **Price tiers, not invented prices.** Google returns a price *tier*, so the app shows ₹–₹₹₹₹ and a "Budget-friendly" badge for Free/Inexpensive rather than fabricating rupee amounts.
- **Auth.** bcrypt password hashing (direct, not passlib), JWT bearer tokens, constant-shape login errors, ownership enforced on every trip/session route. Account deletion (`DELETE /auth/me`, password-reconfirmed) cascades through the database via foreign keys, not application code, so no linked row can be left behind by a bug in one endpoint — see `docs/privacy.md`.
- **Deep links are either real or honest, never guessed.** Uber and Booking.com links are built from each provider's actual documented/public URL format, carrying real coordinates and dates. Rapido and IRCTC have no public deep-link scheme to build from — rather than fabricate one that would silently fail on a real phone, those links say so (`prefilled: false`) and open the plain site instead.

## CI

`.github/workflows/ci.yml` runs on every push/PR to `main`: backend tests against a real Postgres service container (Python 3.9, matching local dev), and frontend typecheck + lint + jest (Node 20). No secrets are required — the backend suite mocks the LLM layer (see Tests above).

## Known limitations

- The route optimizer and evaluation harness are built and tested standalone but not yet wired into the live `/chat` planning flow — the LLM planner's own ordering is what ships today.
- `scripts/run_evaluation.py --live` and `scripts/smoke_chat.py` (real conversations against live Claude) need `ANTHROPIC_API_KEY` to have billing credit; not yet run against the live model as of this writing.
- Costs are estimates in ₹ for one traveller; there are no live prices or bookings.
- Weather comes from a 16-day forecast window, so days further out than that show no forecast until the trip gets closer. Trips created before dates existed have no dates; for them "Day k" is still treated as today + (k−1).
- Place data is only cached for 10 minutes in memory, per Google's terms; each place detail view is a billable Enterprise-tier call (Google's free monthly quota is generous for development).
- The chat assistant needs `ANTHROPIC_API_KEY`; the LLM-dependent behaviour was verified with scripted/mock models, so run a few real conversations before relying on prompt quality.
- In-process caches and the per-session lock assume a single API process or Postgres-level locking; use a shared cache (Redis) if you scale out.
