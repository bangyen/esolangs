"""Uniform completion, rejection, fault and limit observations."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Literal

from esolangs.exceptions import (
    ArgumentError,
    EsolangError,
    ExecutionBudgetError,
    InputExhaustedError,
    InterpreterLimitError,
    MissingDependencyError,
    ProgramError,
    TemplateError,
    UnknownLanguageError,
)
from esolangs.results import CompletionReport, ExecutionResult
from esolangs.runtime._validate import _has_backing_type

FailureStatus = Literal["rejected", "input_exhausted", "limit", "fault"]
OutcomeStatus = Literal["completed", "rejected", "input_exhausted", "limit", "fault"]


@dataclass(slots=True)
class _FailureEvidence:
    error: EsolangError | None = None
    observation: ExecutionResult | None = None


_FAILURE_EVIDENCE: ContextVar[_FailureEvidence | None] = ContextVar(
    "failure_evidence", default=None
)
_UNOBSERVED = ExecutionResult("", None, None, None)


@contextmanager
def _track_acquisition_failures() -> Iterator[None]:
    """Distinguish caller failures even when no execution outcome is requested."""
    if _FAILURE_EVIDENCE.get() is not None:
        yield
        return
    token = _FAILURE_EVIDENCE.set(_FailureEvidence())
    try:
        yield
    finally:
        _FAILURE_EVIDENCE.reset(token)


def _is_acquisition_failure(error: BaseException) -> bool:
    """Check whether this exact error came from a caller's acquisition hook."""
    state = _FAILURE_EVIDENCE.get()
    return (
        state is not None and state.error is error and state.observation is _UNOBSERVED
    )


def _remember_acquisition_failure(error: EsolangError) -> None:
    """Mark an error that escaped source or input acquisition without modifying it."""
    _remember_failure_evidence(error, _UNOBSERVED)


def _remember_failure_evidence(
    error: EsolangError, observation: ExecutionResult
) -> None:
    """Keep this invocation's evidence separate from a propagated error."""
    failure = _FAILURE_EVIDENCE.get()
    if failure is not None:
        failure.error = error
        failure.observation = observation


def _failure_status(error: EsolangError) -> FailureStatus:
    if _has_backing_type(error, InputExhaustedError):
        return "input_exhausted"
    if issubclass(type(error), (ExecutionBudgetError, InterpreterLimitError)):
        return "limit"
    if issubclass(
        type(error),
        (
            ArgumentError,
            ProgramError,
            TemplateError,
            UnknownLanguageError,
            MissingDependencyError,
        ),
    ):
        return "rejected"
    return "fault"


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    """One completed result or failed observation, retaining its original error.

    A limit never constitutes a Boolean answer or completion proof. Counters
    remain unavailable when execution was not observed.
    """

    status: OutcomeStatus
    observation: ExecutionResult
    error: EsolangError | None = field(default=None, kw_only=True)

    def __new__(
        cls, *args: object, error: EsolangError | None = None, **kwargs: object
    ) -> ExecutionOutcome:
        """Preserve the original constructor while returning a concrete outcome."""
        if cls is ExecutionOutcome and (args or kwargs):
            return object.__new__(CompletedRun if error is None else FailedRun)
        return object.__new__(cls)

    def __setstate__(self, state: list[object]) -> None:
        """Restore legacy three-field pickle records as concrete outcomes."""
        status, observation, error = state
        if type(self) is ExecutionOutcome:
            object.__setattr__(
                self, "__class__", CompletedRun if error is None else FailedRun
            )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "observation", observation)
        object.__setattr__(self, "error", error)
        self.__post_init__()

    def __post_init__(self) -> None:
        """Require completion evidence or a matching unfinished failure."""
        if not _has_backing_type(self.observation, ExecutionResult):
            raise ArgumentError("an outcome requires an execution observation")
        status: str = self.status
        if type(status) is not str:
            if not issubclass(type(status), str):
                raise ArgumentError("an outcome requires a text status")
            status = str.__str__(status)
            object.__setattr__(self, "status", status)

    @property
    def bound(self) -> str | None:
        """The exhausted caller-set budget, when the error declares one."""
        if _has_backing_type(self.error, ExecutionBudgetError):
            bound = getattr(self.error, "bound", None)
            if _has_backing_type(bound, str):
                return str.__str__(bound)
        return None

    def unwrap(self) -> ExecutionResult:
        """Return completion or raise the retained public error."""
        if self.error is not None:
            raise self.error
        return self.observation


class CompletedRun(ExecutionOutcome):
    """A finalized observation with completion evidence."""

    __slots__ = ()
    status: Literal["completed"]
    error: None

    def __post_init__(self) -> None:
        """Require the successful case of the execution contract."""
        super().__post_init__()
        if (
            self.status != "completed"
            or self.error is not None
            or not _has_backing_type(self.observation.completion, CompletionReport)
        ):
            raise ArgumentError("a completed outcome requires completion evidence")

    @classmethod
    def from_result(cls, observation: ExecutionResult) -> CompletedRun:
        """Finish a run with its observed result."""
        return cls("completed", observation)

    @property
    def completion(self) -> CompletionReport:
        """Return the validated completion evidence."""
        completion = self.observation.completion
        assert completion is not None
        return completion


class FailedRun(ExecutionOutcome):
    """An unfinished observation with the original execution error."""

    __slots__ = ()
    status: FailureStatus
    error: EsolangError

    def __post_init__(self) -> None:
        """Require the failure case of the execution contract."""
        super().__post_init__()
        if (
            not _has_backing_type(self.error, EsolangError)
            or self.status != _failure_status(self.error)
            or self.observation.completion is not None
        ):
            raise ArgumentError(
                "a failed outcome requires its error and unfinished observation"
            )


def _failed_outcome(
    error: EsolangError, *, observation: ExecutionResult | None = None
) -> ExecutionOutcome:
    """Pair this invocation's unfinished observation with the original error."""
    if observation is None:
        observation = error.observation
        if observation is None:
            observation = ExecutionResult(error.partial_output, None, None, None)
        elif (
            _has_backing_type(observation, ExecutionResult)
            and observation.completion is not None
        ):
            observation = _UNOBSERVED
    return FailedRun(_failure_status(error), observation, error=error)


def _capture_outcome[**P](
    execute: Callable[P, ExecutionOutcome],
) -> Callable[P, ExecutionOutcome]:
    """Capture deliberate boundary failures; implementation bugs still escape."""

    @wraps(execute)
    def capture(*args: P.args, **kwargs: P.kwargs) -> ExecutionOutcome:
        failure = _FailureEvidence()
        # Isolated acquisition uses a copy of this context in its reader thread.
        token = _FAILURE_EVIDENCE.set(failure)
        try:
            return execute(*args, **kwargs)
        except EsolangError as error:
            observation = failure.observation if failure.error is error else None
            return _failed_outcome(error, observation=observation)
        finally:
            _FAILURE_EVIDENCE.reset(token)

    return capture
