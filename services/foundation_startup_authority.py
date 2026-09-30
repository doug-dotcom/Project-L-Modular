"""Non-blocking startup reconciliation for optional Shine Foundation authority."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from services.foundation_companion_service import (
    ensure_foundation_delegation,
    foundation_account_owner,
)


RETRYABLE_STATUSES = frozenset({"busy", "unavailable"})
DEFAULT_RETRY_DELAYS_SECONDS = (2.0, 5.0, 12.0, 30.0)
MAX_RETRY_DELAY_SECONDS = 30.0
FOUNDATION_CHECK_TIMEOUT_SECONDS = 6.0
LEASE_RETRY_CUSHION_SECONDS = 0.5
MAX_BUSY_OUTCOMES = 8


class FoundationStartupAuthority:
    """Reconcile Foundation authority without holding Project L startup open.

    Foundation is optional to L's standalone purpose, so startup must never wait
    on a remote refresh or a lease held by another deployment. This coordinator
    publishes only content-free operational state and retries a bounded number
    of retry-safe outcomes in a daemon worker.
    """

    def __init__(
        self,
        *,
        owner_resolver: Callable[[Any], str | None] = foundation_account_owner,
        ensure_impl: Callable[..., dict] = ensure_foundation_delegation,
        retry_delays_seconds: tuple[float, ...] = DEFAULT_RETRY_DELAYS_SECONDS,
        max_retry_delay_seconds: float = MAX_RETRY_DELAY_SECONDS,
        check_timeout_seconds: float = FOUNDATION_CHECK_TIMEOUT_SECONDS,
        thread_factory: Callable[..., Any] = threading.Thread,
        wait_impl: Callable[[float], bool] | None = None,
        now_impl: Callable[[], datetime] | None = None,
        max_busy_outcomes: int = MAX_BUSY_OUTCOMES,
    ):
        if not retry_delays_seconds:
            raise ValueError("at least one retry delay is required")
        if any(delay < 0 for delay in retry_delays_seconds):
            raise ValueError("retry delays must be non-negative")
        if max_retry_delay_seconds <= 0:
            raise ValueError("max retry delay must be positive")
        if check_timeout_seconds <= 0:
            raise ValueError("check timeout must be positive")
        if max_busy_outcomes < 1:
            raise ValueError("max busy outcomes must be positive")

        self._owner_resolver = owner_resolver
        self._ensure_impl = ensure_impl
        self._retry_delays = tuple(float(delay) for delay in retry_delays_seconds)
        self._max_retry_delay = float(max_retry_delay_seconds)
        self._check_timeout = float(check_timeout_seconds)
        self._thread_factory = thread_factory
        self._wait_impl = wait_impl
        self._now_impl = now_impl or (lambda: datetime.now(timezone.utc))
        self._max_busy_outcomes = int(max_busy_outcomes)

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._on_transition = None
        self._state = {
            "status": "not_started",
            "attempts": 0,
            "background_retry": False,
            "retry_exhausted": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def _publish(
        self,
        *,
        status: str,
        attempts: int,
        background_retry: bool,
        retry_exhausted: bool = False,
    ) -> dict[str, Any]:
        snapshot = {
            "status": str(status or "unavailable"),
            "attempts": max(0, int(attempts)),
            "background_retry": bool(background_retry),
            "retry_exhausted": bool(retry_exhausted),
        }
        with self._lock:
            self._state = snapshot
            callback = self._on_transition
        if callback is not None:
            try:
                callback(dict(snapshot))
            except Exception:
                # Observability must never interfere with authority recovery.
                pass
        return snapshot

    def _retry_delay(self, result: dict, retry_index: int) -> float:
        retry_after = result.get("retry_after")
        delay = None

        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            if isinstance(retry_after, str) and retry_after.strip():
                try:
                    target = datetime.fromisoformat(
                        retry_after.strip().replace("Z", "+00:00")
                    )
                    if target.tzinfo is None:
                        target = target.replace(tzinfo=timezone.utc)
                    now = self._now_impl()
                    if now.tzinfo is None:
                        now = now.replace(tzinfo=timezone.utc)
                    delay = (
                        target.astimezone(timezone.utc)
                        - now.astimezone(timezone.utc)
                    ).total_seconds() + LEASE_RETRY_CUSHION_SECONDS
                except (TypeError, ValueError):
                    delay = None

        if delay is None:
            delay = self._retry_delays[
                min(retry_index, len(self._retry_delays) - 1)
            ]
        if delay <= 0:
            delay = LEASE_RETRY_CUSHION_SECONDS
        return min(max(delay, LEASE_RETRY_CUSHION_SECONDS), self._max_retry_delay)

    def _wait(self, delay: float) -> bool:
        if self._wait_impl is not None:
            return bool(self._wait_impl(delay))
        return self._stop.wait(delay)

    @staticmethod
    def _retryable(result: dict) -> bool:
        status = str(result.get("status") or "unavailable")
        if status not in RETRYABLE_STATUSES:
            return False
        if status == "unavailable" and result.get("retry_safe") is False:
            return False
        return True

    def _run(self, db) -> None:
        try:
            owner_id = self._owner_resolver(db)
        except Exception:
            owner_id = None
            owner_lookup_failed = True
        else:
            owner_lookup_failed = False

        if owner_lookup_failed:
            result = {"status": "unavailable", "retry_safe": True}
        elif not owner_id:
            self._publish(
                status="not_configured",
                attempts=0,
                background_retry=False,
            )
            return
        else:
            result = {}

        attempts = 0
        unavailable_outcomes = 0
        busy_outcomes = 0
        max_unavailable_outcomes = len(self._retry_delays) + 1

        while True:
            if self._stop.is_set():
                self._publish(
                    status=self.snapshot().get("status", "stopped"),
                    attempts=attempts,
                    background_retry=False,
                )
                return

            attempts += 1

            if owner_lookup_failed:
                try:
                    owner_id = self._owner_resolver(db)
                except Exception:
                    owner_id = None
                if owner_id:
                    owner_lookup_failed = False
                else:
                    result = {"status": "unavailable", "retry_safe": True}

            if not owner_lookup_failed:
                try:
                    result = self._ensure_impl(
                        db,
                        owner_id,
                        timeout_seconds=self._check_timeout,
                    )
                except Exception:
                    result = {"status": "unavailable", "retry_safe": True}

            if not isinstance(result, dict):
                result = {"status": "unavailable", "retry_safe": True}

            status = str(result.get("status") or "unavailable")
            retryable = self._retryable(result)
            if not retryable:
                self._publish(
                    status=status,
                    attempts=attempts,
                    background_retry=False,
                )
                return

            if status == "busy":
                busy_outcomes += 1
                retry_exhausted = busy_outcomes >= self._max_busy_outcomes
                retry_index = busy_outcomes - 1
            else:
                unavailable_outcomes += 1
                retry_exhausted = (
                    unavailable_outcomes >= max_unavailable_outcomes
                )
                retry_index = unavailable_outcomes - 1

            self._publish(
                status=status,
                attempts=attempts,
                background_retry=not retry_exhausted,
                retry_exhausted=retry_exhausted,
            )

            if retry_exhausted:
                return

            delay = self._retry_delay(result, retry_index)
            if self._wait(delay):
                self._publish(
                    status=status,
                    attempts=attempts,
                    background_retry=False,
                )
                return

    def start(self, db, *, on_transition: Callable[[dict], None] | None = None) -> dict:
        """Schedule reconciliation and return immediately with safe state."""
        if db is None:
            self._on_transition = on_transition
            return self._publish(
                status="not_configured",
                attempts=0,
                background_retry=False,
            )

        with self._lock:
            existing = self._thread
            if existing is not None and existing.is_alive():
                if on_transition is not None:
                    self._on_transition = on_transition
                return dict(self._state)

            self._stop.clear()
            self._on_transition = on_transition
            self._state = {
                "status": "checking",
                "attempts": 0,
                "background_retry": True,
                "retry_exhausted": False,
            }
            thread = self._thread_factory(
                target=self._run,
                args=(db,),
                name="foundation-startup-authority",
                daemon=True,
            )
            self._thread = thread
            snapshot = dict(self._state)
            callback = self._on_transition

        if callback is not None:
            try:
                callback(dict(snapshot))
            except Exception:
                pass
        thread.start()
        return snapshot

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self._state.get("background_retry"):
                self._state = {
                    **self._state,
                    "background_retry": False,
                }


FOUNDATION_STARTUP_AUTHORITY = FoundationStartupAuthority()
