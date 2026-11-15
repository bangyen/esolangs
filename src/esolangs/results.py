"""Immutable execution results and successful completion evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport

__all__ = ["BoundaryCycle", "Completion", "CompletionReport", "ExecutionResult"]


# A frozen dataclass costs 1.8% per evaluated Brainfuck row (25.4 vs 25.0 us)
# against a NamedTuple; taken so a new field cannot break unpacking.
@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Output, stdin usage and explicit completion evidence.

    Input position counts characters in captured stdin; reads count successful
    IO calls and past-end counts failed reads, including caught EOFs.
    Counters are None for custom VMs without library-owned IO.
    Completion is absent before output finalization.
    Steps count completed cooperative commands, excluding a faulting command
    and post-halt output finalization; None when the runner does not count
    (``run`` counts only under ``max_steps``).
    Runtime failures retain an unfinished observation on EsolangError.observation.
    """

    output: str
    input_position: int | None
    input_reads: int | None
    input_past_end: int | None
    completion: CompletionReport | None = field(default=None, kw_only=True)
    steps: int | None = field(default=None, kw_only=True)

    def __repr__(self) -> str:
        """Render observations even with unusually large counts."""
        from esolangs.runtime.memory import repr_value

        return (
            f"{type(self).__qualname__}(output={self.output!r}, "
            f"input_position={repr_value(self.input_position)}, "
            f"input_reads={repr_value(self.input_reads)}, "
            f"input_past_end={repr_value(self.input_past_end)}, "
            f"completion={self.completion!r}, steps={repr_value(self.steps)})"
        )

    def __post_init__(self) -> None:
        """Reject invalid output, counters and completion evidence."""
        problem = self._invalid_fields()
        if problem is not None:
            from esolangs.exceptions import ArgumentError

            raise ArgumentError(problem)
        if type(self.output) is not str:
            object.__setattr__(self, "output", str.__str__(self.output))

    def _invalid_fields(self) -> str | None:
        output: object = self.output
        if type(output) is not str and not issubclass(type(output), str):
            return "invalid execution result: output must be text"
        counters = (self.input_position, self.input_reads, self.input_past_end)
        for value in counters:
            if value is not None and not _valid_count(value):
                return "invalid execution counter"
        if None in counters and counters != (None, None, None):
            return "incomplete execution input counters"
        if self.steps is not None and not _valid_count(self.steps):
            return "invalid execution counter"
        completion: object = self.completion
        if completion is not None:
            if not isinstance(completion, CompletionReport):
                return "invalid execution completion evidence"
            cycle = completion.cycle
            if (
                cycle is not None
                and self.steps is not None
                and self.steps != cycle.repeat_pass * cycle.commands_per_pass
            ):
                return "execution steps disagree with periodic completion evidence"
        return None


def _valid_count(value: int) -> bool:
    return type(value) is int and value >= 0
