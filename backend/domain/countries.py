"""Country codes. Pure domain module (no framework or database imports).

Only the ISO 3166-1 alpha-2 *format* is checked (two uppercase ASCII letters). The module does
not carry a country list; the list of countries that matter for customs and road rules is a
versioned table of its own (customs_areas, later revision).
"""

import re

_COUNTRY_RE = re.compile(r"[A-Z]{2}")


def validate_country(value: str) -> str:
    if not _COUNTRY_RE.fullmatch(value):
        raise ValueError("country must be an ISO 3166-1 alpha-2 code (two uppercase letters)")
    return value
