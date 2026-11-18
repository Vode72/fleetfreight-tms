from datetime import UTC, datetime

import pytest

from domain.registers import archive, is_archived

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def test_is_archived() -> None:
    assert not is_archived(None)
    assert is_archived(NOW)


def test_archive_sets_the_time_and_is_idempotent() -> None:
    assert archive(None, NOW) == NOW
    later = datetime(2026, 12, 1, tzinfo=UTC)
    assert archive(NOW, later) == NOW  # the first archive time stays


def test_archive_requires_a_timezone_aware_time() -> None:
    with pytest.raises(ValueError):
        archive(None, datetime(2026, 11, 18, 12, 0))
