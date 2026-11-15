"""In-memory failed-attempt limiter. Pure domain module (no framework or database imports).

Sliding window per key. State lives in one process only: good enough for a single-instance
deployment in phase 1; a shared store would be needed for several instances.
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import timedelta


class AttemptLimiter:
    def __init__(
        self,
        max_failures: int,
        window: timedelta,
        *,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_failures = max_failures
        self._window = window.total_seconds()
        self._max_keys = max_keys
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float] | None:
        attempts = self._failures.get(key)
        if attempts is None:
            return None
        while attempts and now - attempts[0] >= self._window:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
            return None
        return attempts

    def retry_after_seconds(self, key: str) -> int:
        """Seconds until the key may try again; 0 when it is not blocked."""
        with self._lock:
            now = self._clock()
            attempts = self._prune(key, now)
            if attempts is None or len(attempts) < self._max_failures:
                return 0
            remaining = self._window - (now - attempts[0])
            return max(1, int(remaining) + 1)

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            if key not in self._failures and len(self._failures) >= self._max_keys:
                self._evict(now)
            attempts = self._failures.setdefault(key, deque())
            attempts.append(now)
            # Never keep more than the limit; older entries cannot change the outcome.
            while len(attempts) > self._max_failures:
                attempts.popleft()

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _evict(self, now: float) -> None:
        for key in list(self._failures):
            self._prune(key, now)
        # Still full: drop the oldest entry so memory stays bounded under a flood of keys.
        if len(self._failures) >= self._max_keys:
            oldest = min(self._failures, key=lambda k: self._failures[k][-1])
            del self._failures[oldest]
