"""Deadline-bound snapshots of caller-owned input."""

from collections.abc import Callable
from contextvars import Context, copy_context
from dataclasses import dataclass
from threading import Event, Thread
from time import monotonic

from esolangs.exceptions import ExecutionTimeoutError
from esolangs.runtime._files import stream_read_deadline
from esolangs.runtime._input import (
    CheckedInput,
    InputFrame,
    InputSource,
    _BoundReader,
    check_input,
    read_input,
)
from esolangs.runtime._validate import _has_backing_type
from esolangs.runtime._wait import wait_slice


@dataclass(frozen=True, slots=True)
class DeferredInput:
    """CLI input to acquire once the interpreter has prepared the source."""

    read: Callable[[], str]


def preparation_expired(*, partial_output: str = "") -> ExecutionTimeoutError:
    """Report a preparation timeout with any known worker output."""
    error = ExecutionTimeoutError("execution timed out during preparation")
    error.bound = "preparation_timeout"
    error.partial_output = partial_output
    return error


def acquire[T](
    capture: Callable[[Callable[[], bool]], T | None],
    deadline: float,
    timeout_error: Callable[[], ExecutionTimeoutError],
    *,
    clock: Callable[[], float] = monotonic,
    context: Context | None = None,
) -> T:
    """Acquire caller-owned input off-thread, retaining exceptions and context."""
    box: list[T | BaseException | None] = []
    cancelled = Event()

    def stopped() -> bool:
        return cancelled.is_set() or clock() >= deadline

    def collect() -> None:
        try:
            box.append(None if stopped() else capture(stopped))
        except BaseException as exc:
            box.append(exc)

    # A blocking read may outlive its invocation. Leave its stream open and
    # let the capture stop at the next boundary.
    caller_context = copy_context() if context is None else context
    reader = Thread(target=caller_context.run, args=(collect,), daemon=True)
    try:
        reader.start()
        while reader.is_alive():
            waited = wait_slice(deadline, clock())
            if not waited:
                break
            reader.join(waited)
    finally:
        cancelled.set()
    if reader.is_alive() or clock() >= deadline:
        raise timeout_error()
    result = box[0]
    if isinstance(result, BaseException):
        raise result
    if result is None:
        raise timeout_error()
    return result


@dataclass(frozen=True, slots=True)
class PendingInput:
    """A bound reader sharing its deadline and context with the eventual read."""

    checked: CheckedInput
    deadline: float
    context: Context

    def snapshot(self, *, frame: InputFrame | None = None) -> str:
        """Consume the bound input after execution preflight."""

        def capture(_stopped: Callable[[], bool]) -> str:
            with stream_read_deadline(self.deadline):
                return read_input(self.checked, frame=frame)

        return acquire(
            capture,
            self.deadline,
            preparation_expired,
            clock=monotonic,
            context=self.context,
        )


def bind_prepared_input(
    stdin: InputSource, timeout: float
) -> CheckedInput | PendingInput:
    """Decode bytes or bind a reader under the preparation deadline."""
    if _has_backing_type(stdin, str):
        return read_input(stdin)
    deadline = monotonic() + timeout
    context = copy_context()

    def bind(_stopped: Callable[[], bool]) -> PendingInput:
        with stream_read_deadline(deadline):
            return PendingInput(check_input(stdin), deadline, context)

    bound = acquire(
        bind,
        deadline,
        preparation_expired,
        clock=monotonic,
        context=context,
    )
    return bound if isinstance(bound.checked, _BoundReader) else bound.checked
