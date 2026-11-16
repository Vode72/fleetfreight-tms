"""User interface preferences (D9, D49). Pure domain module (no framework or database imports).

The allowed values are stored in the database (see the users CHECK constraints) and must match
the frontend: THEMES in frontend/src/theme/theme.ts and SUPPORTED_LANGUAGES in
frontend/src/i18n/index.ts. NULL in the database means "use the default".
"""

THEMES: tuple[str, ...] = ("business-light", "control-dark")
LANGUAGES: tuple[str, ...] = ("en", "fi")
DEFAULT_THEME = "business-light"
DEFAULT_LANGUAGE = "en"


def validate_theme(value: str) -> str:
    if value not in THEMES:
        raise ValueError(f"theme must be one of {', '.join(THEMES)}")
    return value


def validate_language(value: str) -> str:
    if value not in LANGUAGES:
        raise ValueError(f"language must be one of {', '.join(LANGUAGES)}")
    return value
