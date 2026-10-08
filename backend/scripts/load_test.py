"""Load test against a RUNNING API (not the test suite - a real server, e.g. `uvicorn app.main:app`).

Exercises the read-heavy, non-LLM endpoints realistically: register once per simulated user, then
repeatedly hit /trips, /itinerary, /tracker (the screens a user actually sits on). Chat/itinerary
generation calls Claude and costs real money per request, so they are NOT included in the load
loop - see --with-chat to add a single, rate-limited chat sample if you want that data too.

Usage:
    pip install locust
    locust -f scripts/load_test.py --host http://127.0.0.1:8000
    # then open http://localhost:8089 and set users/spawn-rate, or run headless:
    locust -f scripts/load_test.py --host http://127.0.0.1:8000 --headless -u 20 -r 5 -t 60s
"""
import os
import random
import uuid

from locust import HttpUser, between, task

WITH_CHAT = os.getenv("LOAD_TEST_WITH_CHAT") == "1"


class TravellerUser(HttpUser):
    wait_time = between(1, 3)  # seconds between a simulated user's actions, like real think-time

    def on_start(self):
        email = "loadtest-{}@example.com".format(uuid.uuid4().hex[:12])
        r = self.client.post("/auth/register", json={"email": email, "password": "LoadTest123"}, name="/auth/register")
        self.token = r.json()["access_token"]
        self.headers = {"Authorization": "Bearer " + self.token}
        self.trip_id = None
        self._seed_trip()

    def _seed_trip(self):
        # A trip with no itinerary yet is enough to exercise GET /trips, /trips/{id}; tracker/itinerary
        # reads against an empty plan still hit the real DB query paths being load-tested.
        r = self.client.post(
            "/trips", headers=self.headers, name="/trips [setup]",
            json={"destination": "Goa", "budget_total": 15000, "days_count": 3, "preferences": ["food"]},
        )
        if r.status_code == 201:
            self.trip_id = r.json()["id"]

    @task(5)
    def list_trips(self):
        self.client.get("/trips", headers=self.headers, name="/trips")

    @task(5)
    def get_trip(self):
        if self.trip_id:
            self.client.get("/trips/{}".format(self.trip_id), headers=self.headers, name="/trips/:id")

    @task(3)
    def get_itinerary(self):
        if self.trip_id:
            self.client.get("/itinerary/{}".format(self.trip_id), headers=self.headers, name="/itinerary/:id")

    @task(3)
    def get_tracker_summary(self):
        if self.trip_id:
            self.client.get("/tracker/{}".format(self.trip_id), headers=self.headers, name="/tracker/:id")

    @task(1)
    def log_expense(self):
        if self.trip_id:
            self.client.post(
                "/tracker/{}/expense".format(self.trip_id), headers=self.headers, name="/tracker/:id/expense",
                json={"amount": round(random.uniform(50, 500), 2), "category": "food"},
            )

    def on_stop(self):
        if self.trip_id:
            self.client.delete("/trips/{}".format(self.trip_id), headers=self.headers, name="/trips/:id [cleanup]")
        self.client.delete(
            "/auth/me", headers=self.headers, name="/auth/me [cleanup]",
            json={"password": "LoadTest123"},
        )
