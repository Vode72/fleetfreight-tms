import pytest

from domain.preferences import (
    DEFAULT_LANGUAGE,
    DEFAULT_THEME,
    LANGUAGES,
    THEMES,
    validate_language,
    validate_theme,
)


def test_defaults_are_allowed_values() -> None:
    assert DEFAULT_THEME in THEMES
    assert DEFAULT_LANGUAGE in LANGUAGES


def test_allowed_values() -> None:
    assert THEMES == ("business-light", "control-dark")
    assert LANGUAGES == ("en", "fi")


@pytest.mark.parametrize("theme", THEMES)
def test_valid_theme(theme: str) -> None:
    assert validate_theme(theme) == theme


@pytest.mark.parametrize("value", ["", "dark", "Business-Light", "control-dark "])
def test_invalid_theme(value: str) -> None:
    with pytest.raises(ValueError):
        validate_theme(value)


@pytest.mark.parametrize("language", LANGUAGES)
def test_valid_language(language: str) -> None:
    assert validate_language(language) == language


@pytest.mark.parametrize("value", ["", "sv", "EN", "fi-FI"])
def test_invalid_language(value: str) -> None:
    with pytest.raises(ValueError):
        validate_language(value)


def _in_list(values: tuple[str, ...] | frozenset[str] | list[str]) -> str:
    return ", ".join(f"'{v}'" for v in sorted(values))


def test_check_constraints_match_domain_values() -> None:
    """The model's and the migration's CHECK lists must list exactly the domain values."""
    from pathlib import Path

    from sqlalchemy import CheckConstraint

    from db.models import User

    checks = {
        c.name: str(c.sqltext)
        for c in User.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(c, CheckConstraint) and isinstance(c.name, str)
    }
    assert checks["ck_users_theme"] == f"theme IN ({_in_list(THEMES)})"
    assert checks["ck_users_language"] == f"language IN ({_in_list(LANGUAGES)})"

    migration = (
        Path(__file__).parents[1] / "migrations/versions/a1c4e7d90b25_add_user_preferences.py"
    )
    text = migration.read_text(encoding="utf-8")
    assert f"theme IN ({_in_list(THEMES)})" in text
    assert f"language IN ({_in_list(LANGUAGES)})" in text
