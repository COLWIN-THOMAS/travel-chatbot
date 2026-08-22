# Conversation Flow

Bot extracts whatever fields are present in each message (flexible order),
only asks for what's still missing. CONFIRM is never skipped.

| State              | Bot asks / does                                  | Moves to next when...                        |
|--------------------|---------------------------------------------------|-----------------------------------------------|
| GREETING           | Welcomes user, asks for destination               | User sends any message                        |
| COLLECTING         | Asks for whichever of [destination, budget, days, preferences] is still missing | All 4 fields are filled            |
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

