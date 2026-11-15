"""Retain diagnostics for input consumed by an uncommitted instruction."""

from __future__ import annotations

from copy import copy
from typing import TYPE_CHECKING, NamedTuple

from esolangs.exceptions import ExecutionBudgetError, HaltError
from esolangs.runtime._state import WorkspaceVariant

if TYPE_CHECKING:
    from collections.abc import Callable

    from esolangs.runtime.io import IO


type _Rejection = ValueError | HaltError
type _Details = tuple[str, str, tuple[str, ...]] | tuple[str, str, tuple[str, ...], str]


class _Diagnostic(NamedTuple):
    error: _Rejection
    details: _Details
    cause: BaseException | None

    def fresh(self) -> _Rejection:
        """Build an error before this caller adds its own execution evidence."""
        error = copy(self.error)
        error.__dict__.pop("__notes__", None)
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
        details: _Details = (
            type(error).__name__,
            str(error),
            tuple(getattr(error, "__notes__", ())),
        )
        if isinstance(error, ExecutionBudgetError) and (
            bound := getattr(error, "bound", None)
        ):
            details = (*details, bound)
        # Copying preserves native slots and typed fields such as a budget's
        # bound. The observer adds output and observations per invocation.
        frozen = copy(error)
        for key in ("__notes__", "observation", "partial_output"):
            frozen.__dict__.pop(key, None)
        self._fault = _Diagnostic(frozen, details, error.__cause__)

    def raise_if_rejected(self) -> None:
        """Raise a fresh copy of an earlier rejection."""
        if self._fault is not None:
            raise self._fault.fresh() from self._fault.cause

    def read[T](self, io: IO, acquire: Callable[[], T]) -> T:
        """Retry reads that failed before any input became available."""
        if self._fault is not None:
            self.raise_if_rejected()
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
