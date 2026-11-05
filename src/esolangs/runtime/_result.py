"""Internal execution results behind the output-only compatibility API."""

from __future__ import annotations

from typing import NamedTuple

from esolangs.runtime._lifecycle import CompletionReport


# A frozen dataclass put the two-input pilot 10.2% over baseline.
class ExecutionResult(NamedTuple):
    """Output and captured stdin usage; legacy completion remains unknown.

    Input position counts characters in captured stdin; reads count successful
    IO calls and past-end counts failed reads, including caught EOFs.
    """

    output: str
    input_position: int
    input_reads: int
    input_past_end: int
    completion: CompletionReport | None = None
