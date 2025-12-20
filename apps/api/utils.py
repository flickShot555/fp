from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from dateutil import parser


def parse_any_date(value: Any) -> Optional[datetime]:
    """Best-effort date parser that returns naive UTC datetimes."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        except Exception:
            return None
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text)
        except Exception:
            try:
                dt = parser.parse(text, fuzzy=True)
            except Exception:
                return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def to_isoformat(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.replace(microsecond=0).isoformat()


def utcnow() -> datetime:
    return datetime.utcnow()
