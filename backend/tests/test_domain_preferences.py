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
