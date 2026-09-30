import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app import config

# A valid bcrypt hash of a random string; used to equalise login timing when the email is unknown.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: Optional[str]) -> bool:
    target = password_hash.encode("utf-8") if password_hash else _DUMMY_HASH
    try:
        ok = bcrypt.checkpw(password.encode("utf-8"), target)
    except ValueError:
        return False
    return ok and password_hash is not None


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[uuid.UUID]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None


# --- Signed photo URLs -------------------------------------------------------
# Place photos are billed per fetch, so the proxy only serves URLs that this server signed.

def _photo_signature(name: str, width: int, exp: int) -> str:
    msg = "{}|{}|{}".format(name, width, exp).encode("utf-8")
    return hmac.new(config.JWT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def sign_photo(name: str, width: int = 800, ttl_seconds: int = 6 * 3600) -> dict:
    exp = int(time.time()) + ttl_seconds
    return {"name": name, "w": width, "exp": exp, "sig": _photo_signature(name, width, exp)}


def verify_photo(name: str, width: int, exp: int, sig: str) -> bool:
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(_photo_signature(name, width, exp), sig)


# --- Login throttling ----------------------------------------------------------
class FailureThrottle:
    """In-memory limiter for failed logins per (client, email). Single-process; use a shared store when scaling out."""

    def __init__(self, limit: int = 8, window_seconds: int = 900) -> None:
        self.limit, self.window = limit, window_seconds
        self._failures: dict = {}

    def _prune(self, key, now: float) -> list:
        recent = [t for t in self._failures.get(key, []) if now - t < self.window]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def blocked(self, key) -> bool:
        return len(self._prune(key, time.time())) >= self.limit

    def record_failure(self, key) -> None:
        now = time.time()
        self._prune(key, now)
        self._failures.setdefault(key, []).append(now)
        if len(self._failures) > 10000:  # bound memory under attack
            self._failures.clear()

    def reset(self, key) -> None:
        self._failures.pop(key, None)

    def clear(self) -> None:
        self._failures.clear()


login_throttle = FailureThrottle()
