"""Small UTC helpers that are safe to keep through later phases."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 form ending with Z."""
    return utc_now().isoformat().replace("+00:00", "Z")