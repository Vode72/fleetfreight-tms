import pytest
from pydantic import ValidationError

from tests.conftest import make_settings


def test_gdp_default_validity_is_twelve_months() -> None:
    assert make_settings().gdp_training_default_validity_months == 12


def test_gdp_default_validity_is_configurable() -> None:
    assert (
        make_settings(gdp_training_default_validity_months=24).gdp_training_default_validity_months
        == 24
    )


@pytest.mark.parametrize("value", [0, -1, 121])
def test_gdp_default_validity_is_bounded(value: int) -> None:
    with pytest.raises(ValidationError):
        make_settings(gdp_training_default_validity_months=value)


def test_gdp_default_validity_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import Settings

    monkeypatch.setenv("GDP_TRAINING_DEFAULT_VALIDITY_MONTHS", "18")
    assert Settings(_env_file=None).gdp_training_default_validity_months == 18
