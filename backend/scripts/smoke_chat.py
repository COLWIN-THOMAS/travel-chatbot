"""Live end-to-end check of the conversation engine against a RUNNING API with a real ANTHROPIC_API_KEY.

    uvicorn app.main:app &            # in another terminal, with ANTHROPIC_API_KEY set in .env
    python scripts/smoke_chat.py      # optional: API_URL=http://127.0.0.1:8000

Registers a throw-away user, walks the whole flow (collect -> confirm -> plan -> tool actions), prints each
turn, asserts the invariants that matter, and deletes the user (cascades to trips/sessions) at the end.
"""
import os
import sys
import uuid

import httpx

API = os.getenv("API_URL", "http://127.0.0.1:8000")
client = httpx.Client(base_url=API, timeout=180.0)


def check(cond, msg):
    print(("PASS  " if cond else "FAIL  ") + msg)
    if not cond:
        raise SystemExit(1)


def say(headers, sid, text):
    r = client.post("/chat", headers=headers, json={"session_id": sid, "message": text})
    if r.status_code != 200:
        print("HTTP", r.status_code, r.text)
        raise SystemExit(1)
    body = r.json()
    print("\n> {}\n< [{}] {}".format(text, body["conversation_state"], body["reply_text"]))
    return body


email = "smoke-{}@example.com".format(uuid.uuid4().hex[:8])
reg = client.post("/auth/register", json={"email": email, "password": "smoke-Passw0rd"}).json()
headers = {"Authorization": "Bearer " + reg["access_token"]}
sid = str(uuid.uuid4())
try:
    r = say(headers, sid, "hi there")
    check(r["conversation_state"] == "FALLBACK" and "go" in r["reply_text"].lower(), "greeting is handled and steers back to the destination")

    r = say(headers, sid, "I'd like to visit Goa, around 15k rupees")
    check(r["extracted_fields"].get("destination") == "Goa" and r["extracted_fields"].get("budget_total") == 15000, "destination + budget extracted from one message")
    check(r["conversation_state"] == "COLLECTING" and "days" in r["reply_text"].lower(), "asks only for what is still missing (days)")

    r = say(headers, sid, "3 days, I love seafood and beaches")
    check(r["conversation_state"] == "CONFIRM", "all details collected -> recap (never skips confirm)")

    r = say(headers, sid, "actually make the budget 12000")
    check(r["conversation_state"] == "CONFIRM" and "12,000" in r["reply_text"], "editing at CONFIRM updates the recap")

    r = say(headers, sid, "yes go ahead")
    check(r["conversation_state"] == "GENERATE_PLAN" and r["trip_id"], "confirmation generates a plan and creates the trip")
    days = r["itinerary"]["days"]
    total = sum(i["estimated_cost"] for d in days for i in d["items"])
    check(len(days) == 3, "plan has exactly 3 days")
    check(total <= 12000, "plan total {:.0f} is within the 12000 budget".format(total))
    trip_id = r["trip_id"]
    first = days[0]["items"][0]["place_name"]

    r = say(headers, sid, "I just visited {} and spent 300 rupees there".format(first))
    check("mark_visited" in r["actions"] and "log_expense" in r["actions"], "assistant used the visit + expense tools")
    t = client.get("/tracker/" + trip_id, headers=headers).json()
    check(t["items_visited"] == 1 and t["spend_total"] == 300, "tracker reflects it (1 visited, 300 spent)")

    r = say(headers, sid, "what's the capital of France?")
    check(bool(r["reply_text"]), "off-topic question gets a reply without crashing")
    print("\nAll live checks passed.")
finally:
    client.delete("/trips/" + (locals().get("trip_id") or str(uuid.uuid4())), headers=headers)
    # the user itself is removed with a direct DB call so no test data is left behind
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        import app.models  # noqa: F401
        from app.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        u = db.query(User).filter(User.email == email).one_or_none()
        if u:
            db.delete(u)
            db.commit()
    except Exception as e:  # cleanup is best-effort
        print("cleanup skipped:", e)
