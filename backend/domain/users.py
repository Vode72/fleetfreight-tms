import hashlib
import hmac

"""User-related pure helpers."""


def normalize_email(email: str) -> str:
    """Canonical form stored in the database and used for lookups: trimmed and lower-case."""
    return email.strip().lower()


def email_log_id(email: str, key: bytes) -> str:
    """Keyed pseudonym of an e-mail address for log correlation (HMAC-SHA256, truncated).

    Unlike a plain hash it cannot be reversed by hashing guessed addresses without the key.
    """
    return hmac.new(key, normalize_email(email).encode("utf-8"), hashlib.sha256).hexdigest()[:12]
