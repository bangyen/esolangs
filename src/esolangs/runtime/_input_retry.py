"""Retain diagnostics for input consumed by an uncommitted instruction."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.runtime._state import WorkspaceVariant

if TYPE_CHECKING:
    from collections.abc import Callable

    from esolangs.runtime.io import IO


type _Rejection = ValueError | HaltError
type _Details = tuple[str, str, tuple[str, ...]]


class _Diagnostic(NamedTuple):
    kind: type[_Rejection]
    args: tuple[object, ...]
    details: _Details
    cause: BaseException | None

    def fresh(self) -> _Rejection:
        """Build an error before this caller adds its own execution evidence."""
        error = BaseException.__new__(self.kind, *self.args)
        for note in self.details[2]:
            error.add_note(note)
        return error


class RejectedInput:
    """Replay an accepted input's failure without fetching another value."""

    _fault: _Diagnostic | None = None

    @property
    def details(self) -> _Details | None:
        """Return the stable, hashable diagnostic without traceback or IO."""
        return self._fault.details if self._fault is not None else None

    def remember(self, error: _Rejection) -> None:
        """Keep the failure of a value already delivered to the interpreter."""
        kind = type(error)
        details = kind.__name__, str(error), tuple(getattr(error, "__notes__", ()))
        self._fault = _Diagnostic(kind, error.args, details, error.__cause__)

    def read[T](self, io: IO, acquire: Callable[[], T]) -> T:
        """Retry reads that failed before any input became available."""
        if self._fault is not None:
            raise self._fault.fresh() from self._fault.cause
        before = io.progress()
        try:
            return acquire()
        except (ValueError, HaltError) as error:
            if io.progress() != before:
                self.remember(error)
            raise

    def cursor(self, progress: int) -> int | WorkspaceVariant:
        """Account for a rejection alongside the input progress."""
        fault = self.details
        if fault is not None:
            return WorkspaceVariant("rejected_input", (progress, *fault))
        return progress

    def snapshot(self, boundary: tuple[object, ...]) -> tuple[object, ...]:
        """Keep the existing snapshot shape at committed boundaries."""
        fault = self.details
        return (*boundary, fault) if fault is not None else boundary
