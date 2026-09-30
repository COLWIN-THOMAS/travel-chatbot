from app import security
from tests.conftest import register


def test_register_login_me(client):
    headers, user = register(client, "Ann@Example.com")
    assert user["email"] == "ann@example.com"  # normalised
    assert client.get("/auth/me", headers=headers).json()["email"] == "ann@example.com"
    r = client.post("/auth/login", json={"email": "ann@example.com", "password": "password123"})
    assert r.status_code == 200 and r.json()["access_token"]


def test_duplicate_email_conflict(client):
    register(client, "dup@example.com")
    r = client.post("/auth/register", json={"email": "DUP@example.com", "password": "password123"})
    assert r.status_code == 409


def test_wrong_password_and_unknown_user_are_indistinguishable(client):
    register(client, "who@example.com")
    a = client.post("/auth/login", json={"email": "who@example.com", "password": "wrongpass1"})
    b = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrongpass1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_password_validation(client):
    assert client.post("/auth/register", json={"email": "a@example.com", "password": "short"}).status_code == 422
    assert client.post("/auth/register", json={"email": "a@example.com", "password": "x" * 73}).status_code == 422
    assert client.post("/auth/register", json={"email": "not-an-email", "password": "password123"}).status_code == 422


def test_protected_routes_require_valid_token(client):
    assert client.get("/trips").status_code == 401
    assert client.get("/trips", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_password_hashing_roundtrip():
    h = security.hash_password("s3cret-pass")
    assert h != "s3cret-pass"
    assert security.verify_password("s3cret-pass", h)
    assert not security.verify_password("other", h)
    assert not security.verify_password("anything", None)


def test_photo_signature_rejects_tampering_and_expiry():
    signed = security.sign_photo("places/abc/photos/xyz", 800, ttl_seconds=60)
    assert security.verify_photo(signed["name"], 800, signed["exp"], signed["sig"])
    assert not security.verify_photo("places/abc/photos/other", 800, signed["exp"], signed["sig"])
    assert not security.verify_photo(signed["name"], 1200, signed["exp"], signed["sig"])
    expired = security.sign_photo("places/abc/photos/xyz", 800, ttl_seconds=-5)
    assert not security.verify_photo(expired["name"], 800, expired["exp"], expired["sig"])


def test_login_is_throttled_after_repeated_failures_and_success_resets(client):
    register(client, "brute@example.com")
    bad = {"email": "brute@example.com", "password": "wrong-password"}
    for _ in range(7):
        assert client.post("/auth/login", json=bad).status_code == 401
    ok = client.post("/auth/login", json={"email": "brute@example.com", "password": "password123"})
    assert ok.status_code == 200  # success before the limit clears the counter
    for _ in range(8):
        assert client.post("/auth/login", json=bad).status_code == 401
    blocked = client.post("/auth/login", json={"email": "brute@example.com", "password": "password123"})
    assert blocked.status_code == 429  # even the right password is refused while blocked
    other = client.post("/auth/login", json={"email": "someone-else@example.com", "password": "wrong-password"})
    assert other.status_code == 401  # other accounts are unaffected


def test_throttle_window_expires(monkeypatch):
    from app import security
    t = security.FailureThrottle(limit=2, window_seconds=60)
    now = [1000.0]
    monkeypatch.setattr(security.time, "time", lambda: now[0])
    t.record_failure("k"); t.record_failure("k")
    assert t.blocked("k")
    now[0] += 61
    assert not t.blocked("k")
