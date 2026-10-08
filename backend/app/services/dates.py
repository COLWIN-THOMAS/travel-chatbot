"""Calendar helpers for trips. "Today" is always the date in India (UTC+05:30), the app's home market,
so a trip starting "today" does not flip to the past at 6:30 pm UTC."""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

IST = timezone(timedelta(hours=5, minutes=30))

UNDECIDED = "undecided"  # chat-slot sentinel: the traveller has no dates yet

# Planning a new trip must start today or later; editing an existing trip may also fix a date that was
# entered wrongly or record a trip that is already under way.
MAX_DAYS_AHEAD = 730
MAX_DAYS_BACK_EDIT = 365


def today_ist() -> date:
    return datetime.now(IST).date()


def parse_iso(value) -> Optional[date]:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def end_date(start: Optional[date], days_count: int) -> Optional[date]:
    return start + timedelta(days=max(days_count, 1) - 1) if start else None


def day_date(start: Optional[date], day_number: int) -> Optional[date]:
    return start + timedelta(days=day_number - 1) if start else None


def phase(start: Optional[date], days_count: int, today: Optional[date] = None) -> str:
    """undated | upcoming | ongoing | completed"""
    if start is None:
        return "undated"
    today = today or today_ist()
    if today < start:
        return "upcoming"
    if today > end_date(start, days_count):
        return "completed"
    return "ongoing"


def days_elapsed(start: Optional[date], today: Optional[date] = None) -> int:
    """How many whole days of the trip are strictly in the past (0 for undated or not yet started)."""
    if start is None:
        return 0
    today = today or today_ist()
    return max((today - start).days, 0)


def check_new_trip_date(d: date, today: Optional[date] = None) -> Optional[str]:
    today = today or today_ist()
    if d < today:
        return "That date has already passed - which day do you start?"
    if d > today + timedelta(days=MAX_DAYS_AHEAD):
        return "I can only plan trips up to two years ahead."
    return None


def check_edit_date(d: date, today: Optional[date] = None) -> Optional[str]:
    today = today or today_ist()
    if d < today - timedelta(days=MAX_DAYS_BACK_EDIT):
        return "That date is too far in the past."
    if d > today + timedelta(days=MAX_DAYS_AHEAD):
        return "Trips can start at most two years from now."
    return None


def pretty(d: date) -> str:
    return "{} {} {} {}".format(d.strftime("%a"), d.day, d.strftime("%b"), d.year)


def pretty_range(start: date, days_count: int) -> str:
    if days_count <= 1:
        return pretty(start)
    return "{} - {}".format(pretty(start), pretty(end_date(start, days_count)))
