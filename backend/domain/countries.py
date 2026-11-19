"""Country codes. Pure domain module (no framework or database imports).

Only the ISO 3166-1 alpha-2 *format* is checked (two uppercase ASCII letters). The module does
not carry a country list: the countries that matter for road rules are reference data in the
`countries` table (2B-3a, D84), and customs areas get a table of their own (2B-3c).
"""

import re

_COUNTRY_RE = re.compile(r"[A-Z]{2}")


def validate_country(value: str) -> str:
    if not _COUNTRY_RE.fullmatch(value):
        raise ValueError("country must be an ISO 3166-1 alpha-2 code (two uppercase letters)")
    return value
