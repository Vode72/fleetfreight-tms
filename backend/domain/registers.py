"""Register rows are archived, not deleted (D72). Pure domain module.

`archived_at` is NULL while a row is active. An archived row stays in the database (history, old
trips and reports keep working) but is not offered in selection lists. Physical deletion is
blocked by RESTRICT foreign keys whenever the row is referenced.
"""

from datetime import datetime


def is_archived(archived_at: datetime | None) -> bool:
    """True when the row has been archived."""
    return archived_at is not None


def archive(archived_at: datetime | None, now: datetime) -> datetime:
    """The archive timestamp to store: archiving twice keeps the first time (idempotent)."""
    if now.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware (UTC)")
    return archived_at if archived_at is not None else now
