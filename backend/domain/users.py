"""User-related pure helpers."""


def normalize_email(email: str) -> str:
    """Canonical form stored in the database and used for lookups: trimmed and lower-case."""
    return email.strip().lower()
