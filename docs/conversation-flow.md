# Conversation Flow

Bot extracts whatever fields are present in each message (flexible order),
only asks for what's still missing. CONFIRM is never skipped.

| State              | Bot asks / does                                  | Moves to next when...                        |
|--------------------|---------------------------------------------------|-----------------------------------------------|
| GREETING           | Welcomes user, asks for destination               | User sends any message                        |
| COLLECTING         | Asks for whichever of [destination, budget, days, start date, preferences] is still missing | All 5 fields are filled            |
| CONFIRM            | Recaps all 4 fields, asks "confirm or edit?"      | User confirms                                  |
| GENERATE_PLAN      | Calls itinerary generator, returns day-wise plan  | Plan is generated and shown                    |
| POST_PLAN          | Free-form: swap a place, adjust budget, mark visited, log expense | (stays here for rest of trip)  |
| FALLBACK           | Extraction found no new fields for the current state. Bot calls Claude for a natural freeform reply (can chit-chat / answer a general travel question), then appends a gentle steer-back to whatever field is still missing | Returns to COLLECTING (or CONFIRM/POST_PLAN, whichever state it was in) once a usable answer arrives |

## Fallback trigger rule
Enter FALLBACK when: the slot-extraction call returns no new fields AND the message isn't a recognized confirm/edit command (e.g. "yes", "confirm", "change budget"). Two consecutive FALLBACK turns in a row → drop to the canned reprompt instead of another LLM call, so a truly stuck conversation doesn't rack up API cost.

## Editing at CONFIRM
"Edit" is not a separate mechanism — CONFIRM re-runs the same slot-extraction
call used in COLLECTING. Any field it finds overwrites the stored value for
that field; the bot then re-shows the CONFIRM recap. This is why extraction
must run on every user message, not just while in COLLECTING.


## As built

Where the design landed in `backend/app/services/conversation.py`:

- **Session memory:** the client sends a `session_id` with every `/chat` call. The session row stores `state`, the merged `slots` and `fallback_count`; the server never re-derives them from message text. Concurrent requests for one session are serialised with a row lock.
- **Three LLM uses, everything else is templated** (cheap, fast, predictable):
  1. *Extraction* (`claude-haiku-4-5`, structured output) on every COLLECTING/CONFIRM message: destination, budget, days, start date, preferences, `is_confirmation`. Values are validated in code (budget > 0, 1–14 days, start date today or later and within two years, trimmed/deduped preferences) before being stored. The extractor is told today's date (India) so it can resolve "next Friday" or "15 Nov" to a concrete `YYYY-MM-DD`; a range like "14 to 17 Nov" fills both the start date and the number of days. If the traveller says they have not decided yet, the slot is stored as `undecided` and the trip is created without dates (they can add them later from the Plan screen).
  2. *Fallback reply* (Haiku) for turns with nothing usable; the app appends the next question itself. After two consecutive fallbacks a canned reprompt is used (no API call).
  3. *Planning* (`claude-sonnet-5`, structured output) at confirmation, grounded in real Google Places candidates, validated (exact day count, total ≤ budget) with one retry that feeds the failure back to the model. If no valid plan exists the user stays at CONFIRM with an explanation and no trip is created.
- **Confirm is never skipped:** `is_confirmation` only counts while in CONFIRM, and only if nothing was changed in the same message.
- **Editing at CONFIRM** re-runs extraction; any changed field overwrites the stored one and the recap is shown again.
- **POST_PLAN** is a small tool-using assistant (`services/assistant.py`) with tools `mark_visited`, `log_expense`, `get_summary`, `update_plan`. Tool arguments are validated; the loop is capped at 5 rounds; the reply may only claim an action if a tool result confirmed it.
- **Guards:** user text is stripped of `<`/`>` before being placed in prompts and labelled as data; messages are capped at 1000 characters; 300 user messages per user per day (`MAX_MESSAGES_PER_DAY`).
- **Failures:** LLM outage → `503` and the turn is not persisted, so the client can simply resend.


## Automatic mid-trip budget rebalancing

Added after the initial build, in response to a real gap: a plan generated once at confirmation can't
account for how an actual trip plays out. Implemented in `services/rebalance.py`, triggered from both the
`/tracker` endpoints and the assistant's `mark_visited`/`log_expense` tools (`services/assistant.py`):

- A day counts as **started** once any of its items is marked visited; the first day with nothing visited,
  and every day after it, is **remaining**.
- After logging an expense or marking a visit, if `remaining_budget < remaining_planned_cost` for the
  remaining days (by more than a 1-rupee rounding margin), the remaining days are regenerated against
  whatever budget is actually left, grounded in real place candidates as usual, biased toward free/cheap
  options via extra planner instructions.
- Started days are never deleted or regenerated, even if the replan fails. With real dates, a day whose date has passed counts as started even if nothing was ticked, and the manual "Adjust plan" and the chat's `update_plan` follow the same rule.
- If no plan fits even the minimum, nothing is changed and the user is told their options rather than
  silently producing a broken itinerary.
- The outcome (rebalanced, or couldn't) is returned as `itinerary_notice` on the two tracker endpoints, and
  relayed by the assistant in its own words when triggered via chat, so the user is never surprised by their
  itinerary changing underneath them.
