from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher

from domain.passwords import PasswordService
from domain.rate_limit import AttemptLimiter
from domain.sessions import (
    SessionPolicy,
    SessionStatus,
    evaluate_session,
    generate_token,
    hash_token,
    should_touch,
)
from domain.users import normalize_email

CHEAP = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
POLICY = SessionPolicy(idle_timeout=timedelta(hours=8), absolute_timeout=timedelta(days=7))


def test_hash_is_argon2id_and_verifies() -> None:
    service = PasswordService(CHEAP)
    stored = service.hash("secret-pass-1")
    assert stored.startswith("$argon2id$")
    assert service.verify("secret-pass-1", stored).ok
    assert not service.verify("other", stored).ok
    assert not service.verify("x", "not-a-hash").ok


def test_rehash_when_parameters_change() -> None:
    old = PasswordService(CHEAP).hash("secret-pass-1")
    upgraded = PasswordService(PasswordHasher(time_cost=2, memory_cost=8, parallelism=1))
    result = upgraded.verify("secret-pass-1", old)
    assert result.ok and result.new_hash is not None
    assert upgraded.verify("secret-pass-1", result.new_hash).new_hash is None
    # A wrong password never yields a new hash.
    assert upgraded.verify("wrong", old).new_hash is None


def test_token_is_random_and_hash_is_sha256_hex() -> None:
    a, b = generate_token(), generate_token()
    assert a != b and len(a) >= 43
    digest = hash_token(a)
    assert len(digest) == 64 and digest != a and digest == hash_token(a)


def test_session_evaluation() -> None:
    def status(**kw: object) -> SessionStatus:
        args: dict[str, object] = {
            "expires_at": NOW + timedelta(days=1),
            "last_seen_at": NOW - timedelta(hours=1),
            "revoked_at": None,
            "now": NOW,
            "policy": POLICY,
        }
        args.update(kw)
        return evaluate_session(**args)  # type: ignore[arg-type]

    assert status() is SessionStatus.VALID
    assert status(revoked_at=NOW) is SessionStatus.REVOKED
    assert status(expires_at=NOW) is SessionStatus.EXPIRED
    assert status(last_seen_at=NOW - timedelta(hours=8)) is SessionStatus.IDLE
    assert status(last_seen_at=NOW - timedelta(hours=7, minutes=59)) is SessionStatus.VALID


def test_should_touch_is_throttled() -> None:
    assert not should_touch(NOW - timedelta(seconds=10), NOW, POLICY)
    assert should_touch(NOW - timedelta(minutes=2), NOW, POLICY)


def test_normalize_email() -> None:
    assert normalize_email("  Admin@Demo.Example.com ") == "admin@demo.example.com"


def test_limiter_blocks_after_max_failures_and_expires() -> None:
    clock = [0.0]
    limiter = AttemptLimiter(3, timedelta(seconds=60), clock=lambda: clock[0])
    for _ in range(2):
        limiter.record_failure("k")
    assert limiter.retry_after_seconds("k") == 0
    limiter.record_failure("k")
    assert 0 < limiter.retry_after_seconds("k") <= 61
    assert limiter.retry_after_seconds("other") == 0
    clock[0] = 61.0
    assert limiter.retry_after_seconds("k") == 0


def test_limiter_reset_and_bounded_memory() -> None:
    limiter = AttemptLimiter(1, timedelta(minutes=1), max_keys=3)
    limiter.record_failure("a")
    limiter.reset("a")
    assert limiter.retry_after_seconds("a") == 0
    for i in range(10):
        limiter.record_failure(f"k{i}")
    assert len(limiter._failures) <= 3
