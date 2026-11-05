"""Internal execution results behind the output-only compatibility API."""

from __future__ import annotations

from typing import NamedTuple

from esolangs.runtime._lifecycle import CompletionReport


# A frozen dataclass put the two-input pilot 10.2% over baseline.
class ExecutionResult(NamedTuple):
    """Output, stdin usage and explicit completion evidence.

    Input position counts characters in captured stdin; reads count successful
    IO calls and past-end counts failed reads, including caught EOFs.
    Counters are None for custom VMs without library-owned IO.
    """

    output: str
    input_position: int | None
    input_reads: int | None
    input_past_end: int | None
    completion: CompletionReport | None = None
