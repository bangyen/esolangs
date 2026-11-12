"""Immutable execution results and successful completion evidence."""

from __future__ import annotations

from typing import NamedTuple

from esolangs.runtime._lifecycle import BoundaryCycle, Completion, CompletionReport

__all__ = ["BoundaryCycle", "Completion", "CompletionReport", "ExecutionResult"]


# A frozen dataclass put the two-input pilot 10.2% over baseline.
class ExecutionResult(NamedTuple):
    """Output, stdin usage and explicit completion evidence.

    Input position counts characters in captured stdin; reads count successful
    IO calls and past-end counts failed reads, including caught EOFs.
    Counters are None for custom VMs without library-owned IO.
    Completion is absent before output finalization.
    Steps count completed cooperative commands, excluding a faulting command
    and post-halt output finalization; None when the runner does not count.
    Runtime failures retain an unfinished observation on EsolangError.observation.
    """

    output: str
    input_position: int | None
    input_reads: int | None
    input_past_end: int | None
    completion: CompletionReport | None = None
    steps: int | None = None
