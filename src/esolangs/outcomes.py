"""Uniform completion, rejection, fault and limit observations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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
from esolangs.results import ExecutionResult

OutcomeStatus = Literal["completed", "rejected", "input_exhausted", "limit", "fault"]


def _failure_status(error: EsolangError) -> OutcomeStatus:
    if isinstance(error, InputExhaustedError):
        return "input_exhausted"
    if isinstance(error, (ExecutionBudgetError, InterpreterLimitError)):
        return "limit"
    if isinstance(
        error,
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
    error: EsolangError | None = None

    def __post_init__(self) -> None:
        """Require completion evidence or a matching unfinished failure."""
        if not isinstance(self.observation, ExecutionResult):
            raise ArgumentError("an outcome requires an execution observation")
        if self.error is None:
            if self.status != "completed" or self.observation.completion is None:
                raise ArgumentError("a completed outcome requires completion evidence")
        elif (
            not isinstance(self.error, EsolangError)
            or self.status != _failure_status(self.error)
            or self.observation.completion is not None
        ):
            raise ArgumentError(
                "a failed outcome requires its error and unfinished observation"
            )

    @property
    def bound(self) -> str | None:
        """The exhausted caller-set budget, when the error declares one."""
        return (
            self.error.bound if isinstance(self.error, ExecutionBudgetError) else None
        )

    def unwrap(self) -> ExecutionResult:
        """Return completion or raise the retained public error."""
        if self.error is not None:
            raise self.error
        return self.observation


def _failed_outcome(error: EsolangError) -> ExecutionOutcome:
    """Retain the original error and its unfinished execution observation."""
    observation = error.observation
    if observation is None:
        observation = ExecutionResult(error.partial_output, None, None, None)
    return ExecutionOutcome(_failure_status(error), observation, error)


def _capture_outcome[**P](
    execute: Callable[P, ExecutionOutcome],
) -> Callable[P, ExecutionOutcome]:
    """Capture deliberate boundary failures; implementation bugs still escape."""

    @wraps(execute)
    def capture(*args: P.args, **kwargs: P.kwargs) -> ExecutionOutcome:
        try:
            return execute(*args, **kwargs)
        except EsolangError as error:
            return _failed_outcome(error)

    return capture
