"""Keep blocking waits responsive to signals delivered to other threads."""

from collections.abc import Callable
from threading import Event
from time import monotonic


def wait_slice(deadline: float | None, now: float) -> float:
    """Bound a single wait so the caller can handle pending Python signals."""
    return 0.1 if deadline is None else max(0.0, min(0.1, deadline - now))


def wait_for_event(
    event: Event,
    deadline: float | None = None,
    *,
    clock: Callable[[], float] = monotonic,
) -> bool:
    """Wait for completion or the absolute deadline, checking signals in between."""
    while not event.is_set():
        waited = wait_slice(deadline, clock())
        if not waited:
            return False
        event.wait(waited)
    return True
