"""Password hashing with argon2id. Pure domain module (no framework or database imports)."""

from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Hashed once per service and used to burn the same CPU time when the account does not exist,
# so response time does not reveal whether an e-mail address is registered.
_DUMMY_PASSWORD = "dummy-password-for-timing-equalisation"


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    # Set only when the password was correct and the stored hash uses outdated parameters.
    new_hash: str | None = None


class PasswordService:
    """Hashes and verifies passwords. argon2id with the library's current recommended defaults.

    The hasher can be injected so tests can use cheap parameters and simulate a parameter change.
    """

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher()  # argon2id by default
        # Computed eagerly (not on first use) with the same parameters as real hashes, so the
        # first unknown-user login is not distinguishable by timing.
        self._dummy_hash = self._hasher.hash(_DUMMY_PASSWORD)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, stored_hash: str) -> VerifyResult:
        """Check a password. On success also report a fresh hash if parameters have changed."""
        try:
            self._hasher.verify(stored_hash, password)
        except VerifyMismatchError, VerificationError, InvalidHashError:
            return VerifyResult(ok=False)
        if self._hasher.check_needs_rehash(stored_hash):
            return VerifyResult(ok=True, new_hash=self._hasher.hash(password))
        return VerifyResult(ok=True)

    def verify_dummy(self, password: str) -> None:
        """Do a full hash comparison against a dummy hash; the result is always a failure."""
        self.verify(password, self._dummy_hash)
